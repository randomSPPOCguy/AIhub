"""
Complete MusicBrainz provider - extracts EVERYTHING possible.

This is the PRIMARY source for music data. It provides:
- Canonical IDs (MBIDs) for artists, albums, tracks
- Wikidata/Wikipedia links for exact page lookups
- Structured music data (releases, recordings, relationships)
- Cross-database links (Discogs, AllMusic, Spotify, etc.)
"""

import asyncio
import time
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


class MBRateLimiter:
    """Strict 1 request per second rate limiter for MusicBrainz."""

    def __init__(self):
        self.min_interval = 1.0
        self.last_request_time: Optional[float] = None
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.time()
            if self.last_request_time is not None:
                elapsed = now - self.last_request_time
                if elapsed < self.min_interval:
                    await asyncio.sleep(self.min_interval - elapsed)
                    now = time.time()
            self.last_request_time = now


_rate_limiter = MBRateLimiter()

HEADERS = {
    "User-Agent": "AIhub-Enrichment/1.4 (https://github.com/aihub-music)",
}


async def search_artist(name: str) -> Optional[Dict[str, Any]]:
    """
    Search for artist and return COMPLETE data.

    Returns everything MusicBrainz knows about the artist:
    - MBID (canonical ID)
    - Wikidata/Wikipedia IDs
    - All external links (Discogs, AllMusic, Spotify, etc.)
    - Band members
    - Genres/tags
    - All release groups (albums, EPs, singles)
    """
    start = time.time()
    trace_id = getattr(search_artist, "_trace_id", "unknown")

    await _rate_limiter.acquire()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Step 1: Search for artist
            params = {
                "query": f'artist:"{name}"',
                "fmt": "json",
                "limit": 1,
            }
            resp = await client.get("https://musicbrainz.org/ws/2/artist/", params=params, headers=HEADERS)
            resp.raise_for_status()
            data = resp.json()

            artists = data.get("artists", [])
            if not artists:
                log_provider_call(trace_id, "musicbrainz_search", (time.time()-start)*1000, False, "No results")
                return None

            mbid = artists[0].get("id")
            if not mbid:
                return None

            # Step 2: Get COMPLETE artist details
            await _rate_limiter.acquire()

            # Request EVERYTHING available
            detail_params = {
                "fmt": "json",
                "inc": "url-rels+release-groups+tags+ratings+genres+aliases",
            }
            detail_resp = await client.get(
                f"https://musicbrainz.org/ws/2/artist/{mbid}",
                params=detail_params,
                headers=HEADERS
            )
            detail_resp.raise_for_status()
            artist_data = detail_resp.json()

            # Extract all data
            result = {
                "type": "artist",
                "mbid": mbid,
                "name": artist_data.get("name"),
                "sort_name": artist_data.get("sort-name"),
                "disambiguation": artist_data.get("disambiguation", ""),
                "type_name": artist_data.get("type", ""),  # Person, Group, Orchestra, etc.
                "country": artist_data.get("country"),
                "life_span": artist_data.get("life-span", {}),
                "active_years": _format_life_span(artist_data.get("life-span", {})),
                "ids": {"musicbrainz": mbid},
                "urls": {},
                "genres": [],
                "tags": [],
                "release_groups": [],
                "albums": [],
                "singles": [],
                "eps": [],
            }

            # Extract genres
            for genre in artist_data.get("genres", []):
                result["genres"].append(genre.get("name"))

            # Extract tags (user-generated)
            for tag in artist_data.get("tags", [])[:10]:  # Top 10 tags
                result["tags"].append(tag.get("name"))

            # Extract URLs and cross-database IDs
            for relation in artist_data.get("relations", []):
                rel_type = relation.get("type", "")
                url_obj = relation.get("url", {})
                url = url_obj.get("resource", "")

                if not url:
                    continue

                # Wikidata
                if rel_type == "wikidata" and "wikidata.org/wiki/" in url:
                    wikidata_id = url.split("/wiki/")[-1]
                    result["ids"]["wikidata"] = wikidata_id
                    result["urls"]["wikidata"] = url

                # Wikipedia
                elif rel_type == "wikipedia":
                    result["urls"]["wikipedia"] = url
                    # Extract language and title
                    if ".wikipedia.org/wiki/" in url:
                        parts = url.split(".wikipedia.org/wiki/")
                        lang = url.split("//")[1].split(".")[0]
                        title = parts[-1]
                        result["wikipedia_title"] = title.replace("_", " ")
                        result["wikipedia_lang"] = lang

                # Discogs
                elif "discogs.com" in url:
                    result["urls"]["discogs"] = url
                    if "/artist/" in url:
                        discogs_id = url.split("/artist/")[-1].split("-")[0]
                        result["ids"]["discogs"] = discogs_id

                # AllMusic
                elif "allmusic.com" in url:
                    result["urls"]["allmusic"] = url

                # Last.fm
                elif "last.fm" in url:
                    result["urls"]["lastfm"] = url

                # Spotify
                elif "spotify.com/artist/" in url:
                    result["urls"]["spotify"] = url
                    spotify_id = url.split("/artist/")[-1].split("?")[0]
                    result["ids"]["spotify"] = spotify_id

                # Apple Music
                elif "music.apple.com" in url:
                    result["urls"]["apple_music"] = url

                # Official homepage
                elif rel_type == "official homepage":
                    result["urls"]["official"] = url

                # Social media
                elif "twitter.com" in url or "x.com" in url:
                    result["urls"]["twitter"] = url
                elif "instagram.com" in url:
                    result["urls"]["instagram"] = url
                elif "facebook.com" in url:
                    result["urls"]["facebook"] = url
                elif "youtube.com" in url:
                    result["urls"]["youtube"] = url

            # Extract release groups (albums, EPs, singles)
            for rg in artist_data.get("release-groups", []):
                rg_type = rg.get("primary-type", "")
                secondary_types = rg.get("secondary-types", [])

                rg_data = {
                    "mbid": rg.get("id"),
                    "title": rg.get("title"),
                    "type": rg_type,
                    "secondary_types": secondary_types,
                    "disambiguation": rg.get("disambiguation", ""),
                    "first_release_date": rg.get("first-release-date", ""),
                    "year": rg.get("first-release-date", "")[:4] if rg.get("first-release-date") else "",
                }

                result["release_groups"].append(rg_data)

                # Categorize by type - FILTER OUT soundtracks, compilations, live albums
                # STRICT: Only include pure studio albums (primary type = "Album" with NO secondary types)
                if rg_type == "Album":
                    # STRICT FILTERING: Exclude anything with secondary types that indicate non-studio albums
                    excluded_secondary = ["Soundtrack", "Compilation", "Live", "Remix", "DJ-mix", "Mixtape/Street", "Spokenword", "Interview", "Audiobook"]
                    is_excluded = any(st in excluded_secondary for st in secondary_types)

                    # Aggressive title-based filtering for soundtracks
                    title_lower = rg.get("title", "").lower()
                    disambiguation_lower = (rg.get("disambiguation", "") or "").lower()
                    
                    # Check for soundtrack indicators in title and disambiguation
                    soundtrack_keywords = [
                        "soundtrack", "ost", "score", "original soundtrack", 
                        "film score", "movie soundtrack", "tv soundtrack",
                        "soundtrack album", "music from", "music of"
                    ]
                    is_soundtrack_in_title = any(keyword in title_lower for keyword in soundtrack_keywords)
                    is_soundtrack_in_disambiguation = any(keyword in disambiguation_lower for keyword in soundtrack_keywords)

                    # STRICT: Only include if:
                    # 1. No excluded secondary types
                    # 2. Title doesn't suggest soundtrack
                    # 3. Disambiguation doesn't suggest soundtrack
                    # 4. PREFER albums with NO secondary types (pure studio albums)
                    if not is_excluded and not is_soundtrack_in_title and not is_soundtrack_in_disambiguation:
                        # Prefer albums with no secondary types, but allow others if they pass filters
                        result["albums"].append(rg_data)
                elif rg_type == "Single":
                    result["singles"].append(rg_data)
                elif rg_type == "EP":
                    result["eps"].append(rg_data)

            # Sort albums: prioritize pure studio albums (no secondary types), then by date (newest first)
            # This ensures studio albums appear before any albums with secondary types
            result["albums"].sort(key=lambda x: (
                len(x.get("secondary_types", [])) == 0,  # True (1) for pure studio albums, False (0) for others
                x.get("first_release_date", ""),  # Then by date (newest first)
            ), reverse=True)

            # Add counts
            result["album_count"] = len(result["albums"])
            result["single_count"] = len(result["singles"])
            result["ep_count"] = len(result["eps"])
            result["total_releases"] = len(result["release_groups"])

            log_provider_call(trace_id, "musicbrainz_artist", (time.time()-start)*1000, True)
            return result

        except Exception as e:
            log_provider_call(trace_id, "musicbrainz_artist", (time.time()-start)*1000, False, str(e))
            return None


async def search_release(title: str, artist: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Search for album/release and return COMPLETE data.

    Returns:
    - Release MBID
    - Wikidata/Wikipedia links
    - Tracklist with durations
    - Label, barcode, catalog number
    - Release date, country
    - Credits (producers, engineers, etc.)
    """
    start = time.time()
    trace_id = getattr(search_release, "_trace_id", "unknown")

    await _rate_limiter.acquire()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Step 1: Search for release
            query = f'release:"{title}"'
            if artist:
                query += f' AND artist:"{artist}"'

            params = {
                "query": query,
                "fmt": "json",
                "limit": 1,
            }
            resp = await client.get("https://musicbrainz.org/ws/2/release/", params=params, headers=HEADERS)
            resp.raise_for_status()
            data = resp.json()

            releases = data.get("releases", [])
            if not releases:
                log_provider_call(trace_id, "musicbrainz_release_search", (time.time()-start)*1000, False, "No results")
                return None

            release_mbid = releases[0].get("id")
            if not release_mbid:
                return None

            # Step 2: Get COMPLETE release details
            await _rate_limiter.acquire()

            detail_params = {
                "fmt": "json",
                "inc": "recordings+artist-credits+labels+url-rels+genres+tags",
            }
            detail_resp = await client.get(
                f"https://musicbrainz.org/ws/2/release/{release_mbid}",
                params=detail_params,
                headers=HEADERS
            )
            detail_resp.raise_for_status()
            release_data = detail_resp.json()

            # Extract all data
            result = {
                "type": "release",
                "mbid": release_mbid,
                "title": release_data.get("title"),
                "artist": release_data.get("artist-credit", [{}])[0].get("artist", {}).get("name", ""),
                "artist_mbid": release_data.get("artist-credit", [{}])[0].get("artist", {}).get("id", ""),
                "date": release_data.get("date", ""),
                "year": release_data.get("date", "")[:4] if release_data.get("date") else "",
                "country": release_data.get("country"),
                "barcode": release_data.get("barcode"),
                "status": release_data.get("status"),
                "packaging": release_data.get("packaging"),
                "ids": {"musicbrainz": release_mbid},
                "urls": {},
                "labels": [],
                "tracks": [],
                "genres": [],
                "tags": [],
                "total_tracks": 0,
                "total_length_ms": 0,
            }

            # Extract labels
            for label_info in release_data.get("label-info", []):
                label = label_info.get("label", {})
                result["labels"].append({
                    "name": label.get("name"),
                    "catalog_number": label_info.get("catalog-number"),
                })

            # Extract URLs
            for relation in release_data.get("relations", []):
                rel_type = relation.get("type", "")
                url = relation.get("url", {}).get("resource", "")

                if "wikidata.org/wiki/" in url:
                    wikidata_id = url.split("/wiki/")[-1]
                    result["ids"]["wikidata"] = wikidata_id
                    result["urls"]["wikidata"] = url
                elif rel_type == "wikipedia":
                    result["urls"]["wikipedia"] = url
                elif "discogs.com" in url:
                    result["urls"]["discogs"] = url
                elif "spotify.com/album/" in url:
                    result["urls"]["spotify"] = url
                    result["ids"]["spotify"] = url.split("/album/")[-1].split("?")[0]

            # Extract tracks
            track_num = 1
            for medium in release_data.get("media", []):
                for track in medium.get("tracks", []):
                    recording = track.get("recording", {})
                    track_data = {
                        "position": track_num,
                        "title": recording.get("title"),
                        "length_ms": track.get("length") or recording.get("length"),
                        "length": _format_duration(track.get("length") or recording.get("length")),
                        "mbid": recording.get("id"),
                    }
                    result["tracks"].append(track_data)
                    track_num += 1

                    if track_data["length_ms"]:
                        result["total_length_ms"] += track_data["length_ms"]

            result["total_tracks"] = len(result["tracks"])
            result["total_length"] = _format_duration(result["total_length_ms"])

            # Extract genres/tags
            for genre in release_data.get("genres", []):
                result["genres"].append(genre.get("name"))
            for tag in release_data.get("tags", [])[:10]:
                result["tags"].append(tag.get("name"))

            log_provider_call(trace_id, "musicbrainz_release", (time.time()-start)*1000, True)
            return result

        except Exception as e:
            log_provider_call(trace_id, "musicbrainz_release", (time.time()-start)*1000, False, str(e))
            return None


async def search_recording(title: str, artist: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Search for track/recording and return COMPLETE data.

    Returns:
    - Recording MBID
    - Length, ISRC
    - Artist credits (featuring, with, etc.)
    - Associated releases (which albums it appears on)
    """
    start = time.time()
    trace_id = getattr(search_recording, "_trace_id", "unknown")

    await _rate_limiter.acquire()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            query = f'recording:"{title}"'
            if artist:
                query += f' AND artist:"{artist}"'

            params = {
                "query": query,
                "fmt": "json",
                "limit": 1,
            }
            resp = await client.get("https://musicbrainz.org/ws/2/recording/", params=params, headers=HEADERS)
            resp.raise_for_status()
            data = resp.json()

            recordings = data.get("recordings", [])
            if not recordings:
                log_provider_call(trace_id, "musicbrainz_recording", (time.time()-start)*1000, False, "No results")
                return None

            recording = recordings[0]

            result = {
                "type": "recording",
                "mbid": recording.get("id"),
                "title": recording.get("title"),
                "artist": recording.get("artist-credit", [{}])[0].get("name", ""),
                "length_ms": recording.get("length"),
                "length": _format_duration(recording.get("length")),
                "ids": {"musicbrainz": recording.get("id")},
                "urls": {},
                "isrc": recording.get("isrcs", [None])[0] if recording.get("isrcs") else None,
                "releases": [],
            }

            # Extract releases this recording appears on
            for release in recording.get("releases", [])[:5]:  # Top 5 releases
                result["releases"].append({
                    "title": release.get("title"),
                    "date": release.get("date", ""),
                    "mbid": release.get("id"),
                })

            log_provider_call(trace_id, "musicbrainz_recording", (time.time()-start)*1000, True)
            return result

        except Exception as e:
            log_provider_call(trace_id, "musicbrainz_recording", (time.time()-start)*1000, False, str(e))
            return None


def _format_life_span(life_span: Dict) -> str:
    """Format artist life span."""
    if not life_span:
        return ""
    begin = life_span.get("begin", "")
    end = life_span.get("end", "")
    if begin and end:
        return f"{begin[:4]} - {end[:4]}"
    elif begin:
        return f"{begin[:4]} - present"
    return ""


def _format_duration(ms: Optional[int]) -> str:
    """Format duration from milliseconds to MM:SS."""
    if not ms:
        return ""
    seconds = ms // 1000
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def set_trace_id(trace_id: str):
    """Set trace ID for logging."""
    search_artist._trace_id = trace_id
    search_release._trace_id = trace_id
    search_recording._trace_id = trace_id
