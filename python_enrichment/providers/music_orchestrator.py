"""Music enrichment orchestrator using MusicBrainz → Wikidata → Wikipedia pipeline."""

import asyncio
from typing import Optional, Dict, Any, List

try:
    from .musicbrainz_enhanced import get_artist_with_wikidata, get_wikidata_info
    from .wikipedia_enhanced import get_wikipedia_page, get_discography_from_section
except ImportError:
    from musicbrainz_enhanced import get_artist_with_wikidata, get_wikidata_info
    from wikipedia_enhanced import get_wikipedia_page, get_discography_from_section


async def enrich_artist_complete(artist_name: str, trace_id: str = "unknown") -> Optional[Dict[str, Any]]:
    """
    Complete artist enrichment using the full pipeline:
    MusicBrainz → Wikidata → Wikipedia → Discography

    This is the KEY function you asked for!

    Args:
        artist_name: Artist name to enrich
        trace_id: Trace ID for logging

    Returns:
        Comprehensive artist data including:
        - Basic info (name, MBID, Wikidata ID)
        - Wikipedia summary and URL
        - Albums from MusicBrainz
        - Discography from Wikipedia (if available)
        - All relevant URLs
        - Facts extracted from multiple sources
    """
    # Set trace IDs for all providers
    from . import musicbrainz_enhanced, wikipedia_enhanced
    musicbrainz_enhanced.set_trace_id(trace_id)
    wikipedia_enhanced.set_trace_id(trace_id)

    # Step 1: Get artist from MusicBrainz (includes Wikidata ID and albums)
    mb_data = await get_artist_with_wikidata(artist_name)

    if not mb_data:
        return None

    # Initialize result with MusicBrainz data
    result = {
        "mbid": mb_data.get("mbid"),
        "name": mb_data.get("name"),
        "wikidata_id": mb_data.get("wikidata_id"),
        "urls": mb_data.get("urls", {}),
        "albums_from_mb": mb_data.get("albums", []),
        "album_count": mb_data.get("album_count", 0),
        "facts": [],
        "sources": [],
    }

    # Step 2: Get Wikipedia data
    wikipedia_url = mb_data.get("wikipedia_url")
    wikipedia_title = None

    if wikipedia_url:
        # Extract title from URL
        wikipedia_title = wikipedia_url.split("/wiki/")[-1].replace("_", " ")
    elif mb_data.get("wikidata_id"):
        # If no direct Wikipedia URL, get it from Wikidata
        wikidata_info = await get_wikidata_info(mb_data["wikidata_id"])
        if wikidata_info:
            wikipedia_title = wikidata_info.get("wikipedia_title")
            result["urls"]["wikipedia"] = wikidata_info.get("wikipedia_url")

    # Step 3: Get Wikipedia page content
    wikipedia_data = None
    if wikipedia_title:
        wikipedia_data = await get_wikipedia_page(wikipedia_title)

    if wikipedia_data:
        # Add Wikipedia summary as a fact
        summary = wikipedia_data.get("summary", "")
        if summary:
            result["facts"].append(summary)
            result["sources"].append({
                "provider": "wikipedia",
                "url": wikipedia_data.get("url", ""),
                "title": wikipedia_data.get("title", ""),
                "section": "Summary",
            })

        # Check if there's a discography section
        if wikipedia_data.get("has_discography"):
            discography_section = wikipedia_data.get("discography_section")
            if discography_section:
                # Extract albums from Wikipedia discography section
                wikipedia_albums = await get_discography_from_section(
                    wikipedia_title,
                    discography_section.get("index"),
                )

                if wikipedia_albums:
                    result["albums_from_wikipedia"] = wikipedia_albums

                    # Add discography fact
                    album_titles = [a["title"] for a in wikipedia_albums[:5]]
                    if album_titles:
                        discography_fact = f"Albums include: {', '.join(album_titles)}"
                        if len(wikipedia_albums) > 5:
                            discography_fact += f" and {len(wikipedia_albums) - 5} more"
                        result["facts"].append(discography_fact)

    # Step 4: Add MusicBrainz albums as facts
    if result.get("albums_from_mb"):
        mb_albums = result["albums_from_mb"][:5]
        album_summaries = []
        for album in mb_albums:
            title = album.get("title", "")
            date = album.get("date", "")
            if title:
                if date:
                    album_summaries.append(f"{title} ({date[:4]})")
                else:
                    album_summaries.append(title)

        if album_summaries:
            mb_fact = f"Discography: {', '.join(album_summaries)}"
            if len(result["albums_from_mb"]) > 5:
                mb_fact += f" and {len(result['albums_from_mb']) - 5} more albums"
            result["facts"].append(mb_fact)
            result["sources"].append({
                "provider": "musicbrainz",
                "url": result["urls"].get("musicbrainz", ""),
                "title": result["name"],
                "section": "Discography",
            })

    # Step 5: Add album count fact
    total_albums = result.get("album_count", 0)
    if total_albums > 0:
        result["facts"].append(f"{result['name']} has released {total_albums} studio albums")

    return result


async def enrich_album(album_name: str, artist_name: Optional[str] = None, trace_id: str = "unknown") -> Optional[Dict[str, Any]]:
    """
    Enrich album information using MusicBrainz and Wikipedia.

    Args:
        album_name: Album name
        artist_name: Optional artist name for better matching
        trace_id: Trace ID

    Returns:
        Album data including tracks, release date, etc.
    """
    # TODO: Implement album-specific enrichment
    # This would follow similar pattern:
    # 1. Search MusicBrainz for release
    # 2. Get Wikidata ID
    # 3. Get Wikipedia page
    # 4. Extract track listing
    return None


# Set trace IDs for all providers
def set_trace_id(trace_id: str) -> None:
    """Set trace ID for all providers."""
    from . import musicbrainz_enhanced, wikipedia_enhanced
    musicbrainz_enhanced.set_trace_id(trace_id)
    wikipedia_enhanced.set_trace_id(trace_id)
