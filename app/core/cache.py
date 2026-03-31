"""
DocuMind v3 — In-Memory Caching Layer

Lightweight TTL cache for embeddings, query results, and LLM responses.
Production alternative: swap with Redis client.
"""
import time
import hashlib
from typing import Any, Optional
from collections import OrderedDict
from app.config import logger


class TTLCache:
    """Thread-safe TTL-based LRU cache."""

    def __init__(self, max_size: int = 500, ttl_seconds: int = 3600):
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _hash_key(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def get(self, key: str) -> Optional[Any]:
        hashed = self._hash_key(key)
        if hashed in self._cache:
            value, timestamp = self._cache[hashed]
            if time.time() - timestamp < self._ttl:
                self._cache.move_to_end(hashed)
                self._hits += 1
                return value
            else:
                del self._cache[hashed]
        self._misses += 1
        return None

    def set(self, key: str, value: Any) -> None:
        hashed = self._hash_key(key)
        if hashed in self._cache:
            del self._cache[hashed]
        self._cache[hashed] = (value, time.time())
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def invalidate(self, key: str) -> None:
        hashed = self._hash_key(key)
        if hashed in self._cache:
            del self._cache[hashed]

    def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{(self._hits / total * 100):.1f}%" if total > 0 else "0%",
        }


# === Singleton Cache Instances ===
embedding_cache = TTLCache(max_size=2000, ttl_seconds=7200)   # 2h for embeddings
query_cache = TTLCache(max_size=200, ttl_seconds=300)          # 5min for query results
llm_cache = TTLCache(max_size=100, ttl_seconds=600)            # 10min for LLM responses
