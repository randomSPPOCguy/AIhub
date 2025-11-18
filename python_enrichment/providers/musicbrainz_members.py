"""
MusicBrainz Band Members & Relationships Extractor

Gets band members, collaborators, producers, etc. from MusicBrainz relationships.
This is FREE data already in MusicBrainz - no extra API needed!
"""

import asyncio
import time
from typing import Optional, Dict, Any, List
import httpx

import sys
import os
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


async def get_band_members(artist_mbid: str) -> Optional[Dict[str, Any]]:
    """
    Get band members, formation, and relationships for an artist.

    This extracts:
    - Current members
    - Past members
    - Member instruments
    - Formation date
    - Related artists (collaborations, side projects)

    Args:
        artist_mbid: MusicBrainz artist ID

    Returns:
        Dict with members, formation info, and relationships
    """
    start = time.time()
    trace_id = getattr(get_band_members, "_trace_id", "unknown")

    await _rate_limiter.acquire()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Request artist with ALL relationship types
            params = {
                "fmt": "json",
                "inc": "artist-rels+work-rels",  # Get member relationships
            }

            resp = await client.get(
                f"https://musicbrainz.org/ws/2/artist/{artist_mbid}",
                params=params,
                headers=HEADERS
            )
            resp.raise_for_status()
            data = resp.json()

            result = {
                "mbid": artist_mbid,
                "name": data.get("name"),
                "type": data.get("type"),  # Group, Person, etc.
                "current_members": [],
                "past_members": [],
                "member_of": [],  # If person, what bands they're in
                "collaborators": [],
                "formation": data.get("life-span", {}),
            }

            # Extract member relationships
            for relation in data.get("relations", []):
                rel_type = relation.get("type")
                direction = relation.get("direction", "forward")

                # Get the related artist
                if "artist" in relation:
                    related_artist = relation["artist"]
                    artist_info = {
                        "name": related_artist.get("name"),
                        "mbid": related_artist.get("id"),
                        "type": related_artist.get("type"),
                    }

                    # Extract attributes (instruments, vocals, etc.)
                    attributes = []
                    for attr in relation.get("attributes", []):
                        attributes.append(attr)
                    if attributes:
                        artist_info["role"] = ", ".join(attributes)

                    # Extract time period
                    begin = relation.get("begin")
                    end = relation.get("end")
                    if begin or end:
                        period = f"{begin or '?'} - {end or 'present'}"
                        artist_info["period"] = period

                    # Categorize relationship
                    if rel_type == "member of band":
                        if direction == "backward":
                            # This person is a member
                            if end:
                                result["past_members"].append(artist_info)
                            else:
                                result["current_members"].append(artist_info)
                        else:
                            # This band has this person as member
                            result["member_of"].append(artist_info)

                    elif rel_type in ["collaboration", "member of", "supporting musician"]:
                        result["collaborators"].append(artist_info)

            # Format formation info
            life_span = result.get("formation", {})
            if life_span:
                begin = life_span.get("begin", "")
                end = life_span.get("end", "")
                if begin and end:
                    result["formation_string"] = f"Formed {begin}, disbanded {end}"
                elif begin:
                    result["formation_string"] = f"Formed in {begin}"
                else:
                    result["formation_string"] = ""

            log_provider_call(trace_id, "musicbrainz_members", (time.time()-start)*1000, True)
            return result

        except Exception as e:
            log_provider_call(trace_id, "musicbrainz_members", (time.time()-start)*1000, False, str(e))
            return None


async def get_album_credits(release_mbid: str) -> Optional[Dict[str, Any]]:
    """
    Get album credits: producers, engineers, studios, etc.

    Args:
        release_mbid: MusicBrainz release ID

    Returns:
        Dict with producers, engineers, recording locations, etc.
    """
    start = time.time()
    trace_id = getattr(get_album_credits, "_trace_id", "unknown")

    await _rate_limiter.acquire()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            params = {
                "fmt": "json",
                "inc": "artist-credits+recordings+work-rels",
            }

            resp = await client.get(
                f"https://musicbrainz.org/ws/2/release/{release_mbid}",
                params=params,
                headers=HEADERS
            )
            resp.raise_for_status()
            data = resp.json()

            result = {
                "mbid": release_mbid,
                "title": data.get("title"),
                "producers": [],
                "engineers": [],
                "mixers": [],
                "studios": [],
                "other_credits": [],
            }

            # Extract relationships from release and recordings
            for relation in data.get("relations", []):
                rel_type = relation.get("type")

                if "artist" in relation:
                    artist = relation["artist"]
                    credit = {
                        "name": artist.get("name"),
                        "mbid": artist.get("id"),
                    }

                    # Categorize by role
                    if "produc" in rel_type.lower():
                        result["producers"].append(credit)
                    elif "engineer" in rel_type.lower():
                        result["engineers"].append(credit)
                    elif "mix" in rel_type.lower():
                        result["mixers"].append(credit)
                    else:
                        credit["role"] = rel_type
                        result["other_credits"].append(credit)

                elif "place" in relation:
                    place = relation["place"]
                    if "studio" in rel_type.lower() or "record" in rel_type.lower():
                        result["studios"].append(place.get("name"))

            log_provider_call(trace_id, "musicbrainz_credits", (time.time()-start)*1000, True)
            return result

        except Exception as e:
            log_provider_call(trace_id, "musicbrainz_credits", (time.time()-start)*1000, False, str(e))
            return None


def set_trace_id(trace_id: str):
    """Set trace ID for logging."""
    get_band_members._trace_id = trace_id
    get_album_credits._trace_id = trace_id
