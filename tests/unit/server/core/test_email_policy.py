"""Tests for approved email domain allowlist policy."""

from __future__ import annotations

import pytest

from server.app.core import email_policy
from server.app.core.config import settings
from server.app.core.email_policy import (
    email_domain,
    get_allowed_email_domains,
    is_allowed_email_domain,
    validate_email_domain_allowed,
)

_BUNDLED = frozenset({"gmail.com", "outlook.com", "yahoo.com", "rediffmail.com"})


@pytest.fixture(autouse=True)
def _allowlist_enabled(monkeypatch):
    monkeypatch.setattr(settings, "email_domain_allowlist_enabled", True)
    monkeypatch.setattr(settings, "email_domain_allowlist_extra", [])


@pytest.fixture(autouse=True)
def _clear_allowlist_cache():
    email_policy._load_bundled_allowlist.cache_clear()
    yield
    email_policy._load_bundled_allowlist.cache_clear()


def test_email_domain_extracts_lowercase():
    assert email_domain("User@Gmail.COM") == "gmail.com"


def test_is_allowed_email_domain_accepts_gmail():
    assert is_allowed_email_domain("user@gmail.com", bundled=_BUNDLED) is True


def test_is_allowed_email_domain_rejects_unknown_provider():
    assert is_allowed_email_domain("yayic93006@aratrin.com", bundled=_BUNDLED) is False


def test_is_allowed_email_domain_rejects_disposable_provider():
    assert is_allowed_email_domain("user@mailinator.com", bundled=_BUNDLED) is False


def test_is_allowed_email_domain_accepts_extra_configured_domain(monkeypatch):
    monkeypatch.setattr(settings, "email_domain_allowlist_extra", ["company.com"])
    assert is_allowed_email_domain("user@company.com", bundled=_BUNDLED) is True


def test_is_allowed_email_domain_skips_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "email_domain_allowlist_enabled", False)
    assert is_allowed_email_domain("user@aratrin.com", bundled=_BUNDLED) is True


def test_validate_email_domain_allowed_raises_for_unapproved():
    with pytest.raises(ValueError, match="Only email addresses from approved providers"):
        validate_email_domain_allowed("user@aratrin.com")


def test_validate_email_domain_allowed_passes_gmail(monkeypatch):
    monkeypatch.setattr(settings, "email_domain_allowlist_extra", [])
    assert validate_email_domain_allowed("user@gmail.com") == "user@gmail.com"


def test_bundled_allowlist_includes_gmail_and_rediffmail():
    bundled = email_policy._load_bundled_allowlist()
    assert "gmail.com" in bundled
    assert "rediffmail.com" in bundled


def test_get_allowed_email_domains_merges_extra(monkeypatch):
    monkeypatch.setattr(settings, "email_domain_allowlist_extra", ["corp.in"])
    allowed = get_allowed_email_domains(bundled=_BUNDLED)
    assert "corp.in" in allowed
    assert "gmail.com" in allowed
