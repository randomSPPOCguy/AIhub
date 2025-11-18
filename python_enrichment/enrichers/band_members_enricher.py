"""
Band Members Enricher
Extracts and formats band member data for fast responses.
Uses MusicBrainz members provider with 24-hour cache.
"""

import time
from typing import Optional, Dict, Any, List
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from providers.musicbrainz_members import get_band_members
    from cache import LRUCache, get_cache
except ImportError:
    from providers import musicbrainz_members
    get_band_members = musicbrainz_members.get_band_members
    from cache import LRUCache, get_cache


# Cache for 24 hours (86400 seconds)
MEMBERS_CACHE_TTL = 86400


class BandMembersEnricher:
    """Enriches artist data with band member information."""

    def __init__(self):
        """Initialize with dedicated cache for band members."""
        # Use dedicated cache with 24-hour TTL
        self.cache = LRUCache(max_size=500, ttl_seconds=MEMBERS_CACHE_TTL)

    async def enrich_members(self, artist_mbid: str, trace_id: str = "unknown") -> Optional[Dict[str, Any]]:
        """
        Get band members with roles and tenure.

        Args:
            artist_mbid: MusicBrainz artist ID
            trace_id: Trace ID for logging

        Returns:
            {
                "current_members": [
                    {"name": "Thom Yorke", "role": "vocals, guitar", "since": "1991"},
                    ...
                ],
                "past_members": [
                    {"name": "...", "role": "...", "period": "1991-1995"},
                ],
                "formation": "Formed in 1991 in Oxford, UK",
                "member_count": 5
            }
        """
        start = time.time()
        cache_key = f"members:{artist_mbid}"

        # Check cache first
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            # Set trace ID for provider
            from providers.musicbrainz_members import set_trace_id
            set_trace_id(trace_id)

            # Get raw member data from provider
            raw_data = await get_band_members(artist_mbid)
            if not raw_data:
                return None

            # Format and structure the response
            result = {
                "mbid": artist_mbid,
                "name": raw_data.get("name", ""),
                "type": raw_data.get("type", ""),
                "current_members": [],
                "past_members": [],
                "formation": raw_data.get("formation_string", ""),
                "member_count": 0,
            }

            # Format current members - deduplicate by MBID and merge roles
            members_by_mbid = {}
            for member in raw_data.get("current_members", []):
                mbid = member.get("mbid", "")
                name = member.get("name", "")
                role = member.get("role", "member")
                period = member.get("period", "")

                if not mbid:
                    # If no MBID, use name as key (less reliable)
                    key = name.lower()
                else:
                    key = mbid

                if key not in members_by_mbid:
                    members_by_mbid[key] = {
                        "name": name,
                        "mbid": mbid,
                        "roles": [],
                        "period": period,
                        "since": self._extract_year_from_period(period),
                    }

                # Merge roles (avoid duplicates, filter generic terms)
                if role and role != "member":
                    roles = [r.strip() for r in role.split(",")]
                    for r in roles:
                        # Filter out generic attributes like "original"
                        if r and r.lower() not in ["member", "original"] and r not in members_by_mbid[key]["roles"]:
                            members_by_mbid[key]["roles"].append(r)

            # Convert to list and format roles
            for member_data in members_by_mbid.values():
                role_str = ", ".join(member_data["roles"]) if member_data["roles"] else "member"
                result["current_members"].append({
                    "name": member_data["name"],
                    "mbid": member_data["mbid"],
                    "role": role_str,
                    "since": member_data["since"],
                })

            # Format past members - deduplicate by MBID
            past_members_by_mbid = {}
            for member in raw_data.get("past_members", []):
                mbid = member.get("mbid", "")
                name = member.get("name", "")
                role = member.get("role", "member")
                period = member.get("period", "")

                if not mbid:
                    key = name.lower()
                else:
                    key = mbid

                if key not in past_members_by_mbid:
                    past_members_by_mbid[key] = {
                        "name": name,
                        "mbid": mbid,
                        "roles": [],
                        "period": period,
                    }

                # Merge roles (filter generic terms)
                if role and role != "member":
                    roles = [r.strip() for r in role.split(",")]
                    for r in roles:
                        if r and r.lower() not in ["member", "original"] and r not in past_members_by_mbid[key]["roles"]:
                            past_members_by_mbid[key]["roles"].append(r)

            # Convert to list
            for member_data in past_members_by_mbid.values():
                role_str = ", ".join(member_data["roles"]) if member_data["roles"] else "member"
                result["past_members"].append({
                    "name": member_data["name"],
                    "mbid": member_data["mbid"],
                    "role": role_str,
                    "period": member_data["period"],
                })

            result["member_count"] = len(result["current_members"])

            # Cache the result
            self.cache.set(cache_key, result, ttl_seconds=MEMBERS_CACHE_TTL)

            latency_ms = (time.time() - start) * 1000
            if latency_ms < 500:
                # Fast path achieved
                pass

            return result

        except Exception as e:
            # Log error but don't fail completely
            import traceback
            traceback.print_exc()
            return None

    def _extract_year_from_period(self, period: str) -> str:
        """Extract start year from period string like '1991 - present'."""
        if not period:
            return ""
        # Extract first year from period
        parts = period.split("-")
        if parts:
            year = parts[0].strip()
            # Remove 'present' or other text, keep just year
            year = year.split()[0] if year.split() else year
            return year
        return ""

    def format_members_for_display(self, data: Dict[str, Any]) -> str:
        """
        Format members data as a readable string for AI responses.

        Args:
            data: Enriched members data

        Returns:
            Formatted string like "Current members: Thom Yorke (vocals, guitar), ..."
        """
        if not data:
            return ""

        facts = []

        # Formation info
        if data.get("formation"):
            facts.append(data["formation"])

        # Current members
        current = data.get("current_members", [])
        if current:
            member_strings = []
            for member in current[:5]:  # Limit to 5 members
                name = member.get("name", "")
                role = member.get("role", "")
                if role and role != "member":
                    member_strings.append(f"{name} ({role})")
                else:
                    member_strings.append(name)
            if member_strings:
                facts.append(f"Current members: {', '.join(member_strings)}")

        # Past members (if any and not too many)
        past = data.get("past_members", [])
        if past and len(past) <= 3:
            past_strings = []
            for member in past[:3]:
                name = member.get("name", "")
                if name:
                    past_strings.append(name)
            if past_strings:
                facts.append(f"Past members: {', '.join(past_strings)}")

        return " ".join(facts) if facts else ""


# Global instance
_enricher: Optional[BandMembersEnricher] = None


def get_enricher() -> BandMembersEnricher:
    """Get or create global enricher instance."""
    global _enricher
    if _enricher is None:
        _enricher = BandMembersEnricher()
    return _enricher


async def enrich_band_members(artist_mbid: str, trace_id: str = "unknown") -> Optional[Dict[str, Any]]:
    """
    Convenience function to enrich band members.

    Args:
        artist_mbid: MusicBrainz artist ID
        trace_id: Trace ID for logging

    Returns:
        Enriched members data
    """
    enricher = get_enricher()
    return await enricher.enrich_members(artist_mbid, trace_id)

