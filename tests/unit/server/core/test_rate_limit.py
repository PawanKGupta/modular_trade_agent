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


def test_clear_rate_limit_after_success(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_login_max", 2)
    req = _request()
    rate_limit.record_rate_limit_failure(req, "login", "a@b.com")
    rate_limit.clear_rate_limit(req, "login", "a@b.com")
    rate_limit.check_rate_limit(req, "login", "a@b.com", max_attempts=2)
