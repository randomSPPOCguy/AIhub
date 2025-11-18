"""Wikipedia provider for enrichment."""

import asyncio
import random
import time
import urllib.parse
from typing import Optional, Dict, Any
import httpx

try:
    from ..config import config
    from ..structured_logging import log_provider_call
except ImportError:
    from config import config
    from structured_logging import log_provider_call


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


async def enrich_wikipedia(subject: str, language: str = "en") -> Optional[Dict[str, Any]]:
    """
    Enrich subject using Wikipedia.

    Args:
        subject: Subject name to search for
        language: Language code (e.g., "en", "es")

    Returns:
        Dictionary with summary, url, title, or None on failure
    """
    start_time = time.time()
    trace_id = getattr(enrich_wikipedia, "_trace_id", "unknown")

    async def _fetch():
        """Internal fetch function for retry logic."""
        async with httpx.AsyncClient(timeout=config.ENRICH_REQUEST_TIMEOUT_SECS) as client:
            # Wikipedia REST API: get page summary
            # URL-encode the subject title
            encoded_subject = urllib.parse.quote(subject.replace(' ', '_'))
            search_url = f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{encoded_subject}"
            
            try:
                response = await client.get(search_url)
                response.raise_for_status()
                data = response.json()

                # Extract relevant information
                result = {
                    "summary": data.get("extract", ""),
                    "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                    "title": data.get("title", subject),
                }

                # Validate we got useful data
                if result["summary"] and result["url"]:
                    return result
                return None

            except httpx.HTTPStatusError as e:
                # 404 is acceptable (page not found)
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
            log_provider_call(trace_id, "wikipedia", latency_ms, success=True)
            return result
        else:
            log_provider_call(trace_id, "wikipedia", latency_ms, success=False, error="No results found")
            return None

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        error_msg = str(e)
        log_provider_call(trace_id, "wikipedia", latency_ms, success=False, error=error_msg)
        return None


# Helper to set trace_id for logging
def set_trace_id(trace_id: str) -> None:
    """Set trace ID for provider logging."""
    enrich_wikipedia._trace_id = trace_id

