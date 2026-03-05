"""In-memory cache for expensive operations like Royal Road API calls."""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A single cache entry with value and expiration."""
    value: Any
    expires_at: float
    
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class TTLCache:
    """Thread-safe in-memory cache with time-to-live expiration."""
    
    def __init__(self, default_ttl: float = 300.0):
        """
        Initialize the cache.
        
        Args:
            default_ttl: Default time-to-live in seconds (default: 5 minutes)
        """
        self._cache: dict[str, CacheEntry] = {}
        self._lock = Lock()
        self.default_ttl = default_ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache, or None if expired/missing."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._cache[key]
                return None
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set a value in the cache with optional custom TTL."""
        ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + ttl
        with self._lock:
            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)
    
    def delete(self, key: str) -> None:
        """Delete a key from the cache."""
        with self._lock:
            self._cache.pop(key, None)
    
    def clear(self) -> None:
        """Clear all entries from the cache."""
        with self._lock:
            self._cache.clear()
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        removed = 0
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items() 
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
                removed += 1
        return removed
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            total = len(self._cache)
            expired = sum(1 for e in self._cache.values() if e.is_expired())
            return {
                "total_entries": total,
                "expired_entries": expired,
                "active_entries": total - expired,
            }


# Global cache instances
# Royal Road data cache - 10 minute TTL (scraping is expensive)
royal_road_cache = TTLCache(default_ttl=600.0)

# Local book status cache - 30 second TTL (filesystem ops are fast but frequent)
book_status_cache = TTLCache(default_ttl=30.0)


def get_royal_road_cache() -> TTLCache:
    """Get the Royal Road cache instance."""
    return royal_road_cache


def get_book_status_cache() -> TTLCache:
    """Get the book status cache instance."""
    return book_status_cache

