"""Restrict signup and profile email changes to approved provider domains."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_ALLOWLIST_PATH = (
    Path(__file__).resolve().parent.parent / "resources" / "email_domain_allowlist.conf"
)

_DISALLOWED_MESSAGE = (
    "Only email addresses from approved providers are allowed "
    "(e.g. Gmail, Outlook, Yahoo, iCloud, Rediffmail)"
)


@lru_cache(maxsize=1)
def _load_bundled_allowlist() -> frozenset[str]:
    """Load the bundled provider allowlist (one domain per line)."""
    if not _ALLOWLIST_PATH.is_file():
        logger.warning("Email domain allowlist missing at %s", _ALLOWLIST_PATH)
        return frozenset()
    domains: set[str] = set()
    for line in _ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        domain = line.strip().lower()
        if domain and not domain.startswith("#"):
            domains.add(domain)
    logger.debug("Loaded %d approved email domains", len(domains))
    return frozenset(domains)


def email_domain(email: str) -> str:
    """Return the lowercased domain part of an email address."""
    return email.rsplit("@", 1)[-1].strip().lower()


def get_allowed_email_domains(*, bundled: frozenset[str] | None = None) -> frozenset[str]:
    """Return bundled plus operator-configured approved domains."""
    from server.app.core.config import settings

    base = bundled if bundled is not None else _load_bundled_allowlist()
    extra = {d.strip().lower() for d in settings.email_domain_allowlist_extra if d.strip()}
    return base | extra


def is_allowed_email_domain(
    email: str,
    *,
    bundled: frozenset[str] | None = None,
) -> bool:
    """Return True when the email domain is on the approved provider allowlist."""
    from server.app.core.config import settings

    if not settings.email_domain_allowlist_enabled:
        return True
    domain = email_domain(email)
    return domain in get_allowed_email_domains(bundled=bundled)


def validate_email_domain_allowed(email: str) -> str:
    """Pydantic-friendly validator: raise when the domain is not approved."""
    if not is_allowed_email_domain(email):
        raise ValueError(_DISALLOWED_MESSAGE)
    return email
