"""Enhanced MusicBrainz provider with Wikidata integration and discography."""

import asyncio
import random
import time
from typing import Optional, Dict, Any, List
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
    """Retry function with exponential backoff and jitter."""
    max_retries = max_retries or config.ENRICH_MAX_RETRIES
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                await asyncio.sleep(delay)
            else:
                break

    return None


async def get_artist_with_wikidata(artist_name: str) -> Optional[Dict[str, Any]]:
    """
    Get artist info from MusicBrainz including Wikidata ID and releases.

    This is the KEY function that bridges MusicBrainz → Wikidata → Wikipedia.

    Args:
        artist_name: Artist name to search for

    Returns:
        Dictionary with:
        - mbid: MusicBrainz ID
        - name: Artist name
        - wikidata_id: Wikidata ID (e.g., Q12345)
        - wikipedia_url: Direct Wikipedia URL from Wikidata relation
        - albums: List of albums with release dates
        - urls: Dict of URLs (musicbrainz, official, etc.)
    """
    start_time = time.time()
    trace_id = getattr(get_artist_with_wikidata, "_trace_id", "unknown")

    # Enforce rate limit
    await _rate_limiter.acquire()

    async def _fetch():
        async with httpx.AsyncClient(timeout=config.ENRICH_REQUEST_TIMEOUT_SECS) as client:
            # Step 1: Search for artist
            search_url = "https://musicbrainz.org/ws/2/artist/"
            params = {
                "query": f'artist:"{artist_name}"',
                "fmt": "json",
                "limit": 1,
            }
            headers = {
                "User-Agent": "AIhub-Enrichment/1.0 (https://github.com/aihub)",
            }

            response = await client.get(search_url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

            artists = data.get("artists", [])
            if not artists:
                return None

            artist = artists[0]
            mbid = artist.get("id")

            if not mbid:
                return None

            # Step 2: Get detailed artist info with relations (includes Wikidata)
            # We need to make a second call to get full details
            await _rate_limiter.acquire()  # Rate limit second call

            detail_url = f"https://musicbrainz.org/ws/2/artist/{mbid}"
            detail_params = {
                "fmt": "json",
                "inc": "url-rels+release-groups",  # Get Wikidata link and releases
            }

            detail_response = await client.get(detail_url, params=detail_params, headers=headers)
            detail_response.raise_for_status()
            detail_data = detail_response.json()

            # Extract basic info
            name = detail_data.get("name", artist_name)

            # Extract Wikidata ID and Wikipedia URL from relations
            wikidata_id = None
            wikipedia_url = None
            official_url = None

            for relation in detail_data.get("relations", []):
                rel_type = relation.get("type")
                url_resource = relation.get("url", {}).get("resource", "")

                if rel_type == "wikidata":
                    # Extract Wikidata ID from URL (e.g., https://www.wikidata.org/wiki/Q12345)
                    if "wikidata.org/wiki/" in url_resource:
                        wikidata_id = url_resource.split("/wiki/")[-1]

                elif rel_type == "wikipedia":
                    wikipedia_url = url_resource

                elif rel_type == "official homepage":
                    official_url = url_resource

            # Extract albums/release-groups
            albums = []
            for rg in detail_data.get("release-groups", [])[:10]:  # Limit to 10 albums
                if rg.get("primary-type") == "Album":
                    albums.append({
                        "title": rg.get("title"),
                        "date": rg.get("first-release-date", ""),
                        "type": rg.get("primary-type"),
                        "mbid": rg.get("id"),
                    })

            # Build URLs
            urls = {
                "musicbrainz": f"https://musicbrainz.org/artist/{mbid}",
            }
            if wikidata_id:
                urls["wikidata"] = f"https://www.wikidata.org/wiki/{wikidata_id}"
            if wikipedia_url:
                urls["wikipedia"] = wikipedia_url
            if official_url:
                urls["official"] = official_url

            result = {
                "mbid": mbid,
                "name": name,
                "wikidata_id": wikidata_id,
                "wikipedia_url": wikipedia_url,
                "albums": albums,
                "album_count": len(albums),
                "urls": urls,
            }

            return result

    try:
        result = await _retry_with_backoff(_fetch)
        latency_ms = (time.time() - start_time) * 1000

        if result:
            log_provider_call(trace_id, "musicbrainz_enhanced", latency_ms, success=True)
            return result
        else:
            log_provider_call(
                trace_id, "musicbrainz_enhanced", latency_ms, success=False, error="No results found"
            )
            return None

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        error_msg = str(e)
        log_provider_call(trace_id, "musicbrainz_enhanced", latency_ms, success=False, error=error_msg)
        return None


async def get_wikidata_info(wikidata_id: str) -> Optional[Dict[str, Any]]:
    """
    Get info from Wikidata including Wikipedia page link.

    Args:
        wikidata_id: Wikidata ID (e.g., Q12345)

    Returns:
        Dictionary with Wikipedia page title, URL, and other info
    """
    start_time = time.time()
    trace_id = getattr(get_wikidata_info, "_trace_id", "unknown")

    async def _fetch():
        async with httpx.AsyncClient(timeout=config.ENRICH_REQUEST_TIMEOUT_SECS) as client:
            # Wikidata API to get entity info
            url = "https://www.wikidata.org/w/api.php"
            params = {
                "action": "wbgetentities",
                "ids": wikidata_id,
                "format": "json",
                "props": "sitelinks|labels|descriptions",
            }

            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            entity = data.get("entities", {}).get(wikidata_id)
            if not entity:
                return None

            # Get Wikipedia sitelinks (English Wikipedia)
            sitelinks = entity.get("sitelinks", {})
            enwiki = sitelinks.get("enwiki", {})

            if not enwiki:
                return None

            wikipedia_title = enwiki.get("title", "")
            wikipedia_url = enwiki.get("url", f"https://en.wikipedia.org/wiki/{wikipedia_title.replace(' ', '_')}")

            # Get label and description
            labels = entity.get("labels", {})
            descriptions = entity.get("descriptions", {})

            label = labels.get("en", {}).get("value", "")
            description = descriptions.get("en", {}).get("value", "")

            return {
                "wikidata_id": wikidata_id,
                "label": label,
                "description": description,
                "wikipedia_title": wikipedia_title,
                "wikipedia_url": wikipedia_url,
            }

    try:
        result = await _retry_with_backoff(_fetch)
        latency_ms = (time.time() - start_time) * 1000

        if result:
            log_provider_call(trace_id, "wikidata", latency_ms, success=True)
            return result
        else:
            log_provider_call(trace_id, "wikidata", latency_ms, success=False, error="No results found")
            return None

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        error_msg = str(e)
        log_provider_call(trace_id, "wikidata", latency_ms, success=False, error=error_msg)
        return None


# Helper to set trace_id for logging
def set_trace_id(trace_id: str) -> None:
    """Set trace ID for provider logging."""
    get_artist_with_wikidata._trace_id = trace_id
    get_wikidata_info._trace_id = trace_id
