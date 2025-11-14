"""
Model Loader - Tracks in-memory model loading progress
Separate from model_manager.py which handles downloads.
"""
from __future__ import annotations
import threading
from dataclasses import dataclass, asdict
from typing import Dict, Optional, Literal

LoadingStep = Literal["initializing", "loading_tokenizer", "loading_weights", "optimizing", "ready", "error"]

@dataclass
class LoadingRecord:
    model_id: str
    model_name: str
    step: LoadingStep = "initializing"
    message: str = "Initializing"
    progress_pct: int = 0
    error: Optional[str] = None


class ModelLoaderTracker:
    """
    Tracks in-memory loading progress for local models.
    Thread-safe for FastAPI background tasks.
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._by_id: Dict[str, LoadingRecord] = {}
    
    def start(self, model_id: str, model_name: str):
        """Start tracking loading for a model"""
        with self._lock:
            self._by_id[model_id] = LoadingRecord(
                model_id=model_id,
                model_name=model_name,
                step="initializing",
                message="Initializing",
                progress_pct=5
            )
    
    def update(self, model_id: str, step: LoadingStep, message: str, pct: int):
        """Update loading progress"""
        with self._lock:
            rec = self._by_id.get(model_id)
            if not rec:
                rec = LoadingRecord(model_id=model_id, model_name=model_id)
                self._by_id[model_id] = rec
            rec.step = step
            rec.message = message
            rec.progress_pct = max(0, min(100, pct))
    
    def done(self, model_id: str):
        """Mark model as fully loaded"""
        with self._lock:
            rec = self._by_id.get(model_id)
            if not rec:
                return
            rec.step = "ready"
            rec.message = "Ready"
            rec.progress_pct = 100
    
    def fail(self, model_id: str, err: Exception | str):
        """Mark model loading as failed"""
        with self._lock:
            rec = self._by_id.get(model_id)
            if not rec:
                rec = LoadingRecord(model_id=model_id, model_name=model_id)
                self._by_id[model_id] = rec
            rec.step = "error"
            rec.message = "Error"
            rec.error = str(err)
            rec.progress_pct = 0
    
    def get_all(self):
        """Get all loading records"""
        with self._lock:
            return {k: asdict(v) for k, v in self._by_id.items()}
    
    def get_one(self, model_id: str):
        """Get single loading record"""
        with self._lock:
            rec = self._by_id.get(model_id)
            return asdict(rec) if rec else None


# Global singleton
model_loader = ModelLoaderTracker()

