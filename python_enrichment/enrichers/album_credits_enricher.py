"""
Album Credits Enricher
Gets producers, engineers, studios, and cover art for albums.
Uses MusicBrainz credits provider and Cover Art Archive.
Caches for 7 days (album credits don't change).
"""

import time
from typing import Optional, Dict, Any, List
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from providers.musicbrainz_members import get_album_credits
    from providers.free_apis import get_cover_art
    from cache import LRUCache
except ImportError:
    from providers import musicbrainz_members, free_apis
    get_album_credits = musicbrainz_members.get_album_credits
    get_cover_art = free_apis.get_cover_art
    from cache import LRUCache


# Cache for 7 days (604800 seconds)
ALBUM_CREDITS_CACHE_TTL = 604800


class AlbumCreditsEnricher:
    """Enriches album data with production credits and cover art."""

    def __init__(self):
        """Initialize with dedicated cache for album credits."""
        # Use dedicated cache with 7-day TTL
        self.cache = LRUCache(max_size=500, ttl_seconds=ALBUM_CREDITS_CACHE_TTL)

    async def enrich_credits(self, release_mbid: str, trace_id: str = "unknown") -> Optional[Dict[str, Any]]:
        """
        Get album production credits and cover art.

        Args:
            release_mbid: MusicBrainz release ID
            trace_id: Trace ID for logging

        Returns:
            {
                "producers": ["Nigel Godrich", "Radiohead"],
                "engineers": ["Darrell Thorp"],
                "mixers": [],
                "studios": ["Abbey Road Studios", "..."],
                "recorded": "1996-1997",
                "cover_art": {
                    "front": "https://...",
                    "back": "https://...",
                    "thumbnails": {
                        "small": "https://...",
                        "large": "https://..."
                    }
                }
            }
        """
        start = time.time()
        cache_key = f"credits:{release_mbid}"

        # Check cache first
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            # Set trace IDs for providers
            from providers.musicbrainz_members import set_trace_id as set_mb_trace_id
            from providers.free_apis import set_trace_id as set_ca_trace_id
            set_mb_trace_id(trace_id)
            set_ca_trace_id(trace_id)

            # Get credits and cover art in parallel
            credits_task = get_album_credits(release_mbid)
            cover_art_task = get_cover_art(release_mbid)

            # Wait for both (or first to complete with timeout handling)
            credits_data = await credits_task
            cover_art_data = await cover_art_task

            # Format the response
            result = {
                "mbid": release_mbid,
                "title": "",
                "producers": [],
                "engineers": [],
                "mixers": [],
                "studios": [],
                "recorded": "",
                "cover_art": None,
            }

            # Process credits data
            if credits_data:
                result["title"] = credits_data.get("title", "")
                
                # Extract producer names
                for producer in credits_data.get("producers", []):
                    name = producer.get("name", "")
                    if name:
                        result["producers"].append(name)

                # Extract engineer names
                for engineer in credits_data.get("engineers", []):
                    name = engineer.get("name", "")
                    if name:
                        result["engineers"].append(name)

                # Extract mixer names
                for mixer in credits_data.get("mixers", []):
                    name = mixer.get("name", "")
                    if name:
                        result["mixers"].append(name)

                # Extract studio names
                studios = credits_data.get("studios", [])
                if studios:
                    result["studios"] = studios

            # Process cover art data
            if cover_art_data:
                cover_art = {}
                
                # Front cover
                if cover_art_data.get("front_cover"):
                    front = cover_art_data["front_cover"]
                    cover_art["front"] = front.get("url", "")
                    if front.get("thumbnails"):
                        cover_art["thumbnails"] = front["thumbnails"]

                # Back cover
                if cover_art_data.get("back_cover"):
                    back = cover_art_data["back_cover"]
                    cover_art["back"] = back.get("url", "")

                if cover_art:
                    result["cover_art"] = cover_art

            # Cache the result
            self.cache.set(cache_key, result, ttl_seconds=ALBUM_CREDITS_CACHE_TTL)

            return result

        except Exception as e:
            # Log error but don't fail completely
            import traceback
            traceback.print_exc()
            return None

    def format_credits_for_display(self, data: Dict[str, Any]) -> List[str]:
        """
        Format credits data as readable strings for AI responses.

        Args:
            data: Enriched credits data

        Returns:
            List of formatted strings, each <100 chars
        """
        if not data:
            return []

        facts = []

        # Producer credit
        producers = data.get("producers", [])
        if producers:
            producers_str = ", ".join(producers[:3])  # Limit to 3
            if len(producers) > 3:
                producers_str += f" (+{len(producers) - 3} more)"
            fact = f"Producer: {producers_str}"
            if len(fact) <= 100:
                facts.append(fact)

        # Engineer credit
        engineers = data.get("engineers", [])
        if engineers:
            engineers_str = ", ".join(engineers[:2])  # Limit to 2
            fact = f"Engineer: {engineers_str}"
            if len(fact) <= 100:
                facts.append(fact)

        # Studio credit
        studios = data.get("studios", [])
        if studios:
            studios_str = ", ".join(studios[:2])  # Limit to 2
            fact = f"Recorded at: {studios_str}"
            if len(fact) <= 100:
                facts.append(fact)

        # Recording period (if available from other sources)
        recorded = data.get("recorded", "")
        if recorded:
            fact = f"Recorded: {recorded}"
            if len(fact) <= 100:
                facts.append(fact)

        return facts


# Global instance
_enricher: Optional[AlbumCreditsEnricher] = None


def get_enricher() -> AlbumCreditsEnricher:
    """Get or create global enricher instance."""
    global _enricher
    if _enricher is None:
        _enricher = AlbumCreditsEnricher()
    return _enricher


async def enrich_album_credits(release_mbid: str, trace_id: str = "unknown") -> Optional[Dict[str, Any]]:
    """
    Convenience function to enrich album credits.

    Args:
        release_mbid: MusicBrainz release ID
        trace_id: Trace ID for logging

    Returns:
        Enriched credits data
    """
    enricher = get_enricher()
    return await enricher.enrich_credits(release_mbid, trace_id)

