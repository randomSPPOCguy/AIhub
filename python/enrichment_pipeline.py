"""Enrichment pipeline chaining MusicBrainz -> Wikidata -> Wikipedia."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


USER_AGENT = "ProjectFrank/0.1 (https://example.com)"


@dataclass
class EnrichmentResult:
    entity: str
    entity_type: str
    musicbrainz: Dict[str, Any]
    wikidata: Dict[str, Any]
    wikipedia: Dict[str, Any]


class EnrichmentPipeline:
    def __init__(self, rate_limit_delay: float = 1.0) -> None:
        self.rate_limit_delay = rate_limit_delay

    def enrich(self, entity_name: str, entity_type: str) -> Dict[str, Any]:
        """Run the enrichment chain. Network errors are captured in the payload."""
        mb = self._musicbrainz_lookup(entity_name, entity_type)
        wd = self._wikidata_lookup(mb)
        wp = self._wikipedia_fetch(wd)
        return asdict(
            EnrichmentResult(
                entity=entity_name,
                entity_type=entity_type,
                musicbrainz=mb,
                wikidata=wd,
                wikipedia=wp,
            )
        )

    def _musicbrainz_lookup(self, entity_name: str, entity_type: str) -> Dict[str, Any]:
        entity = urllib.parse.quote(entity_name)
        url = (
            f"https://musicbrainz.org/ws/2/artist/?query={entity}&fmt=json"
            if entity_type == "artist"
            else f"https://musicbrainz.org/ws/2/search/?query={entity}&fmt=json"
        )
        return self._get_json(url, "musicbrainz")

    def _wikidata_lookup(self, mb_payload: Dict[str, Any]) -> Dict[str, Any]:
        wikidata_id = self._extract_wikidata_id(mb_payload)
        if not wikidata_id:
            return {"error": "missing wikidata id"}
        url = (
            "https://www.wikidata.org/w/api.php?action=wbgetentities"
            f"&ids={wikidata_id}&format=json&props=labels|descriptions|sitelinks"
        )
        return self._get_json(url, "wikidata")

    def _wikipedia_fetch(self, wd_payload: Dict[str, Any]) -> Dict[str, Any]:
        site_link = self._extract_wikipedia_title(wd_payload)
        if not site_link:
            return {"error": "missing wikipedia sitelink"}
        title = urllib.parse.quote(site_link)
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
        return self._get_json(url, "wikipedia")

    def _get_json(self, url: str, label: str) -> Dict[str, Any]:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # broad but necessary for foundation
            payload = {"error": str(exc), "url": url}
        time.sleep(self.rate_limit_delay)
        payload["_source"] = label
        return payload

    @staticmethod
    def _extract_wikidata_id(mb_payload: Dict[str, Any]) -> Optional[str]:
        for artist in mb_payload.get("artists", []):
            relations = artist.get("relations", [])
            for rel in relations:
                if rel.get("type") == "wikidata":
                    return rel.get("url", {}).get("resource", "").split("/")[-1]
        return None

    @staticmethod
    def _extract_wikipedia_title(wd_payload: Dict[str, Any]) -> Optional[str]:
        entities = wd_payload.get("entities", {})
        if not entities:
            return None
        _, data = next(iter(entities.items()))
        enwiki = data.get("sitelinks", {}).get("enwiki", {})
        return enwiki.get("title")
