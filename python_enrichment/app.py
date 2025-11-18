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
    from .providers.multi_source_orchestrator import (
        enrich_artist_multi_source,
        enrich_music_entity,
        set_trace_id as set_orchestrator_trace_id
    )
    from .providers.wikipedia_enhanced import (
        get_wikipedia_page,
        is_music_related_wikipedia,
        set_trace_id as set_wikipedia_enhanced_trace_id
    )
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
    from providers.multi_source_orchestrator import (
        enrich_artist_multi_source,
        enrich_music_entity,
        set_trace_id as set_orchestrator_trace_id
    )
    from providers.wikipedia_enhanced import (
        get_wikipedia_page,
        is_music_related_wikipedia,
        set_trace_id as set_wikipedia_enhanced_trace_id
    )

app = FastAPI(title="AIhub Enrichment Service", version=config.SERVICE_VERSION)


def extract_subjects(text: str, room: Optional[RoomContext] = None) -> List[Dict[str, str]]:
    """
    Extract potential subjects from text and room context.

    MUSIC-FIRST APPROACH:
    - When extracting subjects, assume music context (artist/band names)
    - Prioritize artist names over generic topics
    - Default to "artist" type unless other context detected

    Args:
        text: Input text
        room: Optional room context

    Returns:
        List of subject dictionaries with name and type
    """
    subjects = []

    # Add subjects from room context (music-specific)
    if room and room.now_playing:
        if room.now_playing.artist:
            subjects.append({"name": room.now_playing.artist, "type": "artist"})
        if room.now_playing.track:
            subjects.append({"name": room.now_playing.track, "type": "track"})

    # Extract from question patterns
    text_lower = text.lower()

    # Detect entity type from context keywords
    is_album_query = any(word in text_lower for word in ["album", "record", "lp", "ep", "release"])
    is_track_query = any(word in text_lower for word in ["song", "track", "single", "tune"])

    # Pattern 1a: "what was/is/whats [ARTIST]'s latest/recent/newest album/song?"
    # Handles: "what was eminem's latest album", "whats eminems most recent album", etc.
    latest_match = re.search(r'(?:what\s+(?:was|is)|whats?)\s+([^\']+?)(?:\'s|s)\s+(?:latest|recent|newest|most\s+recent|last)\s+(album|song|track|record)', text_lower)
    if latest_match:
        artist_name = latest_match.group(1).strip()
        entity_type_query = latest_match.group(2).strip()
        # Clean up common words
        artist_name = re.sub(r'\b(the|a|an)\b', '', artist_name).strip()
        if artist_name and artist_name not in [s["name"].lower() for s in subjects]:
            # This is asking about an artist's discography
            subjects.append({"name": artist_name.title(), "type": "artist"})

    # Pattern 1b: "who is [ENTITY]?" or "what is [ENTITY]?"
    who_match = re.search(r'(?:who|what)(?:\'s| is) ([^?]+)', text_lower)
    if who_match and not latest_match:  # Don't duplicate if latest_match found
        entity = who_match.group(1).strip()
        # Clean up common words
        entity = re.sub(r'\b(the|a|an)\b', '', entity).strip()
        if entity and entity not in [s["name"].lower() for s in subjects]:
            # Determine type based on context
            if is_album_query:
                entity_type = "album"
            elif is_track_query:
                entity_type = "track"
            else:
                # Default to artist (MUSIC-FIRST)
                entity_type = "artist"

            subjects.append({"name": entity.title(), "type": entity_type})

    # Pattern 2: "tell me about [ENTITY]" or "what about [ENTITY]"
    about_match = re.search(r'(?:tell me about|what about|about) ([^?]+)', text_lower)
    if about_match and not who_match:  # Don't duplicate
        entity = about_match.group(1).strip()
        entity = re.sub(r'\s+(the|a|an)\s+', ' ', entity).strip()
        if entity and entity not in [s["name"].lower() for s in subjects]:
            # Determine type based on context
            if is_album_query:
                entity_type = "album"
            elif is_track_query:
                entity_type = "track"
            else:
                # Default to artist (MUSIC-FIRST)
                entity_type = "artist"

            subjects.append({"name": entity.title(), "type": entity_type})

    # Pattern 3: Look for quoted strings (usually song/album titles)
    quoted = re.findall(r'"([^"]+)"', text)
    for quote in quoted:
        if quote not in [s["name"] for s in subjects]:
            # Quoted strings are usually track or album names
            if is_album_query:
                subjects.append({"name": quote, "type": "album"})
            else:
                subjects.append({"name": quote, "type": "track"})

    # Pattern 4: Look for capitalized proper nouns (multi-word names)
    # This catches things like "Wet Leg", "Poe", "Radiohead"
    if not subjects:
        capitalized = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text)
        for cap in capitalized:
            if cap.lower() not in ['i', 'bot'] and cap not in [s["name"] for s in subjects]:
                # Default to artist (MUSIC-FIRST)
                subjects.append({"name": cap, "type": "artist"})

    # If still no subjects found, use key content words (skip question words)
    if not subjects and text:
        # Remove common question words and get meaningful terms
        cleaned = re.sub(r'\b(who|what|where|when|why|how|is|are|was|were|the|a|an|about|tell|me)\b', '', text_lower)
        words = cleaned.split()
        meaningful = [w for w in words if len(w) > 2][:3]
        if meaningful:
            # Default to artist (MUSIC-FIRST)
            subjects.append({"name": " ".join(meaningful).title(), "type": "artist"})

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

    MUSIC-FIRST APPROACH:
    - For music entities (artists, albums, tracks), use multi-source orchestrator
    - Multi-source orchestrator calls MusicBrainz FIRST, then uses Wikipedia metadata from MB
    - This ensures correct Wikipedia pages (e.g., "Radiohead" not "Radio_head")

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
    set_orchestrator_trace_id(trace_id)
    set_wikipedia_enhanced_trace_id(trace_id)

    for subject_info in subjects:
        subject_name = subject_info["name"]
        subject_type = subject_info["type"]

        # MUSIC-FIRST: Use multi-source orchestrator for music entities
        if subject_type in ["artist", "album", "track"] and config.ENRICH_MUSICBRAINZ_ENABLED:
            try:
                # Use multi-source orchestrator (MusicBrainz → Wikipedia flow)
                orchestrator_result = await enrich_artist_multi_source(subject_name, trace_id)

                if orchestrator_result:
                    # Extract subject data
                    subject_result = {
                        "name": orchestrator_result.get("name", subject_name),
                        "type": subject_type,
                        "ids": orchestrator_result.get("ids", {}),
                        "urls": orchestrator_result.get("urls", {}),
                        "metadata": orchestrator_result.get("metadata", {}),
                    }

                    subjects_data.append(subject_result)

                    # Add facts from orchestrator
                    orchestrator_facts = orchestrator_result.get("facts", [])
                    facts.extend(orchestrator_facts)

                    # Add sources from orchestrator
                    orchestrator_sources = orchestrator_result.get("sources", [])
                    sources.extend(orchestrator_sources)

                    continue  # Skip to next subject (orchestrator handled everything)

                else:
                    # MusicBrainz not found - check if Wikipedia has disambiguation
                    if config.ENRICH_WIKIPEDIA_ENABLED:
                        wiki_data = await get_wikipedia_page(subject_name, language)

                        if wiki_data and wiki_data.get("is_disambiguation"):
                            # Return disambiguation response
                            subject_result = {
                                "name": subject_name,
                                "type": "disambiguation",
                                "requires_clarification": True,
                                "disambiguation_options": wiki_data.get("disambiguation_options", []),
                                "music_options": wiki_data.get("music_options", []),
                                "has_music_options": wiki_data.get("has_music_options", False),
                                "prompt": _create_disambiguation_prompt(subject_name, wiki_data.get("disambiguation_options", [])),
                            }

                            subjects_data.append(subject_result)

                            # Add facts explaining disambiguation needed
                            facts.append(f"Multiple meanings found for '{subject_name}'. User clarification needed.")

                            sources.append({
                                "provider": "wikipedia",
                                "url": wiki_data.get("url", ""),
                                "title": wiki_data.get("title", subject_name),
                                "language": language,
                                "type": "disambiguation"
                            })

                            continue  # Skip to next subject

            except Exception as e:
                log_error(trace_id, f"Multi-source orchestrator error for {subject_name}: {str(e)}")
                # Fall through to legacy provider approach

        # Legacy approach for non-music entities or if orchestrator failed
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


def _create_disambiguation_prompt(subject_name: str, options: List[Dict[str, Any]]) -> str:
    """
    Create user-friendly disambiguation prompt.

    Args:
        subject_name: The subject name
        options: Disambiguation options

    Returns:
        Disambiguation prompt string
    """
    if not options:
        return f"Multiple meanings found for '{subject_name}'."

    # Get top 3 options
    top_options = options[:3]
    labels = [opt.get("label", "") for opt in top_options if opt.get("label")]

    if len(labels) == 0:
        return f"Multiple meanings found for '{subject_name}'."
    elif len(labels) == 1:
        return f"Did you mean {labels[0]}?"
    elif len(labels) == 2:
        return f"Did you mean {labels[0]} or {labels[1]}?"
    else:
        return f"Did you mean {', '.join(labels[:-1])}, or {labels[-1]}?"


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

