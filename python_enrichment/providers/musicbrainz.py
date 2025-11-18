"""MusicBrainz provider for enrichment with strict 1 req/sec rate limiting."""

import asyncio
import random
import time
from typing import Optional, Dict, Any
import httpx

try:
    from ..config import config
    from ..structured_logging import log_provider_call
except ImportError:
    from config import config
    from structured_logging import log_provider_call


class RateLimiter:
    """Rate limiter to enforce 1 request per second."""

    def __init__(self, requests_per_second: float = 1.0):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Maximum requests per second
        """
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time: Optional[float] = None
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire permission to make a request (waits if necessary)."""
        async with self._lock:
            now = time.time()
            if self.last_request_time is not None:
                elapsed = now - self.last_request_time
                if elapsed < self.min_interval:
                    wait_time = self.min_interval - elapsed
                    await asyncio.sleep(wait_time)
                    now = time.time()
            self.last_request_time = now


# Global rate limiter instance
_rate_limiter = RateLimiter(requests_per_second=1.0)


async def _retry_with_backoff(
    func, max_retries: int = None, base_delay: float = 0.1
) -> Optional[Any]:
    """
    Retry function with exponential backoff and jitter.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retries (uses config default if None)
        base_delay: Base delay in seconds

    Returns:
        Function result or None on failure
    """
    max_retries = max_retries or config.ENRICH_MAX_RETRIES
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                # Exponential backoff with jitter
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                await asyncio.sleep(delay)
            else:
                break

    return None


async def enrich_musicbrainz(artist_name: str) -> Optional[Dict[str, Any]]:
    """
    Enrich artist using MusicBrainz.

    Args:
        artist_name: Artist name to search for

    Returns:
        Dictionary with mbid, name, urls, or None on failure
    """
    start_time = time.time()
    trace_id = getattr(enrich_musicbrainz, "_trace_id", "unknown")

    # Enforce rate limit
    await _rate_limiter.acquire()

    async def _fetch():
        """Internal fetch function for retry logic."""
        async with httpx.AsyncClient(timeout=config.ENRICH_REQUEST_TIMEOUT_SECS) as client:
            # MusicBrainz API: search for artist
            search_url = "https://musicbrainz.org/ws/2/artist/"
            params = {
                "query": f'artist:"{artist_name}"',
                "fmt": "json",
                "limit": 1,
            }
            headers = {
                "User-Agent": "AIhub-Enrichment/1.0 (https://github.com/your-repo)",
            }

            try:
                response = await client.get(search_url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()

                artists = data.get("artists", [])
                if not artists:
                    return None

                artist = artists[0]

                # Extract relevant information
                mbid = artist.get("id")
                name = artist.get("name", artist_name)
                
                # Build URLs
                urls = {
                    "musicbrainz": f"https://musicbrainz.org/artist/{mbid}",
                }

                # Add official URLs if available
                if "relations" in artist:
                    for relation in artist["relations"]:
                        if relation.get("type") == "official homepage":
                            urls["official"] = relation.get("url", {}).get("resource", "")

                result = {
                    "mbid": mbid,
                    "name": name,
                    "urls": urls,
                }

                return result

            except httpx.HTTPStatusError as e:
                # 404 or other HTTP errors
                if e.response.status_code == 404:
                    return None
                raise
            except httpx.TimeoutException:
                raise
            except Exception as e:
                raise

    try:
        result = await _retry_with_backoff(_fetch)
        latency_ms = (time.time() - start_time) * 1000

        if result:
            log_provider_call(trace_id, "musicbrainz", latency_ms, success=True)
            return result
        else:
            log_provider_call(trace_id, "musicbrainz", latency_ms, success=False, error="No results found")
            return None

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        error_msg = str(e)
        log_provider_call(trace_id, "musicbrainz", latency_ms, success=False, error=error_msg)
        return None


# Helper to set trace_id for logging
def set_trace_id(trace_id: str) -> None:
    """Set trace ID for provider logging."""
    enrich_musicbrainz._trace_id = trace_id

