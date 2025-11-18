"""
Free API Providers - No authentication required!

These services provide music data WITHOUT requiring API keys:
1. Cover Art Archive - Album artwork
2. Wikidata - Structured data, band members, awards
3. Archive.org - Live recordings, bootlegs
4. MusicBrainz Cover Art - Album covers
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


async def get_cover_art(release_mbid: str) -> Optional[Dict[str, Any]]:
    """
    Get album cover art from Cover Art Archive (FREE, no key needed).

    Args:
        release_mbid: MusicBrainz release ID

    Returns:
        Dict with cover art URLs (front, back, full resolution, thumbnails)
    """
    start = time.time()
    trace_id = getattr(get_cover_art, "_trace_id", "unknown")

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            url = f"https://coverartarchive.org/release/{release_mbid}"
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

            result = {
                "front_cover": None,
                "back_cover": None,
                "all_images": [],
            }

            for image in data.get("images", []):
                image_data = {
                    "url": image.get("image"),
                    "thumbnails": image.get("thumbnails", {}),
                    "types": image.get("types", []),
                    "front": image.get("front", False),
                    "back": image.get("back", False),
                }

                result["all_images"].append(image_data)

                if image_data["front"]:
                    result["front_cover"] = image_data
                if image_data["back"]:
                    result["back_cover"] = image_data

            log_provider_call(trace_id, "coverart", (time.time()-start)*1000, True)
            return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                log_provider_call(trace_id, "coverart", (time.time()-start)*1000, False, "No cover art found")
            else:
                log_provider_call(trace_id, "coverart", (time.time()-start)*1000, False, str(e))
            return None
        except Exception as e:
            log_provider_call(trace_id, "coverart", (time.time()-start)*1000, False, str(e))
            return None


async def get_wikidata_extended(wikidata_id: str) -> Optional[Dict[str, Any]]:
    """
    Get extended Wikidata information (FREE, no key needed).

    Extracts:
    - Band members with instruments
    - Awards
    - Chart positions
    - Genres (more detailed than MusicBrainz)
    - Origin location
    - Record labels

    Args:
        wikidata_id: Wikidata ID (e.g., Q44190 for Radiohead)

    Returns:
        Dict with structured data
    """
    start = time.time()
    trace_id = getattr(get_wikidata_extended, "_trace_id", "unknown")

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            url = "https://www.wikidata.org/w/api.php"
            params = {
                "action": "wbgetentities",
                "ids": wikidata_id,
                "format": "json",
                "props": "claims|labels|descriptions",
                "languages": "en",
            }

            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            entity = data.get("entities", {}).get(wikidata_id, {})
            claims = entity.get("claims", {})

            result = {
                "wikidata_id": wikidata_id,
                "label": entity.get("labels", {}).get("en", {}).get("value", ""),
                "description": entity.get("descriptions", {}).get("en", {}).get("value", ""),
                "members": [],
                "genres": [],
                "origin": None,
                "inception": None,
                "awards": [],
                "record_labels": [],
            }

            # Extract members (P527 - has part)
            for claim in claims.get("P527", []):
                if claim.get("mainsnak", {}).get("datavalue"):
                    member_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                    # Would need another API call to get member details
                    result["members"].append({"id": member_id})

            # Extract genres (P136)
            for claim in claims.get("P136", []):
                if claim.get("mainsnak", {}).get("datavalue"):
                    genre_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                    result["genres"].append({"id": genre_id})

            # Extract origin (P740 - location of formation)
            if "P740" in claims and claims["P740"]:
                origin_claim = claims["P740"][0]
                if origin_claim.get("mainsnak", {}).get("datavalue"):
                    result["origin"] = origin_claim["mainsnak"]["datavalue"]["value"]["id"]

            # Extract inception/formation date (P571)
            if "P571" in claims and claims["P571"]:
                inception_claim = claims["P571"][0]
                if inception_claim.get("mainsnak", {}).get("datavalue"):
                    result["inception"] = inception_claim["mainsnak"]["datavalue"]["value"]["time"]

            # Extract awards (P166)
            for claim in claims.get("P166", []):
                if claim.get("mainsnak", {}).get("datavalue"):
                    award_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                    result["awards"].append({"id": award_id})

            # Extract record labels (P264)
            for claim in claims.get("P264", []):
                if claim.get("mainsnak", {}).get("datavalue"):
                    label_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                    result["record_labels"].append({"id": label_id})

            log_provider_call(trace_id, "wikidata_extended", (time.time()-start)*1000, True)
            return result

        except Exception as e:
            log_provider_call(trace_id, "wikidata_extended", (time.time()-start)*1000, False, str(e))
            return None


def set_trace_id(trace_id: str):
    """Set trace ID for logging."""
    get_cover_art._trace_id = trace_id
    get_wikidata_extended._trace_id = trace_id
