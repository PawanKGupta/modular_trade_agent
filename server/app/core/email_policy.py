"""Reject disposable / temporary email domains at registration and profile email change."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_BLOCKLIST_PATH = (
    Path(__file__).resolve().parent.parent
    / "resources"
    / "disposable_email_blocklist.conf"
)


@lru_cache(maxsize=1)
def _load_blocklist() -> frozenset[str]:
    """Load the bundled disposable-domain blocklist (one domain per line)."""
    if not _BLOCKLIST_PATH.is_file():
        logger.warning("Disposable email blocklist missing at %s", _BLOCKLIST_PATH)
        return frozenset()
    domains: set[str] = set()
    for line in _BLOCKLIST_PATH.read_text(encoding="utf-8").splitlines():
        domain = line.strip().lower()
        if domain and not domain.startswith("#"):
            domains.add(domain)
    logger.debug("Loaded %d disposable email domains", len(domains))
    return frozenset(domains)


def email_domain(email: str) -> str:
    """Return the lowercased domain part of an email address."""
    return email.rsplit("@", 1)[-1].strip().lower()


def is_disposable_email(email: str, *, blocklist: frozenset[str] | None = None) -> bool:
    """Return True when the email domain is on the disposable blocklist."""
    from server.app.core.config import settings

    if not settings.block_disposable_emails:
        return False
    domain = email_domain(email)
    if domain in {d.lower() for d in settings.disposable_email_allowlist}:
        return False
    bl = blocklist if blocklist is not None else _load_blocklist()
    return domain in bl


def validate_email_not_disposable(email: str) -> str:
    """Pydantic-friendly validator: raise when the address uses a disposable domain."""
    if is_disposable_email(email):
        raise ValueError("Disposable email addresses are not allowed")
    return email
