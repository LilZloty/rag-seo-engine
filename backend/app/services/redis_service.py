"""
Redis Cache Service with in-memory fallback.
Uses Redis when available (USE_REDIS=true), falls back to TTLCache otherwise.
"""

import json
import time
from functools import wraps
from typing import Any, Callable, Optional, Dict
from app.core.config import settings


class TTLCache:
    """In-memory cache with TTL — used as fallback when Redis is unavailable."""

    def __init__(self, default_ttl: int = 300):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            entry = self._cache[key]
            if time.time() < entry["expires"]:
                return entry["value"]
            del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self._cache[key] = {
            "value": value,
            "expires": time.time() + (ttl or self._default_ttl),
        }

    def delete(self, key: str) -> None:
        self._cache.pop(key, None)

    invalidate = delete  # alias for compatibility

    def invalidate_pattern(self, pattern: str) -> int:
        keys_to_delete = [k for k in self._cache if pattern in k]
        for k in keys_to_delete:
            del self._cache[k]
        return len(keys_to_delete)

    def flush(self) -> None:
        self._cache.clear()


class RedisCache:
    """Redis-backed cache with JSON serialization."""

    def __init__(self, default_ttl: int = 300):
        import redis
        self._client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self._default_ttl = default_ttl
        self._client.ping()

    def get(self, key: str) -> Optional[Any]:
        val = self._client.get(key)
        if val is None:
            return None
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        serialized = json.dumps(value, default=str)
        self._client.setex(key, ttl or self._default_ttl, serialized)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    invalidate = delete  # alias for compatibility

    def invalidate_pattern(self, pattern: str) -> int:
        keys = self._client.keys(f"*{pattern}*")
        if keys:
            return self._client.delete(*keys)
        return 0

    def flush(self) -> None:
        self._client.flushdb()


def create_cache(default_ttl: int = 300):
    """Factory: returns RedisCache if enabled and reachable, else TTLCache."""
    if settings.USE_REDIS:
        try:
            cache = RedisCache(default_ttl=default_ttl)
            return cache
        except Exception:
            pass
    return TTLCache(default_ttl=default_ttl)


# Global cache instances — TTLs scale with environment
_base_ttl = settings.effective_cache_ttl  # 60s dev, 300s staging, 600s prod
cache = create_cache(default_ttl=_base_ttl)
llm_cache = create_cache(default_ttl=_base_ttl * 6)       # 6x base for LLM responses
serp_cache = create_cache(default_ttl=_base_ttl * 3)      # 3x base for SERP data
product_cache = create_cache(default_ttl=_base_ttl)        # 1x base for product data

# Map id() → human name so the @cached decorator can label hit/miss metrics
# by which cache is being used. Keeping this simple: new cache instances
# created ad-hoc by callers will fall back to the generic "custom" label.
_CACHE_NAMES = {
    id(cache): "cache",
    id(llm_cache): "llm_cache",
    id(serp_cache): "serp_cache",
    id(product_cache): "product_cache",
}


def cached(
    ttl: Optional[int] = None,
    cache_obj: Any = None,
    key_prefix: Optional[str] = None,
) -> Callable:
    """Caches a sync function's return value in the given cache.

    Empty/falsy results (None, [], {}, "") are NOT cached — so transient
    failures or missing-credential states don't lock the dashboard into a
    broken-looking view until the TTL expires.

    Args:
        ttl: seconds to cache. Defaults to the cache's own default_ttl.
        cache_obj: cache instance (default: module-level `cache`).
        key_prefix: override auto-generated key prefix (fn.__qualname__).
    """
    def decorator(fn: Callable) -> Callable:
        is_method = "." in fn.__qualname__
        prefix = key_prefix or fn.__qualname__

        @wraps(fn)
        def wrapper(*args, **kwargs):
            c = cache_obj if cache_obj is not None else cache
            key_args = list(args[1:] if is_method else args)
            key_args.extend(f"{k}={kwargs[k]}" for k in sorted(kwargs))
            key = f"{prefix}:" + ":".join(str(a) for a in key_args) if key_args else prefix
            hit = c.get(key)
            # Record hit/miss for observability. Lazy-import to avoid a hard
            # dep cycle if metrics imports ever touch redis_service.
            try:
                from app.core.metrics import metrics as _metrics
                _metrics.record_cache(_CACHE_NAMES.get(id(c), "custom"), hit is not None)
            except Exception:
                pass
            if hit is not None:
                return hit
            result = fn(*args, **kwargs)
            if result:
                c.set(key, result, ttl=ttl)
            return result
        return wrapper
    return decorator
