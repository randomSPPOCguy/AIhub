"""FastAPI application for enrichment service."""

import asyncio
import uuid
import time
import re
from typing import List, Dict, Any, Optional
from fastapi import FastAPI

try:
    from .models import (
        EnrichRequest,
        EnrichResponse,
        EnrichHints,
        SubjectHint,
        Subject,
        Source,
        Meta,
        RoomContext,
    )
    from .config import config
    from .cache import get_cache, normalize_cache_key
    from .structured_logging import (
        log_enrichment_start,
        log_enrichment_complete,
        log_error,
    )
    from .providers.wikipedia import enrich_wikipedia, set_trace_id as set_wikipedia_trace_id
    from .providers.musicbrainz import enrich_musicbrainz, set_trace_id as set_musicbrainz_trace_id
except ImportError:
    from models import (
        EnrichRequest,
        EnrichResponse,
        EnrichHints,
        SubjectHint,
        Subject,
        Source,
        Meta,
        RoomContext,
    )
    from config import config
    from cache import get_cache, normalize_cache_key
    from structured_logging import (
        log_enrichment_start,
        log_enrichment_complete,
        log_error,
    )
    from providers.wikipedia import enrich_wikipedia, set_trace_id as set_wikipedia_trace_id
    from providers.musicbrainz import enrich_musicbrainz, set_trace_id as set_musicbrainz_trace_id

app = FastAPI(title="AIhub Enrichment Service", version=config.SERVICE_VERSION)


def extract_subjects(text: str, room: Optional[RoomContext] = None) -> List[Dict[str, str]]:
    """
    Extract potential subjects from text and room context.

    Args:
        text: Input text
        room: Optional room context

    Returns:
        List of subject dictionaries with name and type
    """
    subjects = []

    # Add subjects from room context
    if room and room.now_playing:
        if room.now_playing.artist:
            subjects.append({"name": room.now_playing.artist, "type": "artist"})
        if room.now_playing.track:
            subjects.append({"name": room.now_playing.track, "type": "track"})

    # Extract from question patterns
    text_lower = text.lower()

    # Pattern 1: "who is [ENTITY]?" or "what is [ENTITY]?"
    who_match = re.search(r'(?:who|what)(?:\'s| is) ([^?]+)', text_lower)
    if who_match:
        entity = who_match.group(1).strip()
        # Clean up common words
        entity = re.sub(r'\s+(the|a|an)\s+', ' ', entity).strip()
        if entity and entity not in [s["name"].lower() for s in subjects]:
            subjects.append({"name": entity.title(), "type": "artist"})

    # Pattern 2: "tell me about [ENTITY]" or "what about [ENTITY]"
    about_match = re.search(r'(?:tell me about|what about|about) ([^?]+)', text_lower)
    if about_match and not who_match:  # Don't duplicate
        entity = about_match.group(1).strip()
        entity = re.sub(r'\s+(the|a|an)\s+', ' ', entity).strip()
        if entity and entity not in [s["name"].lower() for s in subjects]:
            subjects.append({"name": entity.title(), "type": "artist"})

    # Pattern 3: Look for quoted strings
    quoted = re.findall(r'"([^"]+)"', text)
    for quote in quoted:
        if quote not in [s["name"] for s in subjects]:
            subjects.append({"name": quote, "type": "topic"})

    # Pattern 4: Look for capitalized proper nouns (multi-word names)
    # This catches things like "Wet Leg" or "Mike Jones"
    if not subjects:
        capitalized = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text)
        for cap in capitalized:
            if cap.lower() not in ['i', 'bot'] and cap not in [s["name"] for s in subjects]:
                subjects.append({"name": cap, "type": "artist"})

    # If still no subjects found, use key content words (skip question words)
    if not subjects and text:
        # Remove common question words and get meaningful terms
        cleaned = re.sub(r'\b(who|what|where|when|why|how|is|are|was|were|the|a|an|about|tell|me)\b', '', text_lower)
        words = cleaned.split()
        meaningful = [w for w in words if len(w) > 2][:3]
        if meaningful:
            subjects.append({"name": " ".join(meaningful).title(), "type": "topic"})

    return subjects


def extract_keywords(text: str, room: Optional[RoomContext] = None) -> List[str]:
    """
    Extract keywords from text and room context.

    Args:
        text: Input text
        room: Optional room context

    Returns:
        List of keywords
    """
    keywords = []

    # Add from room context
    if room:
        if room.topic:
            keywords.append(room.topic.lower())
        if room.now_playing:
            if room.now_playing.artist:
                keywords.append(room.now_playing.artist.lower())
            if room.now_playing.track:
                keywords.append(room.now_playing.track.lower())

    # Extract from text (simple word extraction)
    words = re.findall(r"\b\w+\b", text.lower())
    # Filter out common stop words (basic list)
    stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "who", "what", "where", "when", "why", "how", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "should", "could", "may", "might", "must", "can"}
    keywords.extend([w for w in words if w not in stop_words and len(w) > 2])

    # Remove duplicates while preserving order
    seen = set()
    unique_keywords = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique_keywords.append(kw)

    return unique_keywords[:20]  # Limit to 20 keywords


async def call_providers(
    subjects: List[Dict[str, str]],
    language: str,
    enabled_providers: List[str],
    trace_id: str,
) -> tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
    """
    Call enabled providers for each subject.

    Args:
        subjects: List of subjects to enrich
        language: Language code
        enabled_providers: List of provider names to use
        trace_id: Trace ID for logging

    Returns:
        Tuple of (subjects_data, facts, sources)
    """
    subjects_data = []
    facts = []
    sources = []

    # Set trace ID for providers
    set_wikipedia_trace_id(trace_id)
    set_musicbrainz_trace_id(trace_id)

    for subject_info in subjects:
        subject_name = subject_info["name"]
        subject_type = subject_info["type"]
        subject_result = {
            "name": subject_name,
            "type": subject_type,
            "ids": {},
            "urls": {},
        }

        # Call providers in parallel
        provider_tasks = []

        if "wikipedia" in enabled_providers and config.ENRICH_WIKIPEDIA_ENABLED:
            provider_tasks.append(("wikipedia", enrich_wikipedia(subject_name, language)))

        if "musicbrainz" in enabled_providers and config.ENRICH_MUSICBRAINZ_ENABLED and subject_type == "artist":
            provider_tasks.append(("musicbrainz", enrich_musicbrainz(subject_name)))

        # Execute providers
        if provider_tasks:
            results = await asyncio.gather(*[task[1] for task in provider_tasks], return_exceptions=True)

            for (provider_name, _), result in zip(provider_tasks, results):
                if isinstance(result, Exception):
                    continue  # Error already logged by provider

                if result:
                    if provider_name == "wikipedia":
                        subject_result["urls"]["wikipedia"] = result.get("url", "")
                        if result.get("summary"):
                            facts.append(result["summary"])
                        sources.append({
                            "provider": "wikipedia",
                            "url": result.get("url", ""),
                            "title": result.get("title", subject_name),
                            "language": language,
                        })

                    elif provider_name == "musicbrainz":
                        subject_result["ids"]["musicbrainz"] = result.get("mbid", "")
                        if result.get("urls"):
                            subject_result["urls"].update(result["urls"])
                        sources.append({
                            "provider": "musicbrainz",
                            "url": result["urls"].get("musicbrainz", ""),
                            "title": result.get("name", subject_name),
                            "language": "en",
                        })

        subjects_data.append(subject_result)

    return subjects_data, facts, sources


def compute_confidence(subjects_data: List[Dict], facts: List[str], sources: List[Dict]) -> float:
    """
    Compute confidence score heuristically.

    Args:
        subjects_data: Enriched subjects
        facts: Extracted facts
        sources: Sources

    Returns:
        Confidence score 0-1
    """
    if not subjects_data and not facts:
        return 0.2  # Very low if nothing found

    # Higher confidence if we have IDs and multiple sources
    has_ids = any(subj.get("ids") for subj in subjects_data)
    has_multiple_sources = len(sources) > 1
    has_facts = len(facts) > 0

    if has_ids and has_multiple_sources and has_facts:
        return 0.9
    elif has_ids or has_multiple_sources:
        return 0.7
    elif has_facts:
        return 0.5
    else:
        return 0.3


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": config.SERVICE_VERSION,
        "service": "enrichment",
    }


@app.post("/enrich", response_model=EnrichResponse)
async def enrich(req: EnrichRequest) -> EnrichResponse:
    """
    Enrich text with structured data from external providers.

    Args:
        req: Enrichment request

    Returns:
        Enrichment response with subjects, keywords, facts, sources, and metadata
    """
    start_time = time.time()

    # Generate trace_id if not provided
    trace_id = req.trace_id or str(uuid.uuid4())

    # Get hints with defaults
    hints = req.hints or EnrichHints()
    language = hints.language
    enabled_providers = hints.providers

    # Log start
    log_enrichment_start(trace_id, req.text, enabled_providers)

    try:
        # Check if subjects provided in hints (from caller's keyword extraction)
        if hints.subjects and len(hints.subjects) > 0:
            # Use provided subjects instead of extracting
            subjects_info = [{"name": s.name, "type": s.type} for s in hints.subjects]
        else:
            # Extract subjects from text and room context
            subjects_info = extract_subjects(req.text, req.room)

        keywords = extract_keywords(req.text, req.room)

        # Check cache
        cache = get_cache()
        cache_key = None
        cached_result = None

        if subjects_info:
            # Use first subject for cache key
            first_subject = subjects_info[0]
            cache_key = normalize_cache_key(first_subject["type"], first_subject["name"], language)
            cached_result = cache.get(cache_key)

        if cached_result:
            # Return cached result with updated trace_id
            cached_result["trace_id"] = trace_id
            cached_result["meta"]["cache_status"] = "hit"
            latency_ms = (time.time() - start_time) * 1000
            cached_result["meta"]["enrichment_time_ms"] = latency_ms

            log_enrichment_complete(
                trace_id,
                latency_ms,
                "hit",
                cached_result["meta"].get("confidence", 0.0),
                len(cached_result.get("subjects", [])),
            )

            return EnrichResponse(**cached_result)

        # Call providers
        subjects_data, facts, sources = await call_providers(
            subjects_info, language, enabled_providers, trace_id
        )

        # Compute confidence
        confidence = compute_confidence(subjects_data, facts, sources)

        # Determine if partial
        partial = len(subjects_data) == 0 or (len(facts) == 0 and len(sources) == 0)

        # Build response
        latency_ms = (time.time() - start_time) * 1000
        cache_status = "miss"

        response_data = {
            "version": config.SERVICE_VERSION,
            "trace_id": trace_id,
            "subjects": subjects_data,
            "keywords": keywords,
            "facts": facts,
            "sources": sources,
            "meta": {
                "confidence": confidence,
                "cache_status": cache_status,
                "enrichment_time_ms": round(latency_ms, 2),
                "partial": partial,
            },
        }

        # Cache the result
        if cache_key and not partial:
            cache.set(cache_key, response_data)

        # Log completion
        log_enrichment_complete(
            trace_id,
            latency_ms,
            cache_status,
            confidence,
            len(subjects_data),
        )

        return EnrichResponse(**response_data)

    except Exception as e:
        # Always return 200 with partial data, never crash
        latency_ms = (time.time() - start_time) * 1000
        error_msg = str(e)
        log_error(trace_id, error_msg)

        # Return empty enrichment with low confidence
        return EnrichResponse(
            version=config.SERVICE_VERSION,
            trace_id=trace_id,
            subjects=[],
            keywords=extract_keywords(req.text, req.room),
            facts=[],
            sources=[],
            meta={
                "confidence": 0.2,
                "cache_status": "miss",
                "enrichment_time_ms": round(latency_ms, 2),
                "partial": True,
            },
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.ENRICH_HOST, port=config.ENRICH_PORT)

