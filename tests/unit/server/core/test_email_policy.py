"""Tests for disposable email domain policy."""

from __future__ import annotations

import pytest

from server.app.core import email_policy
from server.app.core.config import settings
from server.app.core.email_policy import (
    email_domain,
    is_disposable_email,
    validate_email_not_disposable,
)


@pytest.fixture(autouse=True)
def _clear_blocklist_cache():
    email_policy._load_blocklist.cache_clear()
    yield
    email_policy._load_blocklist.cache_clear()


def test_email_domain_extracts_lowercase():
    assert email_domain("User@Example.COM") == "example.com"


def test_is_disposable_email_detects_known_domain():
    blocklist = frozenset({"mailinator.com", "tempmail.com"})
    assert is_disposable_email("a@mailinator.com", blocklist=blocklist) is True


def test_is_disposable_email_allows_regular_domain():
    blocklist = frozenset({"mailinator.com"})
    assert is_disposable_email("user@example.com", blocklist=blocklist) is False


def test_is_disposable_email_respects_allowlist(monkeypatch):
    monkeypatch.setattr(settings, "block_disposable_emails", True)
    monkeypatch.setattr(settings, "disposable_email_allowlist", ["mailinator.com"])
    blocklist = frozenset({"mailinator.com"})
    assert is_disposable_email("user@mailinator.com", blocklist=blocklist) is False


def test_is_disposable_email_skips_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "block_disposable_emails", False)
    blocklist = frozenset({"mailinator.com"})
    assert is_disposable_email("user@mailinator.com", blocklist=blocklist) is False


def test_validate_email_not_disposable_raises():
    blocklist = frozenset({"mailinator.com"})
    with pytest.raises(ValueError, match="Disposable email addresses are not allowed"):
        validate_email_not_disposable("user@mailinator.com")


def test_validate_email_not_disposable_passes_regular_email(monkeypatch):
    monkeypatch.setattr(settings, "block_disposable_emails", True)
    monkeypatch.setattr(settings, "disposable_email_allowlist", [])
    assert validate_email_not_disposable("user@example.com") == "user@example.com"


def test_bundled_blocklist_includes_mailinator():
    assert "mailinator.com" in email_policy._load_blocklist()
