"""In-memory LRU cache with TTL support."""

import time
from typing import Optional, Dict, Any
from collections import OrderedDict

try:
    from .config import config
except ImportError:
    from config import config


class LRUCache:
    """Simple LRU cache with TTL support."""

    def __init__(self, max_size: int = 1000, ttl_seconds: Optional[int] = None):
        """
        Initialize LRU cache.

        Args:
            max_size: Maximum number of items in cache
            ttl_seconds: Time-to-live in seconds (None for no expiration)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds or config.ENRICH_CACHE_TTL_SECS
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    def _is_expired(self, timestamp: float) -> bool:
        """Check if entry is expired based on TTL."""
        if self.ttl_seconds is None:
            return False
        return time.time() - timestamp > self.ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or expired
        """
        if key not in self.cache:
            return None

        value, timestamp = self.cache[key]

        # Check if expired
        if self._is_expired(timestamp):
            del self.cache[key]
            return None

        # Move to end (most recently used)
        self.cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Optional TTL override (uses default if None)
        """
        # Remove if exists
        if key in self.cache:
            del self.cache[key]

        # Evict oldest if at capacity
        elif len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)  # Remove oldest (first item)

        # Store with current timestamp
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds
        self.cache[key] = (value, time.time())

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()

    def size(self) -> int:
        """Get current cache size."""
        return len(self.cache)

    def _cleanup_expired(self) -> None:
        """Remove expired entries (called periodically)."""
        current_time = time.time()
        expired_keys = [
            key
            for key, (_, timestamp) in self.cache.items()
            if self._is_expired(timestamp)
        ]
        for key in expired_keys:
            del self.cache[key]


# Global cache instance
_cache: Optional[LRUCache] = None


def get_cache() -> LRUCache:
    """Get or create global cache instance."""
    global _cache
    if _cache is None:
        _cache = LRUCache(max_size=1000, ttl_seconds=config.ENRICH_CACHE_TTL_SECS)
    return _cache


def normalize_cache_key(subject_type: str, name: str, language: str = "en") -> str:
    """
    Normalize cache key from subject information.

    Args:
        subject_type: Type of subject (e.g., "artist", "topic")
        name: Subject name
        language: Language code

    Returns:
        Normalized cache key
    """
    # Normalize: lowercase, strip, replace spaces with underscores
    normalized_name = name.lower().strip().replace(" ", "_")
    return f"{subject_type}:{normalized_name}:{language}"

