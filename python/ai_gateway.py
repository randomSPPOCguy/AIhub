"""Python bridge for Project Frank.

This module is embedded into the Rust binary via PyO3. It provides the public
functions invoked from Rust and orchestrates enrichment + LLM calls using
a local Phi-3 model.
"""

from __future__ import annotations

import json
import os
import sys
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List
import sqlite3
import random
from datetime import datetime, timezone, timedelta

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from transformers import logging as transformers_logging
    import torch
    HAS_TRANSFORMERS = True

    # PATCH 3: Suppress transformers warnings and messages
    transformers_logging.set_verbosity_error()
    warnings.filterwarnings("ignore", category=UserWarning)
    warnings.filterwarnings("ignore", category=FutureWarning)
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

except ImportError:
    HAS_TRANSFORMERS = False
    # Log to stderr to avoid UI clutter
    print("⚠️  transformers not installed. Using placeholder responses.", file=sys.stderr, flush=True)

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    print("⚠️  google-generativeai not installed. Gemini unavailable.", file=sys.stderr, flush=True)

from enrichment_pipeline import EnrichmentPipeline

_pipeline = EnrichmentPipeline()

# Global model and tokenizer (loaded once)
# Use a sentinel to track initialization state more reliably
_model = None
_tokenizer = None
_model_initialized = False


@contextmanager
def suppress_stderr():
    """Context manager to suppress stderr output during model loading."""
    original_stderr = sys.stderr
    try:
        sys.stderr = open(os.devnull, 'w')
        yield
    finally:
        sys.stderr.close()
        sys.stderr = original_stderr


def _initialize_model():
    """Initialize the Phi-3 model and tokenizer (lazy loading)."""
    global _model, _tokenizer, _model_initialized

    # Check both the model object and our flag to ensure persistence
    if _model is not None and _model_initialized:
        return  # Already initialized - silent return to avoid UI clutter
    
    # Debug: Check if we're being called multiple times
    if _model is None and _model_initialized:
        # Model was reset - log to stderr (won't appear in TUI)
        print("⚠️  Model was initialized but is now None - Python may have been reinitialized", file=sys.stderr, flush=True)
        _model_initialized = False

    if not HAS_TRANSFORMERS:
        # Log to stderr to avoid cluttering TUI
        print("❌ Transformers not available, using fallback", file=sys.stderr, flush=True)
        return

    try:
        # Only log to stderr during query processing (warmup logs separately)
        # This prevents UI clutter when model loads during a query
        print("🔄 Loading Phi-3 Mini model...", file=sys.stderr, flush=True)

        # Suppress stderr during model loading to hide flash-attention warnings
        with suppress_stderr():
            # Load tokenizer (use cached files after first download)
            try:
                _tokenizer = AutoTokenizer.from_pretrained(
                    "microsoft/Phi-3-mini-4k-instruct",
                    trust_remote_code=True,
                    local_files_only=True  # Use cached files only
                )
            except:
                # First time download
                _tokenizer = AutoTokenizer.from_pretrained(
                    "microsoft/Phi-3-mini-4k-instruct",
                    trust_remote_code=True
                )

            # Set padding token if missing (prevents attention mask warnings)
            if _tokenizer.pad_token is None:
                _tokenizer.pad_token = _tokenizer.eos_token

            # Load model (use cached files after first download)
            try:
                _model = AutoModelForCausalLM.from_pretrained(
                    "microsoft/Phi-3-mini-4k-instruct",
                    trust_remote_code=True,
                    torch_dtype=torch.float16,  # Use FP16 for faster inference
                    device_map="auto",  # Automatically use GPU if available
                    attn_implementation="eager",  # Use eager attention (no flash-attention needed)
                    _attn_implementation="eager",  # Fallback for older transformers versions
                    local_files_only=True  # Use cached files only
                )
            except:
                # First time download
                _model = AutoModelForCausalLM.from_pretrained(
                    "microsoft/Phi-3-mini-4k-instruct",
                    trust_remote_code=True,
                    torch_dtype=torch.float16,
                    device_map="auto",
                    attn_implementation="eager",
                    _attn_implementation="eager"
                )

        _model_initialized = True
        # Log to stderr to avoid UI clutter
        print("✅ Phi-3 model loaded successfully!", file=sys.stderr, flush=True)

    except Exception as e:
        # Errors go to stderr, not stdout (won't appear in TUI prompt box)
        print(f"❌ Error loading Phi-3 model: {e}", file=sys.stderr, flush=True)
        print("Using fallback placeholder responses", file=sys.stderr, flush=True)
        _model = None
        _model_initialized = False


def warmup_model() -> str:
    """Pre-load the model at startup to avoid first-query latency.
    
    This should be called once when the application starts to ensure
    the model is loaded and ready before the first user query.
    Messages are returned as strings (not printed) so Rust can handle display.
    """
    # Temporarily enable stdout for warmup messages (only during startup)
    _initialize_model()
    if _model is not None and _model_initialized:
        return "✅ Phi-3 model pre-loaded and ready"
    elif not HAS_TRANSFORMERS:
        return "⚠️ Model warmup skipped (transformers not available)"
    else:
        return "⚠️ Model warmup failed (check logs for details)"


def _generate_with_phi3(prompt: str, max_tokens: int = 128, temperature: float = 0.7) -> str:
    """Generate text using the local Phi-3 model."""
    _initialize_model()

    if _model is None or _tokenizer is None:
        return "[Phi-3 model not available, using placeholder response]"

    try:
        # Format using Phi-3's chat template
        messages = [
            {"role": "user", "content": prompt}
        ]

        # Apply chat template
        inputs = _tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_tensors="pt"
        )

        # Move to same device as model
        device = next(_model.parameters()).device
        inputs = inputs.to(device)

        # Generate response with timeout to prevent long waits
        with torch.no_grad():
            outputs = _model.generate(
                inputs,
                max_new_tokens=max_tokens,
                max_time=15.0,  # Stop after 15 seconds to keep responses fast
                temperature=temperature,
                top_p=0.9,
                do_sample=True,
                pad_token_id=_tokenizer.eos_token_id
            )

        # Decode and clean response
        response = _tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Remove the input prompt from response
        if prompt in response:
            response = response.split(prompt)[1].strip()

        # Remove any remaining template markers
        response = response.replace("<|assistant|>", "").strip()

        return response

    except Exception as e:
        return f"[Generation error: {str(e)}]"


def _generate_with_gemini(prompt: str, api_key: str, max_tokens: int = 512, temperature: float = 0.7, system_prompt: str = "", model_name: str = "gemini-1.5-pro-latest") -> str:
    """Generate text using Google Gemini API."""
    if not HAS_GEMINI:
        return "[Gemini not available - install google-generativeai]"

    if not api_key:
        return "[Gemini API key not configured]"

    try:
        genai.configure(api_key=api_key)
        target_model = model_name or "gemini-1.5-pro-latest"
        if target_model.startswith("models/"):
            target_model = target_model.split("/", 1)[1]
        model = genai.GenerativeModel(target_model)

        # Prepend system prompt if provided
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        response = model.generate_content(
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )
        )

        # Prefer candidates->content->parts aggregation to avoid response.text quick accessor issues
        try:
            texts = []
            # Walk all candidates and parts to aggregate any text
            if hasattr(response, "candidates") and response.candidates:
                for cand in response.candidates:
                    content = getattr(cand, "content", None)
                    parts = getattr(content, "parts", None) if content else None
                    if parts:
                        for p in parts:
                            t = getattr(p, "text", None)
                            if isinstance(t, str) and t:
                                texts.append(t)
            # Fallback to top-level parts
            if not texts and hasattr(response, "parts") and response.parts:
                for p in response.parts:
                    t = getattr(p, "text", None)
                    if isinstance(t, str) and t:
                        texts.append(t)
            if texts:
                agg = "".join(texts).strip()
                if agg:
                    return agg
            # Try response.text but guard against quick accessor issues
            if hasattr(response, "text"):
                try:
                    t = response.text
                    if isinstance(t, str) and t.strip():
                        return t
                except Exception:
                    pass
            # Try to_dict() deep extraction of any text-like fields as last resort
            to_dict = getattr(response, "to_dict", None)
            if callable(to_dict):
                d = to_dict()
                def extract_all(o):
                    out = []
                    if isinstance(o, str):
                        out.append(o)
                    elif isinstance(o, dict):
                        for v in o.values():
                            out.extend(extract_all(v))
                    elif isinstance(o, list):
                        for v in o:
                            out.extend(extract_all(v))
                    else:
                        txt = getattr(o, "text", None)
                        if isinstance(txt, str):
                            out.append(txt)
                    return out
                collected = [s for s in (s.strip() for s in extract_all(d)) if s]
                if collected:
                    return "\n".join(collected)
        except Exception as e:
            print(f"[Gemini parse warning: {e}]", file=sys.stderr, flush=True)

        # Final fallback with finish_reason for visibility
        try:
            fr = None
            if hasattr(response, "candidates") and response.candidates:
                fr = getattr(response.candidates[0], "finish_reason", None)
            return f"[Gemini returned an empty or unsupported response format; finish_reason={fr}]"
        except Exception:
            return "[Gemini returned an empty or unsupported response format]"

    except Exception as e:
        return f"[Gemini error: {str(e)}]"


@dataclass
class ResponseBundle:
    query: str
    enrichment: List[str]
    llm_response: str = ""

    def format(self) -> str:
        chunks = "\n".join(f"- {item}" for item in self.enrichment) or "No enrichment data."

        sections = [
            "=" * 60,
            "PROJECT FRANK - Phi-3 Response",
            "=" * 60,
            f"\nYour Query: {self.query}\n",
        ]

        if chunks != "No enrichment data.":
            sections.append(f"Enrichment Data:\n{chunks}\n")

        if self.llm_response:
            sections.append(f"AI Response:\n{self.llm_response}\n")

        sections.append("=" * 60)

        return "\n".join(sections)


def _optional_followup() -> str:
    try:
        if random.random() < 0.5:
            return ""
        idx = _read_artist_index_current()
        if not idx:
            return ""
        name = idx.get("artist_name") or "the artist"
        if idx.get("latest_album_tracks"):
            return f"\n\nWant the track list from {name}'s latest album?"
        if idx.get("albums"):
            return f"\n\nWant the full album list for {name}?"
        if idx.get("genres"):
            return f"\n\nWant the genres we have cached for {name}?"
        return ""
    except Exception:
        return ""

def generate_response(query: str, enrichment_data: List[str], clean_output: bool = False) -> str:
    """Generate a response using the local Phi-3 model with enrichment context."""

    # Build context from enrichment data, filtering out errors
    context_items = []
    if enrichment_data and enrichment_data != ["No enrichment data."]:
        for item in enrichment_data:
            # Skip error messages from enrichment
            if isinstance(item, str) and ('"error"' in item.lower() or 'http error' in item.lower()):
                continue
            context_items.append(item)

    context = ""
    if context_items:
        context = "\n\nAdditional context:\n" + "\n".join(context_items)

    # Zero-token quick answer from artist_index (madlib cache)
    qa = _quick_answer_from_index(query)
    if qa:
        extra = _optional_followup()
        final = qa + extra if extra else qa
        return final if clean_output else final

    # Create a conversational prompt for Phi-3
    prompt = f"""You are a friendly and knowledgeable AI assistant. Have natural conversations with users about any topic.
If you receive context information, use it to enhance your response, but don't let missing context stop you from being helpful.
Be conversational, engaging, and provide complete, well-formed responses.

User question: {query}{context}

Respond naturally and helpfully:"""

    try:
        # Generate response using Phi-3
        llm_response = _generate_with_phi3(prompt, max_tokens=256)

        # Return clean response if requested (for web UI)
        if clean_output:
            return llm_response

        # Create response bundle
        bundle = ResponseBundle(
            query=query,
            enrichment=enrichment_data,
            llm_response=llm_response
        )

        return bundle.format()

    except Exception as e:
        # Fallback to placeholder if model fails
        # Log to stderr to avoid UI clutter
        print(f"Error generating LLM response: {e}", file=sys.stderr, flush=True)

        error_msg = f"[Model error: {str(e)}]"

        # Return clean error if requested
        if clean_output:
            return error_msg

        bundle = ResponseBundle(
            query=query,
            enrichment=enrichment_data,
            llm_response=error_msg
        )
        return bundle.format()


def generate_response_with_model(
    query: str,
    enrichment_data: List[str],
    model_type: str,
    model_name: str = "",
    api_key: str = "",
    temperature: float = 0.7,
    max_tokens: int = 512,
    system_prompt: str = "",
    clean_output: bool = False
) -> str:
    """Generate a response using a specified model with enrichment context.

    Args:
        query: User query
        enrichment_data: Context information
        model_type: "phi3", "gemini", "openai", etc.
        api_key: API key for cloud models
        temperature: Generation temperature (0.0-2.0)
        max_tokens: Maximum tokens to generate
        system_prompt: System prompt to prepend
        clean_output: If True, return only the LLM response without formatting
    """
    # Build context from enrichment data, filtering out errors
    context_items = []
    if enrichment_data and enrichment_data != ["No enrichment data."]:
        for item in enrichment_data:
            # Skip error messages from enrichment
            if isinstance(item, str) and ('"error"' in item.lower() or 'http error' in item.lower()):
                continue
            context_items.append(item)

    context = ""
    if context_items:
        context = "\n\nAdditional context:\n" + "\n".join(context_items)

    # Zero-token quick answer from artist_index (madlib cache)
    qa = _quick_answer_from_index(query)
    if qa:
        extra = _optional_followup()
        final = qa + extra if extra else qa
        return final if clean_output else final

    # Create a conversational prompt
    base_prompt = system_prompt if system_prompt else """You are a friendly and knowledgeable AI assistant. Have natural conversations with users about any topic.
If you receive context information, use it to enhance your response, but don't let missing context stop you from being helpful.
Be conversational, engaging, and provide complete, well-formed responses."""

    prompt = f"""{base_prompt}

User question: {query}{context}

Respond naturally and helpfully:"""

    try:
        # Route to the appropriate model
        if model_type == "gemini":
            llm_response = _generate_with_gemini(
                prompt,
                api_key,
                max_tokens,
                temperature,
                system_prompt,
                model_name or "gemini-1.5-pro-latest"
            )
        elif model_type == "phi3":
            llm_response = _generate_with_phi3(prompt, max_tokens, temperature)
        else:
            llm_response = f"[Unknown model type: {model_type}]"

        # Return clean response if requested (for web UI)
        if clean_output:
            return llm_response

        # Create response bundle
        bundle = ResponseBundle(
            query=query,
            enrichment=enrichment_data,
            llm_response=llm_response
        )

        return bundle.format()

    except Exception as e:
        # Fallback to placeholder if model fails
        # Log to stderr to avoid UI clutter
        print(f"Error generating LLM response: {e}", file=sys.stderr, flush=True)

        error_msg = f"[Model error: {str(e)}]"

        # Return clean error if requested
        if clean_output:
            return error_msg

        bundle = ResponseBundle(
            query=query,
            enrichment=enrichment_data,
            llm_response=error_msg
        )
        return bundle.format()


def _normalize_query_py(query: str) -> str:
    s = query.strip().lower()
    # strip punctuation
    for ch in "?!.,;:\\\"":
        s = s.replace(ch, " ")
    # remove common fillers
    for w in [
        "what was", "what is", "what's", "whats",
        "who is", "who's",
        "tell me about", "tell me",
        "can you tell me",
        "more info on", "info on", "more info", "more on",
        "give me", "show me",
        "ok frank", "okay frank", "okay, frank", "ok, frank", "hey frank",
        "ok", "okay", "hey",
        "please",
        "about",
        # music-specific
        "last album", "latest album", "new album",
        "album", "albums",
        "last song", "latest song",
        "song", "songs",
        "single", "track", "tracks",
        "release", "record", "records",
        "just came out", "most recent",
        "that just came out",
    ]:
        s = s.replace(w, " ")
    # strip possessive
    s = s.replace("'s", " ").replace("’s", " ")
    toks = [t for t in s.split() if t]
    # remove leading conversational fillers but preserve "yeah yeah yeahs"
    while toks:
        first = toks[0]
        if first in ("yeah", "yep", "yup", "ok", "okay", "hey"):
            if first == "yeah" and len(toks) >= 3 and toks[1] == "yeah" and toks[2].startswith("yeah"):
                break
            toks = toks[1:]
            continue
        break
    # normalize short digit+'s' like "u2s" -> "u2"
    for i, t in enumerate(toks):
        if len(t) <= 4 and t.endswith("s") and any(c.isdigit() for c in t):
            toks[i] = t[:-1]
    if not toks:
        return ""
    if len(toks) == 1:
        t = toks[0]
        if len(t) > 3 and t.endswith("s"):
            t = t[:-1]
        return t
    return " ".join(toks)


def _read_go_cache(normalized_query: str) -> dict | None:
    """Read cached enrichment produced by Go from SQLite if fresh."""
    try:
        db_path = os.getenv("AIHUB_DB_PATH", "").strip()
        if not db_path:
            return None
        ttl_hours = 24
        try:
            ttl_hours = int(os.getenv("AIHUB_DB_TTL_HOURS", "24"))
        except Exception:
            pass
        max_age = timedelta(hours=max(1, min(ttl_hours, 168)))

        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT metadata, timestamp FROM music_cache WHERE query = ?", (normalized_query,))
            row = cur.fetchone()
            if not row:
                return None
            meta_text, ts = row
            # parse RFC3339 timestamp
            try:
                t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                t = None
            if t is None or datetime.now(timezone.utc) - t > max_age:
                return None
            # wrap metadata for the LLM context
            try:
                meta = json.loads(meta_text)
            except Exception:
                meta = {"raw": meta_text}
            return {
                "source": "go_cache",
                "query": normalized_query,
                "cached_at": ts,
                "metadata": meta,
            }
        finally:
            conn.close()
    except Exception:
        return None


def _is_generic_query(q: str) -> bool:
    s = q.strip().lower()
    for ch in "?!.,;:\\\"":
        s = s.replace(ch, " ")
    stop = {
        "what","whats","what's","who","who's","is","the","a","an","of","for","to","and","or",
        "can","you","tell","me","about","please","new","latest","most","recent","that","just",
        "came","out","song","songs","album","albums","single","track","tracks","release","record",
        "ok","okay","hey","well",
        "do","i","my","your","our","we","people","think","recommend","listen"
    }
    toks = [t for t in s.split() if t]
    core = [t for t in toks if t not in stop]
    return len(core) == 0


def _read_artist_index_current() -> dict | None:
    """Return the most recently updated artist_index row as a dict with parsed JSON."""
    try:
        db_path = os.getenv("AIHUB_DB_PATH", "").strip()
        if not db_path:
            return None
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT artist_name, mbid, genres, albums, latest_album, latest_single, latest_album_tracks, updated_at "
                "FROM artist_index ORDER BY datetime(updated_at) DESC LIMIT 1"
            )
            row = cur.fetchone()
            if not row:
                return None
            artist_name, mbid, genres, albums, latest_album, latest_single, tracks, updated_at = row
            def _parse_json(txt):
                try:
                    return json.loads(txt) if isinstance(txt, str) and txt else None
                except Exception:
                    return None
            return {
                "artist_name": artist_name,
                "mbid": mbid,
                "genres": _parse_json(genres) or [],
                "albums": _parse_json(albums) or [],
                "latest_album": _parse_json(latest_album) or {},
                "latest_single": _parse_json(latest_single) or {},
                "latest_album_tracks": _parse_json(tracks) or [],
                "updated_at": updated_at,
            }
        finally:
            conn.close()
    except Exception:
        return None


def _read_artist_index_by_name(name: str) -> dict | None:
    """Return artist_index row by exact lower-cased artist name if present."""
    try:
        db_path = os.getenv("AIHUB_DB_PATH", "").strip()
        if not db_path or not name:
            return None
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT artist_name, mbid, genres, albums, latest_album, latest_single, latest_album_tracks, updated_at "
                "FROM artist_index WHERE lower(artist_name) = ? LIMIT 1",
                (name.lower(),)
            )
            row = cur.fetchone()
            if not row:
                return None
            artist_name, mbid, genres, albums, latest_album, latest_single, tracks, updated_at = row
            def _parse_json(txt):
                try:
                    return json.loads(txt) if isinstance(txt, str) and txt else None
                except Exception:
                    return None
            return {
                "artist_name": artist_name,
                "mbid": mbid,
                "genres": _parse_json(genres) or [],
                "albums": _parse_json(albums) or [],
                "latest_album": _parse_json(latest_album) or {},
                "latest_single": _parse_json(latest_single) or {},
                "latest_album_tracks": _parse_json(tracks) or [],
                "updated_at": updated_at,
            }
        finally:
            conn.close()
    except Exception:
        return None


def _is_music_intent(q: str) -> bool:
    ql = q.strip().lower()
    keys = [
        "album", "albums", "discography",
        "song", "songs", "single",
        "track", "tracks", "tracklist",
        "genre", "genres",
        "latest", "new", "recent",
        "release", "record"
    ]
    return any(k in ql for k in keys)


def _is_tech_intent(q: str) -> bool:
    ql = q.strip().lower()
    tech = [
        "built on", "built with", "what are you built",
        "programming language", "language is this",
        "framework", "tech stack", "technology stack",
        "backend", "front end", "frontend", "server built",
        "what language are you", "what stack"
    ]
    return any(k in ql for k in tech)


def _quick_answer_from_index(query: str) -> str:
    """
    Zero-token fast path: answer common questions using artist_index cache.
    Returns empty string if no direct answer is available.
    """
    ql = query.strip().lower()
    # Guardrails: only answer zero-token when it's clearly music-related,
    # and avoid technical/about questions that cause hallucinations.
    if _is_tech_intent(ql) or not _is_music_intent(ql):
        return ""
    normalized = _normalize_query_py(query)
    # Require a real entity; do NOT fall back to a random cached artist
    if not normalized or _is_generic_query(normalized):
        return ""
    index = _read_artist_index_by_name(normalized)
    if not index:
        return ""

    if not index:
        return ""

    name = index.get("artist_name") or "the artist"
    genres = index.get("genres") or []
    albums = index.get("albums") or []
    latest = index.get("latest_album") or {}
    single = index.get("latest_single") or {}
    tracks = index.get("latest_album_tracks") or []

    # Combined request: latest album and song/single
    if (("latest" in ql) or ("new" in ql) or ("recent" in ql)) and ("album" in ql) and (("song" in ql) or ("single" in ql)):
        at = latest.get("title", "")
        ad = latest.get("date", "")
        st = single.get("title", "")
        sd = single.get("date", "")
        parts_resp = []
        if at:
            parts_resp.append(f"latest album is '{at}'{f' ({ad})' if ad else ''}")
        if st:
            parts_resp.append(f"latest song is '{st}'{f' ({sd})' if sd else ''}")
        if parts_resp:
            return f"{name}'s " + "; ".join(parts_resp) + "."
        # fall through to individual handlers if not enough info

    if ("album" in ql and any(k in ql for k in ["latest", "new", "recent"])) or ("latest" in ql and "album" in ql):
        title = latest.get("title", "")
        date = latest.get("date", "")
        if title:
            return f"{name}'s latest album is '{title}'{f' ({date})' if date else ''}."
        return f"I don't have a latest album recorded for {name} yet."

    # Latest song/single
    if any(k in ql for k in ["latest", "new", "recent"]) and any(k in ql for k in ["song", "single"]):
        st = single.get("title", "")
        sd = single.get("date", "")
        if st:
            return f"{name}'s latest song is '{st}'{f' ({sd})' if sd else ''}."
        return f"I don't have a latest song recorded for {name} yet."

    if "albums" in ql or "discography" in ql:
        if albums:
            titles = [a.get("title", "") for a in albums if a.get("title")]
            if titles:
                return f"{name}'s albums:\n- " + "\n- ".join(titles)
        return f"I don't have an album list cached for {name} yet."

    if any(k in ql for k in ["tracklist", "tracks", "songs"]):
        if tracks:
            shown = tracks[:30]
            return f"Tracks from {name}'s latest album:\n- " + "\n- ".join(shown)
        return f"I don't have a track list cached for {name}'s latest album yet."

    if "genre" in ql or "style" in ql:
        if genres:
            return f"{name} genres: " + ", ".join(genres[:10])
        return f"I don't have genres cached for {name} yet."

    if "how many song" in ql or "how many tracks" in ql:
        if tracks:
            return f"{name}'s latest album has {len(tracks)} tracks."
        return f"I don't have track count cached for {name}'s latest album yet."

    parts = []
    if latest.get("title"):
        parts.append(f"Latest album: {latest['title']}" + (f" ({latest.get('date','')})" if latest.get("date") else ""))
    if genres:
        parts.append("Genres: " + ", ".join(genres[:10]))
    if albums:
        parts.append(f"Albums cached: {len(albums)}")
    if tracks:
        parts.append(f"Latest album tracks cached: {len(tracks)}")
    if single.get("title"):
        parts.append(f"Latest single: {single['title']}" + (f" ({single.get('date','')})" if single.get("date") else ""))
    if parts:
        return f"{name}: " + " | ".join(parts)
    return ""


def enrich_entity(entity_name: str, entity_type: str = "artist") -> str:
    """Return enrichment payload as a JSON string.

    Prefer Go+SQLite cache when available to reduce tokens and network calls.
    """
    try:
        normalized = _normalize_query_py(entity_name)
        cached = _read_go_cache(normalized) if normalized else None
        if cached:
            return json.dumps(cached, ensure_ascii=False)
    except Exception:
        # fall back silently
        pass

    enriched = _pipeline.enrich(entity_name, entity_type)
    return json.dumps(enriched, ensure_ascii=False)
