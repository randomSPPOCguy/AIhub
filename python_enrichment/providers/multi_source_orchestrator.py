"""
Multi-source orchestrator - Context-aware enrichment using multiple APIs.

Flow:
1. MusicBrainz FIRST - Get canonical MBID and all IDs (Wikidata, Discogs, Spotify, etc.)
2. Use MBID/Wikidata → Get exact Wikipedia page
3. Use other IDs → Enrich from Discogs, Last.fm, Genius, etc.
4. Combine all data into comprehensive result

Context-aware:
- Artist query → Full artist profile with discography
- Album query → Album details with tracklist
- Track query → Track info with lyrics and credits
"""

import asyncio
from typing import Optional, Dict, Any, List

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from providers.musicbrainz_complete import search_artist, search_release, search_recording
    from providers.wikipedia_enhanced import get_wikipedia_page
    from structured_logging import log_provider_call
except ImportError:
    from musicbrainz_complete import search_artist, search_release, search_recording
    from wikipedia_enhanced import get_wikipedia_page
    import structured_logging
    log_provider_call = structured_logging.log_provider_call


async def enrich_artist_multi_source(
    artist_name: str,
    trace_id: str = "unknown"
) -> Optional[Dict[str, Any]]:
    """
    Complete artist enrichment from multiple sources.

    Sources used:
    1. MusicBrainz - Canonical data, IDs, discography
    2. Wikipedia - Biography, summary, detailed discography
    3. Wikidata - Cross-links (auto-included via MB)
    4. [Future] Last.fm - Tags, similar artists, play counts
    5. [Future] Discogs - Detailed release info, marketplace data

    Args:
        artist_name: Artist name
        trace_id: Trace ID

    Returns:
        Comprehensive artist profile
    """
    try:
        from providers import musicbrainz_complete, wikipedia_enhanced
    except ImportError:
        import musicbrainz_complete, wikipedia_enhanced
    musicbrainz_complete.set_trace_id(trace_id)
    wikipedia_enhanced.set_trace_id(trace_id)

    # Step 1: MusicBrainz - PRIMARY SOURCE (canonical data)
    mb_data = await search_artist(artist_name)
    if not mb_data:
        return None

    result = {
        "type": "artist",
        "name": mb_data["name"],
        "mbid": mb_data["mbid"],
        "ids": mb_data["ids"],
        "urls": mb_data["urls"],
        "context": "artist",
        "facts": [],
        "sources": [],
    }

    # Add basic facts from MusicBrainz
    facts = []

    # Fact: Artist type and active years
    type_name = mb_data.get("type_name", "")
    active_years = mb_data.get("active_years", "")
    if type_name and active_years:
        facts.append(f"{mb_data['name']} is a {type_name.lower()} active from {active_years}")
    elif type_name:
        facts.append(f"{mb_data['name']} is a {type_name.lower()}")

    # Fact: Country
    if mb_data.get("country"):
        facts.append(f"From {mb_data['country']}")

    # Fact: Genres
    if mb_data.get("genres"):
        genres_str = ", ".join(mb_data["genres"][:5])
        facts.append(f"Genres: {genres_str}")

    # Fact: Discography summary
    album_count = mb_data.get("album_count", 0)
    if album_count > 0:
        facts.append(f"Released {album_count} studio albums")

        # Add album titles (NEWEST FIRST - sorted by date descending)
        albums = mb_data.get("albums", [])[:10]  # Show top 10 recent albums
        if albums:
            # Highlight the LATEST album prominently
            latest_album = albums[0]
            latest_title = latest_album["title"]
            latest_year = latest_album["year"]
            if latest_year:
                facts.append(f"Latest album: {latest_title} ({latest_year})")
            else:
                facts.append(f"Latest album: {latest_title}")

            # List recent albums
            if len(albums) > 1:
                album_list = []
                for album in albums[1:6]:  # Next 5 recent albums
                    title = album["title"]
                    year = album["year"]
                    if year:
                        album_list.append(f"{title} ({year})")
                    else:
                        album_list.append(title)

                album_str = ", ".join(album_list)
                if album_count > 6:
                    album_str += f" and {album_count - 6} more"
                facts.append(f"Recent albums: {album_str}")

    result["facts"].extend(facts)
    result["sources"].append({
        "provider": "musicbrainz",
        "url": mb_data["urls"].get("musicbrainz", ""),
        "sections": ["discography", "metadata", "relationships"]
    })

    # Step 2: Wikipedia - Get detailed biography
    wikipedia_title = mb_data.get("wikipedia_title")
    if wikipedia_title:
        wiki_data = await get_wikipedia_page(wikipedia_title)
        if wiki_data:
            # Add Wikipedia summary
            summary = wiki_data.get("summary", "")
            if summary and summary not in facts:
                result["facts"].insert(0, summary)  # Put bio first
                result["sources"].append({
                    "provider": "wikipedia",
                    "url": wiki_data.get("url", ""),
                    "sections": ["summary"]
                })

            # Note if discography section exists
            if wiki_data.get("has_discography"):
                discog_section = wiki_data.get("discography_section", {})
                result["sources"][-1]["sections"].append(f"discography ({discog_section.get('title', 'Discography')})")

    # Step 3: Additional metadata from MusicBrainz
    result["metadata"] = {
        "total_releases": mb_data.get("total_releases", 0),
        "albums": mb_data.get("album_count", 0),
        "singles": mb_data.get("single_count", 0),
        "eps": mb_data.get("ep_count", 0),
        "genres": mb_data.get("genres", []),
        "tags": mb_data.get("tags", []),
    }

    # Include full discography
    result["discography"] = {
        "albums": mb_data.get("albums", []),
        "singles": mb_data.get("singles", []),
        "eps": mb_data.get("eps", []),
    }

    # Step 4: [Future] Last.fm enrichment
    # if mb_data["ids"].get("lastfm"):
    #     lastfm_data = await get_lastfm_artist(mb_data["ids"]["lastfm"])
    #     if lastfm_data:
    #         result["metadata"]["play_count"] = lastfm_data.get("playcount")
    #         result["metadata"]["listeners"] = lastfm_data.get("listeners")
    #         result["metadata"]["similar_artists"] = lastfm_data.get("similar", [])

    return result


async def enrich_album_multi_source(
    album_title: str,
    artist_name: Optional[str] = None,
    trace_id: str = "unknown"
) -> Optional[Dict[str, Any]]:
    """
    Complete album enrichment from multiple sources.

    Sources:
    1. MusicBrainz - Tracklist, release date, label, catalog number
    2. Wikipedia - Album info, critical reception, chart positions
    3. Discogs - Detailed credits, marketplace data
    4. AllMusic - Reviews, ratings

    Args:
        album_title: Album title
        artist_name: Artist name (improves matching)
        trace_id: Trace ID

    Returns:
        Comprehensive album data
    """
    try:
        from providers import musicbrainz_complete, wikipedia_enhanced
    except ImportError:
        import musicbrainz_complete, wikipedia_enhanced
    musicbrainz_complete.set_trace_id(trace_id)
    wikipedia_enhanced.set_trace_id(trace_id)

    # Step 1: MusicBrainz - PRIMARY SOURCE
    mb_data = await search_release(album_title, artist_name)
    if not mb_data:
        return None

    result = {
        "type": "album",
        "title": mb_data["title"],
        "artist": mb_data["artist"],
        "mbid": mb_data["mbid"],
        "artist_mbid": mb_data.get("artist_mbid"),
        "ids": mb_data["ids"],
        "urls": mb_data["urls"],
        "context": "album",
        "facts": [],
        "sources": [],
    }

    # Add facts from MusicBrainz
    facts = []

    # Fact: Release info
    date = mb_data.get("date", "")
    if date:
        facts.append(f"Released on {date}")

    # Fact: Label
    labels = mb_data.get("labels", [])
    if labels:
        label_names = [l["name"] for l in labels if l.get("name")]
        if label_names:
            facts.append(f"Released by {', '.join(label_names)}")

    # Fact: Track count and length
    track_count = mb_data.get("total_tracks", 0)
    total_length = mb_data.get("total_length", "")
    if track_count and total_length:
        facts.append(f"{track_count} tracks, total length {total_length}")
    elif track_count:
        facts.append(f"{track_count} tracks")

    # Fact: Genres
    genres = mb_data.get("genres", [])
    if genres:
        facts.append(f"Genres: {', '.join(genres)}")

    result["facts"].extend(facts)
    result["sources"].append({
        "provider": "musicbrainz",
        "url": mb_data["urls"].get("musicbrainz", ""),
        "sections": ["tracklist", "release_info", "metadata"]
    })

    # Step 2: Wikipedia - Album article
    if mb_data["urls"].get("wikipedia"):
        wiki_url = mb_data["urls"]["wikipedia"]
        if "/wiki/" in wiki_url:
            wiki_title = wiki_url.split("/wiki/")[-1].replace("_", " ")
            wiki_data = await get_wikipedia_page(wiki_title)
            if wiki_data:
                summary = wiki_data.get("summary", "")
                if summary:
                    result["facts"].insert(0, summary)
                    result["sources"].append({
                        "provider": "wikipedia",
                        "url": wiki_url,
                        "sections": ["summary", "critical_reception"]
                    })

    # Include full tracklist
    result["tracklist"] = mb_data.get("tracks", [])
    result["metadata"] = {
        "date": mb_data.get("date"),
        "year": mb_data.get("year"),
        "country": mb_data.get("country"),
        "barcode": mb_data.get("barcode"),
        "labels": mb_data.get("labels", []),
        "genres": mb_data.get("genres", []),
        "total_tracks": track_count,
        "total_length": total_length,
        "total_length_ms": mb_data.get("total_length_ms", 0),
    }

    return result


async def enrich_track_multi_source(
    track_title: str,
    artist_name: Optional[str] = None,
    trace_id: str = "unknown"
) -> Optional[Dict[str, Any]]:
    """
    Complete track enrichment from multiple sources.

    Sources:
    1. MusicBrainz - Length, ISRC, releases it appears on
    2. Genius - Lyrics, annotations
    3. Wikipedia - Song article (if notable)

    Args:
        track_title: Track title
        artist_name: Artist name
        trace_id: Trace ID

    Returns:
        Comprehensive track data
    """
    try:
        from providers import musicbrainz_complete
    except ImportError:
        import musicbrainz_complete
    musicbrainz_complete.set_trace_id(trace_id)

    # Step 1: MusicBrainz
    mb_data = await search_recording(track_title, artist_name)
    if not mb_data:
        return None

    result = {
        "type": "track",
        "title": mb_data["title"],
        "artist": mb_data["artist"],
        "mbid": mb_data["mbid"],
        "ids": mb_data["ids"],
        "urls": mb_data["urls"],
        "context": "track",
        "facts": [],
        "sources": [],
    }

    # Add facts
    facts = []

    # Fact: Length
    length = mb_data.get("length", "")
    if length:
        facts.append(f"Duration: {length}")

    # Fact: Appears on albums
    releases = mb_data.get("releases", [])
    if releases:
        release_list = [f"{r['title']}" + (f" ({r['date'][:4]})" if r.get('date') else "") for r in releases[:3]]
        release_str = ", ".join(release_list)
        if len(releases) > 3:
            release_str += f" and {len(releases) - 3} more"
        facts.append(f"Appears on: {release_str}")

    result["facts"].extend(facts)
    result["sources"].append({
        "provider": "musicbrainz",
        "url": f"https://musicbrainz.org/recording/{mb_data['mbid']}",
        "sections": ["recording_info"]
    })

    result["metadata"] = {
        "length": mb_data.get("length"),
        "length_ms": mb_data.get("length_ms"),
        "isrc": mb_data.get("isrc"),
        "releases": releases,
    }

    # Step 2: [Future] Genius lyrics
    # if artist_name:
    #     genius_data = await search_genius(track_title, artist_name)
    #     if genius_data:
    #         result["lyrics"] = genius_data.get("lyrics")
    #         result["urls"]["genius"] = genius_data.get("url")

    return result


async def enrich_music_entity(
    query_text: str,
    entity_type: str,
    entity_name: str,
    artist_name: Optional[str] = None,
    trace_id: str = "unknown"
) -> Optional[Dict[str, Any]]:
    """
    Smart enrichment router based on entity type.

    Args:
        query_text: Original query text
        entity_type: "artist", "album", "track", or "auto"
        entity_name: Name of entity to enrich
        artist_name: Artist name (for albums/tracks)
        trace_id: Trace ID

    Returns:
        Context-aware enrichment result
    """
    # Auto-detect entity type if needed
    if entity_type == "auto":
        query_lower = query_text.lower()
        if any(word in query_lower for word in ["album", "record", "lp", "ep"]):
            entity_type = "album"
        elif any(word in query_lower for word in ["song", "track", "single"]):
            entity_type = "track"
        else:
            # Default to artist
            entity_type = "artist"

    # Route to appropriate enrichment function
    if entity_type == "artist":
        return await enrich_artist_multi_source(entity_name, trace_id)
    elif entity_type == "album":
        return await enrich_album_multi_source(entity_name, artist_name, trace_id)
    elif entity_type == "track":
        return await enrich_track_multi_source(entity_name, artist_name, trace_id)
    else:
        return None


def set_trace_id(trace_id: str):
    """Set trace ID for all providers."""
    try:
        from providers import musicbrainz_complete, wikipedia_enhanced
    except ImportError:
        import musicbrainz_complete, wikipedia_enhanced
    musicbrainz_complete.set_trace_id(trace_id)
    wikipedia_enhanced.set_trace_id(trace_id)
