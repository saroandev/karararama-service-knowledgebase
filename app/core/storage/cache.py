"""
Storage cache management
"""
import time
import logging
from typing import Optional, Any, Dict
from app.core.storage.base import BaseCacheManager

logger = logging.getLogger(__name__)


class StorageCache(BaseCacheManager):
    """In-memory cache for storage operations"""

    def __init__(self, ttl: int = 300, max_size: int = 100):
        """
        Initialize cache manager

        Args:
            ttl: Time to live in seconds (default: 5 minutes)
            max_size: Maximum number of cached items
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ttl = ttl
        self._max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            return None

        entry = self._cache[key]

        # Check if expired
        if time.time() - entry['timestamp'] > self._ttl:
            del self._cache[key]
            logger.debug(f"Cache expired for key: {key}")
            return None

        logger.debug(f"Cache hit for key: {key}")
        return entry['data']

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional custom TTL for this entry
        """
        # Check cache size limit
        if len(self._cache) >= self._max_size:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug(f"Cache full, removed oldest entry: {oldest_key}")

        self._cache[key] = {
            'data': value,
            'timestamp': time.time(),
            'ttl': ttl or self._ttl
        }
        logger.debug(f"Cache set for key: {key}")

    def invalidate(self, pattern: str) -> None:
        """
        Invalidate cache entries matching pattern

        Args:
            pattern: Pattern to match (e.g., document_id)
        """
        keys_to_remove = [
            key for key in self._cache
            if pattern in key
        ]

        for key in keys_to_remove:
            del self._cache[key]
            logger.debug(f"Cache invalidated for key: {key}")

        if keys_to_remove:
            logger.info(f"Invalidated {len(keys_to_remove)} cache entries for pattern: {pattern}")

    def clear(self) -> None:
        """Clear all cache"""
        size = len(self._cache)
        self._cache.clear()
        logger.info(f"Cleared {size} entries from cache")

    def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dictionary with cache stats
        """
        return {
            'size': len(self._cache),
            'max_size': self._max_size,
            'ttl': self._ttl,
            'keys': list(self._cache.keys())
        }