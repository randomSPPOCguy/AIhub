"""Python bridge for Project Frank.

This module is embedded into the Rust binary via PyO3. It provides the public
functions invoked from Rust and orchestrates enrichment + LLM calls.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List

from enrichment_pipeline import EnrichmentPipeline

_pipeline = EnrichmentPipeline()


@dataclass
class ResponseBundle:
    query: str
    enrichment: List[str]

    def format(self) -> str:
        chunks = "\n".join(f"- {item}" for item in self.enrichment) or "No enrichment yet."
        return "\n".join(
            [
                "Project Frank",
                f"Prompt :: {self.query}",
                f"Enrichment:\n{chunks}",
                "Response is synthesized by the placeholder NLG engine.",
            ]
        )


def generate_response(query: str, enrichment_data: List[str]) -> str:
    """Return a human-like response. Replace with a real NLG/LLM implementation."""
    bundle = ResponseBundle(query=query, enrichment=enrichment_data)
    return bundle.format()


def enrich_entity(entity_name: str, entity_type: str = "artist") -> str:
    """Return enrichment payload as a JSON string."""
    enriched = _pipeline.enrich(entity_name, entity_type)
    return json.dumps(enriched, ensure_ascii=False)
