"""
Optional Redis-backed JSON store with graceful fallback behavior.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

try:
    import redis
except ImportError:  # pragma: no cover - exercised indirectly by fallback tests
    redis = None  # type: ignore[assignment]

from config import get_settings

logger = logging.getLogger(__name__)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Value of type {type(value)!r} is not JSON serializable")


class RedisStore:
    """Small JSON-oriented wrapper around redis-py."""

    def __init__(self, url: str, prefix: str = "geovision"):
        if redis is None:  # pragma: no cover - guarded by get_redis_store
            raise RuntimeError("redis package is not installed")
        self._prefix = str(prefix or "geovision").strip(":")
        self._client = redis.Redis.from_url(url, decode_responses=True)

    def ping(self) -> bool:
        return bool(self._client.ping())

    def build_key(self, key: str) -> str:
        normalized = str(key or "").lstrip(":")
        return f"{self._prefix}:{normalized}" if normalized else self._prefix

    def get_json(self, key: str) -> Optional[Any]:
        raw_value = self._client.get(self.build_key(key))
        if raw_value is None:
            return None
        return json.loads(raw_value)

    def set_json(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        raw_value = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            default=_json_default,
        )
        namespaced_key = self.build_key(key)
        if ttl_seconds is not None and int(ttl_seconds) > 0:
            self._client.setex(namespaced_key, int(ttl_seconds), raw_value)
        else:
            self._client.set(namespaced_key, raw_value)

    def delete(self, key: str) -> None:
        self._client.delete(self.build_key(key))

    def zadd(self, key: str, mapping: dict[str, float]) -> None:
        if mapping:
            self._client.zadd(self.build_key(key), mapping)

    def zcard(self, key: str) -> int:
        return int(self._client.zcard(self.build_key(key)))

    def zrange(self, key: str, start: int, end: int) -> list[str]:
        values = self._client.zrange(self.build_key(key), start, end)
        return [str(value) for value in values]

    def zrem(self, key: str, *values: str) -> None:
        if values:
            self._client.zrem(self.build_key(key), *values)

    def expire(self, key: str, ttl_seconds: int) -> None:
        if ttl_seconds > 0:
            self._client.expire(self.build_key(key), int(ttl_seconds))

    def geoadd(self, key: str, longitude: float, latitude: float, member: str) -> None:
        self._client.geoadd(
            self.build_key(key),
            (float(longitude), float(latitude), str(member)),
        )

    def geosearch_by_member(
        self,
        key: str,
        member: str,
        radius_m: float,
        limit: Optional[int] = None,
        withdist: bool = True,
    ) -> list[tuple[str, Optional[float]]]:
        kwargs: dict[str, Any] = {
            "name": self.build_key(key),
            "member": str(member),
            "unit": "m",
            "radius": float(radius_m),
            "sort": "ASC",
            "withdist": withdist,
        }
        if limit is not None:
            kwargs["count"] = int(limit)

        raw_results = self._client.geosearch(**kwargs)
        normalized: list[tuple[str, Optional[float]]] = []
        for item in raw_results or []:
            if isinstance(item, dict):
                member_value = item.get("member") or item.get("name") or item.get("value")
                distance_value = item.get("dist") or item.get("distance") or item.get("distance_m")
            elif isinstance(item, (list, tuple)):
                member_value = item[0] if item else None
                distance_value = item[1] if len(item) > 1 else None
            else:
                member_value = item
                distance_value = None

            member_text = str(member_value).strip() if member_value is not None else ""
            if not member_text:
                continue

            try:
                distance_m = float(distance_value) if distance_value is not None else None
            except (TypeError, ValueError):
                distance_m = None
            normalized.append((member_text, distance_m))

        return normalized


_REDIS_STORE_UNINITIALIZED = object()
_redis_store: object | RedisStore | None = _REDIS_STORE_UNINITIALIZED


def get_redis_store() -> Optional[RedisStore]:
    """Return a live RedisStore when configured, otherwise None."""

    global _redis_store
    if _redis_store is not _REDIS_STORE_UNINITIALIZED:
        return _redis_store if isinstance(_redis_store, RedisStore) else None

    settings = get_settings()
    redis_url = str(settings.redis_url or "").strip()
    if not redis_url:
        _redis_store = None
        return None

    if redis is None:
        logger.warning("REDIS_URL is set but redis package is not installed; Redis is disabled.")
        _redis_store = None
        return None

    try:
        store = RedisStore(
            url=redis_url,
            prefix=settings.redis_key_prefix,
        )
        store.ping()
        _redis_store = store
        logger.info("Redis store enabled with prefix '%s'", settings.redis_key_prefix)
        return store
    except Exception as exc:  # pragma: no cover - depends on external redis availability
        logger.warning("Redis unavailable (%s); falling back to local process state.", exc)
        _redis_store = None
        return None


def reset_redis_store_for_tests() -> None:
    """Reset cached singleton state for unit tests."""

    global _redis_store
    _redis_store = _REDIS_STORE_UNINITIALIZED
