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


# Music-related markers in Wikipedia URLs/titles
MUSIC_MARKERS = [
    "(band)", "(artist)", "(singer)", "(musician)", "(group)",
    "(rapper)", "(composer)", "(producer)", "(dj)",
    "(album)", "(song)", "(ep)", "(single)",
    "(record_producer)", "(musical_artist)", "(music_group)"
]


def is_music_related_wikipedia(url_or_title: str) -> bool:
    """
    Check if Wikipedia URL or title is music-related.

    Args:
        url_or_title: Wikipedia URL or page title

    Returns:
        True if music-related, False otherwise
    """
    text_lower = url_or_title.lower()
    return any(marker in text_lower for marker in MUSIC_MARKERS)


def is_disambiguation_page(title: str, summary: str, url: str = "") -> bool:
    """
    Check if Wikipedia page is a disambiguation page.

    Args:
        title: Page title
        summary: Page summary/extract
        url: Page URL (optional)

    Returns:
        True if disambiguation page, False otherwise
    """
    title_lower = title.lower()
    summary_lower = summary.lower()

    # Check title
    if "disambiguation" in title_lower:
        return True

    # Check summary for disambiguation markers
    disambiguation_markers = [
        "may refer to",
        "may also refer to",
        "can refer to",
        "disambiguation page",
        "disambiguation)",
        "other uses, see",
    ]

    for marker in disambiguation_markers:
        if marker in summary_lower:
            return True

    return False


def extract_disambiguation_options(title: str, summary: str) -> List[Dict[str, Any]]:
    """
    Extract disambiguation options from Wikipedia disambiguation page.

    Args:
        title: Page title
        summary: Page summary text

    Returns:
        List of disambiguation options with labels, paths, and keywords
    """
    options = []

    # Parse summary for options
    # Typically in format: "X may refer to: \n* Option 1 (description)\n* Option 2 (description)"
    lines = summary.split('\n')

    for line in lines:
        line = line.strip()
        if not line or len(line) < 5:
            continue

        # Skip the main "may refer to" line
        if "may refer to" in line.lower() or "can refer to" in line.lower():
            continue

        # Look for list items or comma-separated options
        # Example: "Poe (singer), American musician"
        # Example: "Edgar Allan Poe (1809–1849), American writer"

        # Extract text in parentheses
        import re
        parentheses_match = re.search(r'\(([^)]+)\)', line)

        label = line.split(',')[0].strip() if ',' in line else line

        # Determine if music-related
        is_music = False
        keywords = []
        path = "other"

        if parentheses_match:
            paren_text = parentheses_match.group(1).lower()

            # Check for music markers
            for marker in MUSIC_MARKERS:
                marker_clean = marker.strip('()')
                if marker_clean in paren_text:
                    is_music = True
                    path = "music"
                    keywords.append("music")
                    keywords.append(marker_clean)
                    break

        # Check line content for music keywords
        line_lower = line.lower()
        music_keywords = ["singer", "musician", "band", "artist", "rapper", "composer", "album", "song"]
        for kw in music_keywords:
            if kw in line_lower:
                is_music = True
                path = "music"
                if kw not in keywords:
                    keywords.append(kw)

        # Check for historical/literary markers
        historical_keywords = ["writer", "author", "poet", "president", "politician", "historical"]
        for kw in historical_keywords:
            if kw in line_lower:
                if path == "other":  # Don't override music
                    path = "historical"
                if kw not in keywords:
                    keywords.append(kw)

        # Create Wikipedia title from label
        wikipedia_title = label.strip()

        options.append({
            "label": label,
            "path": path,
            "wikipedia_title": wikipedia_title,
            "keywords": keywords,
            "is_music": is_music,
            "raw_text": line
        })

    # Sort: music options first
    options.sort(key=lambda x: (not x["is_music"], x["label"]))

    return options


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

                # Check if this is a disambiguation page
                is_disambig = is_disambiguation_page(title, extract, url)

                result = {
                    "title": title,
                    "summary": extract,
                    "url": url,
                    "thumbnail": thumbnail,
                    "sections": sections,
                    "has_discography": discography_section is not None,
                    "discography_section": discography_section,
                    "is_disambiguation": is_disambig,
                    "is_music_related": is_music_related_wikipedia(url) if url else is_music_related_wikipedia(title),
                }

                # If disambiguation, extract options
                if is_disambig:
                    options = extract_disambiguation_options(title, extract)
                    result["disambiguation_options"] = options

                    # Filter for music options
                    music_options = [opt for opt in options if opt["is_music"]]
                    result["has_music_options"] = len(music_options) > 0
                    result["music_options"] = music_options

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
