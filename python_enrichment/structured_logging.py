"""Structured logging helpers for enrichment service."""

import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("enrichment")
handler = logging.StreamHandler()
formatter = logging.Formatter("%(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def _log(level: str, event: str, payload: Dict[str, Any]) -> None:
    entry = {
        "ts": time.time(),
        "level": level,
        "event": event,
        **payload,
    }
    logger.log(logging.INFO if level == "info" else logging.ERROR, json.dumps(entry))


def log_enrichment_start(trace_id: str, text: str, providers: list[str]) -> None:
    _log(
        "info",
        "enrich_start",
        {"trace_id": trace_id, "text_preview": text[:80], "providers": providers},
    )


def log_enrichment_complete(
    trace_id: str,
    latency_ms: float,
    cache_status: str,
    confidence: float,
    subjects_count: int,
) -> None:
    _log(
        "info",
        "enrich_complete",
        {
            "trace_id": trace_id,
            "latency_ms": round(latency_ms, 2),
            "cache_status": cache_status,
            "confidence": confidence,
            "subjects_count": subjects_count,
        },
    )


def log_error(trace_id: Optional[str], message: str) -> None:
    _log("error", "enrich_error", {"trace_id": trace_id, "error": message})


def log_provider_call(
    trace_id: str,
    provider: str,
    latency_ms: float,
    success: bool,
    error: Optional[str] = None,
) -> None:
    payload: Dict[str, Any] = {
        "trace_id": trace_id,
        "provider": provider,
        "latency_ms": round(latency_ms, 2),
        "success": success,
    }
    if error:
        payload["error"] = error
    _log("info" if success else "error", "provider_call", payload)
