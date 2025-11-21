"""Wikipedia full article content provider - extracts rich facts from complete articles."""

import asyncio
import re
from typing import Optional, Dict, Any, List
import httpx

try:
    from ..config import config
    from ..structured_logging import log_provider_call
except ImportError:
    from config import config
    from structured_logging import log_provider_call


async def get_full_wikipedia_article(page_title: str, language: str = "en") -> Optional[Dict[str, Any]]:
    """
    Get FULL Wikipedia article content with rich facts extraction.

    This fetches the complete article text and extracts:
    - Full introduction/summary
    - Infobox data (album details, artist info, etc.)
    - Key sections (Background, Recording, Critical reception, etc.)
    - Chart positions
    - Genre descriptions
    - Awards and certifications

    Args:
        page_title: Wikipedia page title
        language: Language code

    Returns:
        Dictionary with full content and extracted facts
    """
    trace_id = getattr(get_full_wikipedia_article, "_trace_id", "unknown")

    try:
        async with httpx.AsyncClient(timeout=config.ENRICH_REQUEST_TIMEOUT_SECS) as client:
            # Use MediaWiki API to get full page content
            api_url = f"https://{language}.wikipedia.org/w/api.php"

            params = {
                "action": "query",
                "prop": "extracts|pageprops|categories",
                "titles": page_title,
                "explaintext": "1",  # Get plain text (no HTML)
                "exintro": "0",  # Get full article, not just intro
                "format": "json",
                "redirects": "1",  # Follow redirects
            }

            response = await client.get(api_url, params=params)
            response.raise_for_status()
            data = response.json()

            pages = data.get("query", {}).get("pages", {})
            if not pages:
                return None

            # Get the first (and only) page
            page = next(iter(pages.values()))

            if page.get("missing"):
                return None

            full_text = page.get("extract", "")
            title = page.get("title", page_title)
            page_id = page.get("pageid")

            if not full_text:
                return None

            # Extract categories (for genre detection)
            categories = []
            for cat in page.get("categories", []):
                cat_title = cat.get("title", "").replace("Category:", "")
                categories.append(cat_title)

            # Parse the article into sections
            sections = _parse_article_sections(full_text)

            # Extract rich facts from the content
            facts = _extract_facts_from_article(full_text, sections, title, categories)

            # Get page URL
            page_url = f"https://{language}.wikipedia.org/wiki/{page_title.replace(' ', '_')}"

            result = {
                "title": title,
                "page_id": page_id,
                "url": page_url,
                "full_text": full_text,
                "sections": sections,
                "categories": categories,
                "facts": facts,
                "language": language,
            }

            log_provider_call(trace_id, "wikipedia_full", response.elapsed.total_seconds() * 1000, success=True)
            return result

    except Exception as e:
        log_provider_call(trace_id, "wikipedia_full", 0, success=False, error=str(e))
        return None


def _parse_article_sections(full_text: str) -> Dict[str, str]:
    """
    Parse Wikipedia article into sections.

    Args:
        full_text: Full article text

    Returns:
        Dictionary mapping section names to content
    """
    sections = {}

    # Split by section headers (== Section ==)
    # Wikipedia plaintext format uses == for headers
    current_section = "introduction"
    current_content = []

    lines = full_text.split("\n")

    for line in lines:
        # Check if this is a section header
        if line.strip().startswith("==") and line.strip().endswith("=="):
            # Save previous section
            if current_content:
                sections[current_section] = "\n".join(current_content).strip()

            # Start new section
            section_name = line.strip().strip("=").strip().lower()
            current_section = section_name
            current_content = []
        else:
            current_content.append(line)

    # Save last section
    if current_content:
        sections[current_section] = "\n".join(current_content).strip()

    return sections


def _extract_facts_from_article(
    full_text: str,
    sections: Dict[str, str],
    title: str,
    categories: List[str]
) -> List[str]:
    """
    Extract rich facts from Wikipedia article.

    This extracts meaningful information like:
    - Genre and style descriptions
    - Critical reception
    - Chart performance
    - Production details
    - Historical context
    - Awards and achievements

    Args:
        full_text: Full article text
        sections: Parsed sections
        title: Article title
        categories: Article categories

    Returns:
        List of extracted facts
    """
    facts = []

    # Extract introduction (first paragraph before any section headers)
    intro = sections.get("introduction", "")
    if intro:
        # Get first 2-3 sentences as overview
        sentences = intro.split(". ")
        if len(sentences) >= 2:
            overview = ". ".join(sentences[:3]) + "."
            facts.append(overview)

    # Extract from key sections
    key_sections = {
        "background": ["background", "history", "formation", "early life"],
        "recording": ["recording", "production", "writing and recording"],
        "composition": ["composition", "music and lyrics", "musical style"],
        "reception": ["critical reception", "reception", "commercial performance"],
        "chart_performance": ["chart performance", "commercial performance", "charts"],
        "legacy": ["legacy", "influence", "impact"],
        "awards": ["awards", "accolades", "certifications"],
    }

    for category, possible_names in key_sections.items():
        for section_name in possible_names:
            if section_name in sections:
                section_content = sections[section_name]
                # Extract first 2 sentences from this section
                sentences = section_content.split(". ")
                if sentences:
                    fact = ". ".join(sentences[:2]) + "."
                    if len(fact) > 50:  # Only include substantial facts
                        facts.append(fact)
                break  # Found this category, move to next

    # Extract genre information from categories
    genre_facts = _extract_genre_info(categories)
    if genre_facts:
        facts.extend(genre_facts)

    # Extract chart positions
    chart_facts = _extract_chart_info(full_text)
    if chart_facts:
        facts.extend(chart_facts)

    # Extract notable singles/tracks if mentioned
    track_facts = _extract_track_info(full_text, sections)
    if track_facts:
        facts.extend(track_facts)

    return facts


def _extract_genre_info(categories: List[str]) -> List[str]:
    """Extract genre information from categories."""
    genre_facts = []

    genre_keywords = [
        "hip hop", "rap", "rock", "pop", "jazz", "electronic",
        "r&b", "soul", "country", "metal", "punk", "indie",
        "alternative", "folk", "blues", "reggae", "classical"
    ]

    found_genres = []
    for cat in categories:
        cat_lower = cat.lower()
        for genre in genre_keywords:
            if genre in cat_lower and "albums" in cat_lower:
                found_genres.append(genre)

    if found_genres:
        unique_genres = list(set(found_genres))
        genre_facts.append(f"Musical genres: {', '.join(unique_genres)}")

    return genre_facts


def _extract_chart_info(full_text: str) -> List[str]:
    """Extract chart performance information."""
    chart_facts = []

    # Look for Billboard Hot 100 mentions
    billboard_pattern = r"(?:peaked|reached|debuted|charted) at (?:number|#)?\s*(\d+)\s+(?:on the )?Billboard (?:Hot 100|200)"
    matches = re.findall(billboard_pattern, full_text, re.IGNORECASE)

    if matches:
        positions = [int(m) for m in matches if m.isdigit()]
        if positions:
            best_position = min(positions)
            chart_facts.append(f"Peaked at #{best_position} on the Billboard charts")

    # Look for "number one" or "#1" mentions
    number_one_pattern = r"(?:reached|debuted at|became|topped|number one|#1)(?:[^.]*?)(?:in|on|across)\s+(\w+(?:\s+\w+)?)"
    if "number one" in full_text.lower() or "#1" in full_text:
        chart_facts.append("Achieved #1 chart position")

    return chart_facts


def _extract_track_info(full_text: str, sections: Dict[str, str]) -> List[str]:
    """Extract information about notable tracks/singles."""
    track_facts = []

    # Look for singles section
    singles_section = None
    for section_name in ["singles", "track listing", "tracks", "songs"]:
        if section_name in sections:
            singles_section = sections[section_name]
            break

    if singles_section:
        # Extract quoted song titles (typically in quotes)
        quoted_titles = re.findall(r'"([^"]+)"', singles_section)
        if quoted_titles:
            notable_tracks = quoted_titles[:3]  # First 3 singles
            if notable_tracks:
                tracks_formatted = ', '.join(f'"{t}"' for t in notable_tracks)
                track_facts.append(f"Notable tracks include: {tracks_formatted}")

    return track_facts


async def get_related_articles(
    main_article_title: str,
    entity_type: str = "artist",
    language: str = "en"
) -> List[Dict[str, Any]]:
    """
    Get related Wikipedia articles for comprehensive enrichment.

    For an artist query about their latest album, this fetches:
    - Artist article (biography, career)
    - Album article (details, reception)
    - Genre articles (musical context)

    Args:
        main_article_title: Main article title (e.g., "Eminem")
        entity_type: Type of entity (artist, album, track)
        language: Language code

    Returns:
        List of related article data
    """
    related = []

    # Get main article
    main_article = await get_full_wikipedia_article(main_article_title, language)
    if main_article:
        related.append({
            "type": "main",
            "entity_type": entity_type,
            "data": main_article
        })

    # TODO: In future, we can fetch:
    # - Album articles via Wikidata links
    # - Genre articles from categories
    # - Related artist articles

    return related


# Helper to set trace_id for logging
def set_trace_id(trace_id: str) -> None:
    """Set trace ID for provider logging."""
    get_full_wikipedia_article._trace_id = trace_id
    get_related_articles._trace_id = trace_id
