"""Rate limiting for auth endpoints (in-memory default, optional Redis)."""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Protocol

from fastapi import HTTPException, Request, status

from .config import settings
from .security_metrics import increment as security_metric_increment

logger = logging.getLogger(__name__)

_SENSITIVE_KEYS = frozenset({"password", "token", "secret", "mpin"})


def get_client_ip(request: Request) -> str:
    """Resolve client IP from proxy headers or direct connection."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


class RateLimitBackend(Protocol):
    def is_blocked(self, key: str, *, max_attempts: int, window_seconds: int) -> bool: ...

    def record_failure(self, key: str, *, window_seconds: int) -> None: ...

    def clear(self, key: str) -> None: ...


class InMemoryRateLimiter:
    """Thread-safe sliding-window counter (single API instance)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._failures: dict[str, list[float]] = defaultdict(list)

    def _prune(self, key: str, window_seconds: int, now: float) -> list[float]:
        cutoff = now - window_seconds
        entries = [t for t in self._failures.get(key, []) if t > cutoff]
        self._failures[key] = entries
        return entries

    def is_blocked(self, key: str, *, max_attempts: int, window_seconds: int) -> bool:
        with self._lock:
            entries = self._prune(key, window_seconds, time.monotonic())
            return len(entries) >= max_attempts

    def record_failure(self, key: str, *, window_seconds: int) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, window_seconds, now)
            self._failures[key].append(now)

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


class RedisRateLimiter:
    """Redis-backed rate limiter for multi-replica deployments."""

    def __init__(self, redis_url: str) -> None:
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("redis package required for RATE_LIMIT_BACKEND=redis") from exc
        self._client = redis.from_url(redis_url, decode_responses=True)

    def is_blocked(self, key: str, *, max_attempts: int, window_seconds: int) -> bool:
        count = self._client.get(key)
        return count is not None and int(count) >= max_attempts

    def record_failure(self, key: str, *, window_seconds: int) -> None:
        pipe = self._client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        pipe.execute()

    def clear(self, key: str) -> None:
        self._client.delete(key)


_backend: RateLimitBackend | None = None


def get_rate_limit_backend() -> RateLimitBackend:
    global _backend
    if _backend is None:
        if settings.rate_limit_backend == "redis" and settings.redis_url:
            _backend = RedisRateLimiter(settings.redis_url)
            logger.info("Rate limiter: Redis backend")
        else:
            _backend = InMemoryRateLimiter()
            logger.info("Rate limiter: in-memory backend")
    return _backend


def reset_rate_limit_backend_for_tests() -> None:
    """Reset singleton (tests only)."""
    global _backend
    _backend = None


def check_rate_limit(request: Request, scope: str, identifier: str, *, max_attempts: int) -> None:
    """Raise 429 if the key is over the failure threshold."""
    if not settings.rate_limit_enabled:
        return
    ip = get_client_ip(request)
    key = f"rl:{scope}:{ip}:{identifier}"
    backend = get_rate_limit_backend()
    if backend.is_blocked(key, max_attempts=max_attempts, window_seconds=settings.rate_limit_window_seconds):
        security_metric_increment(f"rate_limit_blocked:{scope}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later.",
        )


def record_rate_limit_failure(
    request: Request, scope: str, identifier: str
) -> None:
    """Record a failed auth attempt for rate limiting."""
    if not settings.rate_limit_enabled:
        return
    ip = get_client_ip(request)
    key = f"rl:{scope}:{ip}:{identifier}"
    get_rate_limit_backend().record_failure(
        key, window_seconds=settings.rate_limit_window_seconds
    )
    security_metric_increment(f"auth_failure:{scope}")


def clear_rate_limit(request: Request, scope: str, identifier: str) -> None:
    """Clear rate limit counter after successful auth."""
    if not settings.rate_limit_enabled:
        return
    ip = get_client_ip(request)
    key = f"rl:{scope}:{ip}:{identifier}"
    get_rate_limit_backend().clear(key)
