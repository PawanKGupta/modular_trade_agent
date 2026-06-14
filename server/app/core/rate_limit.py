"""Rate limiting for auth endpoints (in-memory default, optional Redis)."""

from __future__ import annotations

import logging
import math
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

    def failure_count(self, key: str, *, window_seconds: int) -> int: ...

    def retry_after_seconds(self, key: str, *, max_attempts: int, window_seconds: int) -> int: ...

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

    def failure_count(self, key: str, *, window_seconds: int) -> int:
        with self._lock:
            return len(self._prune(key, window_seconds, time.monotonic()))

    def retry_after_seconds(self, key: str, *, max_attempts: int, window_seconds: int) -> int:
        with self._lock:
            now = time.monotonic()
            entries = self._prune(key, window_seconds, now)
            if len(entries) < max_attempts:
                return 0
            oldest = min(entries)
            return max(0, int(math.ceil(oldest + window_seconds - now)))

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

    def failure_count(self, key: str, *, window_seconds: int) -> int:
        count = self._client.get(key)
        return int(count) if count else 0

    def retry_after_seconds(self, key: str, *, max_attempts: int, window_seconds: int) -> int:
        count = self._client.get(key)
        if count is None or int(count) < max_attempts:
            return 0
        ttl = self._client.ttl(key)
        if ttl is None or ttl < 0:
            return window_seconds
        return int(ttl)

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


def _rate_limit_key(request: Request, scope: str, identifier: str) -> str:
    return f"rl:{scope}:{get_client_ip(request)}:{identifier}"


def get_failure_count(request: Request, scope: str, identifier: str) -> int:
    """Return recent failed-attempt count for the rate-limit key (0 when disabled)."""
    if not settings.rate_limit_enabled:
        return 0
    key = _rate_limit_key(request, scope, identifier)
    return get_rate_limit_backend().failure_count(
        key, window_seconds=settings.rate_limit_window_seconds
    )


def prelock_warning_message(failure_count: int, *, max_attempts: int) -> str | None:
    """Vague pre-lockout copy — no exact attempt counts (reduces brute-force signal)."""
    if not settings.rate_limit_enabled:
        return None
    warn_after = max(2, max_attempts - 2)
    if failure_count < warn_after:
        return None
    return (
        "Multiple failed login attempts. Your account may be temporarily locked "
        "if this continues."
    )


def login_failure_detail(request: Request, email: str, *, max_attempts: int | None = None) -> str | dict[str, str]:
    """Record a failed login and build a 401 ``detail`` payload (optional vague warning)."""
    email_lower = email.lower()
    limit = max_attempts if max_attempts is not None else settings.rate_limit_login_max
    record_rate_limit_failure(request, "login", email_lower)
    warning = prelock_warning_message(
        get_failure_count(request, "login", email_lower),
        max_attempts=limit,
    )
    if warning:
        return {"message": "Invalid credentials", "warning": warning}
    return "Invalid credentials"


def rate_limit_detail_message() -> str:
    """Fallback user-facing copy when retry timing is unavailable."""
    seconds = settings.rate_limit_window_seconds
    if seconds < 60:
        return "Too many attempts. Please try again shortly."
    minutes = max(1, round(seconds / 60))
    unit = "minute" if minutes == 1 else "minutes"
    return f"Too many attempts. Please try again in about {minutes} {unit}."


def rate_limit_blocked_detail(retry_after_seconds: int) -> dict[str, str | int]:
    """Structured 429 payload with remaining lockout time for client countdown."""
    return {
        "message": "Too many login attempts. Please wait before trying again.",
        "retry_after_seconds": max(0, int(retry_after_seconds)),
    }


def check_rate_limit(request: Request, scope: str, identifier: str, *, max_attempts: int) -> None:
    """Raise 429 if the key is over the failure threshold."""
    if not settings.rate_limit_enabled:
        return
    key = _rate_limit_key(request, scope, identifier)
    backend = get_rate_limit_backend()
    window = settings.rate_limit_window_seconds
    if backend.is_blocked(key, max_attempts=max_attempts, window_seconds=window):
        retry_after = backend.retry_after_seconds(
            key, max_attempts=max_attempts, window_seconds=window
        )
        security_metric_increment(f"rate_limit_blocked:{scope}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate_limit_blocked_detail(retry_after),
            headers={"Retry-After": str(retry_after)},
        )


def record_rate_limit_failure(
    request: Request, scope: str, identifier: str
) -> None:
    """Record a failed auth attempt for rate limiting."""
    if not settings.rate_limit_enabled:
        return
    key = _rate_limit_key(request, scope, identifier)
    get_rate_limit_backend().record_failure(
        key, window_seconds=settings.rate_limit_window_seconds
    )
    security_metric_increment(f"auth_failure:{scope}")


def clear_rate_limit(request: Request, scope: str, identifier: str) -> None:
    """Clear rate limit counter after successful auth."""
    if not settings.rate_limit_enabled:
        return
    key = _rate_limit_key(request, scope, identifier)
    get_rate_limit_backend().clear(key)
