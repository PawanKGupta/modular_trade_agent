"""Tests for auth rate limiting."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from server.app.core import rate_limit
from server.app.core.config import settings


@pytest.fixture(autouse=True)
def reset_backend():
    rate_limit.reset_rate_limit_backend_for_tests()
    yield
    rate_limit.reset_rate_limit_backend_for_tests()


def _request(ip: str = "203.0.113.1"):
    req = MagicMock()
    req.headers = {"X-Forwarded-For": ip}
    req.client = MagicMock(host=ip)
    return req


def test_login_blocked_after_max_failures(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_login_max", 3)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 900)
    req = _request()
    for _ in range(3):
        rate_limit.record_rate_limit_failure(req, "login", "user@example.com")
    with pytest.raises(HTTPException) as exc:
        rate_limit.check_rate_limit(req, "login", "user@example.com", max_attempts=3)
    assert exc.value.status_code == 429
    detail = exc.value.detail
    assert isinstance(detail, dict)
    assert detail["message"] == "Too many login attempts. Please wait before trying again."
    assert detail["retry_after_seconds"] > 0
    assert exc.value.headers["Retry-After"] == str(detail["retry_after_seconds"])


def test_retry_after_seconds_sliding_window(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    backend = rate_limit.InMemoryRateLimiter()
    key = "rl:login:203.0.113.1:user@example.com"
    base = 10_000.0
    times = iter([base, base + 1.5])
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: next(times))
    backend.record_failure(key, window_seconds=900)
    backend.record_failure(key, window_seconds=900)
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: base + 100.0)
    retry_after = backend.retry_after_seconds(key, max_attempts=2, window_seconds=900)
    assert retry_after == 800


def test_rate_limit_detail_message_short_window(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 45)
    assert rate_limit.rate_limit_detail_message() == "Too many attempts. Please try again shortly."


def test_rate_limit_detail_message_one_minute(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 60)
    assert rate_limit.rate_limit_detail_message() == "Too many attempts. Please try again in about 1 minute."


def test_prelock_warning_not_shown_for_early_failures(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    assert rate_limit.prelock_warning_message(1, max_attempts=5) is None
    assert rate_limit.prelock_warning_message(2, max_attempts=5) is None


def test_prelock_warning_shown_near_lockout(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    msg = rate_limit.prelock_warning_message(3, max_attempts=5)
    assert msg is not None
    assert "temporarily locked" in msg
    assert "3" not in msg
    assert "2" not in msg


def test_login_failure_detail_adds_warning_after_threshold(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_login_max", 5)
    req = _request()
    email = "user@example.com"
    assert rate_limit.login_failure_detail(req, email) == "Invalid credentials"
    assert rate_limit.login_failure_detail(req, email) == "Invalid credentials"
    detail = rate_limit.login_failure_detail(req, email)
    assert isinstance(detail, dict)
    assert detail["message"] == "Invalid credentials"
    assert "temporarily locked" in detail["warning"]


def test_clear_rate_limit_after_success(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_login_max", 2)
    req = _request()
    rate_limit.record_rate_limit_failure(req, "login", "a@b.com")
    rate_limit.clear_rate_limit(req, "login", "a@b.com")
    rate_limit.check_rate_limit(req, "login", "a@b.com", max_attempts=2)
