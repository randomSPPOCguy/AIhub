"""Enhanced Wikipedia provider with structured data extraction."""

import asyncio
import random
import time
import re
from typing import Optional, Dict, Any, List
import httpx

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config import config
    from structured_logging import log_provider_call
except ImportError:
    import config as config_module
    import structured_logging as logging_module
    config = config_module
    log_provider_call = logging_module.log_provider_call


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


async def get_wikipedia_page(page_title: str, language: str = "en") -> Optional[Dict[str, Any]]:
    """
    Get Wikipedia page content with structured data extraction.

    This uses the Wikipedia REST API to get the page summary and full HTML
    to extract structured information like discography.

    Args:
        page_title: Wikipedia page title (can be from Wikidata)
        language: Language code

    Returns:
        Dictionary with summary, sections, infobox data, etc.
    """
    start_time = time.time()
    trace_id = getattr(get_wikipedia_page, "_trace_id", "unknown")

    async def _fetch():
        async with httpx.AsyncClient(timeout=config.ENRICH_REQUEST_TIMEOUT_SECS) as client:
            # URL encode the page title
            encoded_title = page_title.replace(' ', '_')

            # Get page summary (quick overview)
            summary_url = f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"

            try:
                summary_response = await client.get(summary_url)
                summary_response.raise_for_status()
                summary_data = summary_response.json()

                # Extract basic info
                extract = summary_data.get("extract", "")
                url = summary_data.get("content_urls", {}).get("desktop", {}).get("page", "")
                title = summary_data.get("title", page_title)
                thumbnail = summary_data.get("thumbnail", {}).get("source", "")

                # Get page sections (for discography, etc.)
                # Use MediaWiki API to get sections
                sections_url = f"https://{language}.wikipedia.org/w/api.php"
                sections_params = {
                    "action": "parse",
                    "page": page_title,
                    "prop": "sections",
                    "format": "json",
                }

                sections_response = await client.get(sections_url, params=sections_params)
                sections_response.raise_for_status()
                sections_data = sections_response.json()

                # Extract section names and indices
                sections = []
                parse_data = sections_data.get("parse", {})
                for section in parse_data.get("sections", []):
                    sections.append({
                        "index": section.get("index"),
                        "level": section.get("level"),
                        "title": section.get("line"),
                        "anchor": section.get("anchor"),
                    })

                # Find discography section if it exists
                discography_section = None
                for section in sections:
                    section_title_lower = section.get("title", "").lower()
                    if "discography" in section_title_lower or "albums" in section_title_lower:
                        discography_section = section
                        break

                result = {
                    "title": title,
                    "summary": extract,
                    "url": url,
                    "thumbnail": thumbnail,
                    "sections": sections,
                    "has_discography": discography_section is not None,
                    "discography_section": discography_section,
                }

                return result

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return None
                raise

    try:
        result = await _retry_with_backoff(_fetch)
        latency_ms = (time.time() - start_time) * 1000

        if result:
            log_provider_call(trace_id, "wikipedia_enhanced", latency_ms, success=True)
            return result
        else:
            log_provider_call(
                trace_id, "wikipedia_enhanced", latency_ms, success=False, error="No results found"
            )
            return None

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        error_msg = str(e)
        log_provider_call(trace_id, "wikipedia_enhanced", latency_ms, success=False, error=error_msg)
        return None


async def get_discography_from_section(page_title: str, section_index: str, language: str = "en") -> Optional[List[Dict[str, Any]]]:
    """
    Extract discography data from a specific Wikipedia section.

    Args:
        page_title: Wikipedia page title
        section_index: Section index (from sections list)
        language: Language code

    Returns:
        List of albums with titles and years
    """
    start_time = time.time()
    trace_id = getattr(get_discography_from_section, "_trace_id", "unknown")

    async def _fetch():
        async with httpx.AsyncClient(timeout=config.ENRICH_REQUEST_TIMEOUT_SECS) as client:
            # Get section HTML
            url = f"https://{language}.wikipedia.org/w/api.php"
            params = {
                "action": "parse",
                "page": page_title,
                "section": section_index,
                "prop": "text",
                "format": "json",
            }

            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            html = data.get("parse", {}).get("text", {}).get("*", "")

            if not html:
                return None

            # Parse HTML for album titles and years (simple regex-based extraction)
            # This is a simplified parser - a full implementation would use BeautifulSoup
            albums = []

            # Look for patterns like:
            # - "Album Name (2020)"
            # - "Album Name" - 2020
            # - List items with years
            album_patterns = [
                r'<i>(.*?)</i>.*?\((\d{4})\)',  # Italic title with year
                r'"(.*?)".*?\((\d{4})\)',  # Quoted title with year
                r'<b>(.*?)</b>.*?\((\d{4})\)',  # Bold title with year
            ]

            for pattern in album_patterns:
                matches = re.findall(pattern, html)
                for title, year in matches:
                    # Clean HTML tags
                    title = re.sub(r'<[^>]+>', '', title).strip()
                    if title and len(title) > 1 and len(title) < 100:
                        albums.append({
                            "title": title,
                            "year": year,
                        })

            # Remove duplicates
            seen = set()
            unique_albums = []
            for album in albums:
                key = (album["title"].lower(), album["year"])
                if key not in seen:
                    seen.add(key)
                    unique_albums.append(album)

            return unique_albums if unique_albums else None

    try:
        result = await _retry_with_backoff(_fetch)
        latency_ms = (time.time() - start_time) * 1000

        if result:
            log_provider_call(trace_id, "wikipedia_discography", latency_ms, success=True)
            return result
        else:
            log_provider_call(
                trace_id, "wikipedia_discography", latency_ms, success=False, error="No albums found"
            )
            return None

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        error_msg = str(e)
        log_provider_call(trace_id, "wikipedia_discography", latency_ms, success=False, error=error_msg)
        return None


# Helper to set trace_id for logging
def set_trace_id(trace_id: str) -> None:
    """Set trace ID for provider logging."""
    get_wikipedia_page._trace_id = trace_id
    get_discography_from_section._trace_id = trace_id
