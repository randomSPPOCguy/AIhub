"""Provider modules for enrichment service."""

try:
    from .wikipedia import enrich_wikipedia
    from .musicbrainz import enrich_musicbrainz
except ImportError:
    from wikipedia import enrich_wikipedia
    from musicbrainz import enrich_musicbrainz

__all__ = ["enrich_wikipedia", "enrich_musicbrainz"]

