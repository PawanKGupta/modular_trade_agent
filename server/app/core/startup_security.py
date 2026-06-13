"""Production startup guards for secrets and environment."""

from __future__ import annotations

import logging
import os
import sys

from .config import settings
from .crypto import encryption_uses_dedicated_env_key

logger = logging.getLogger(__name__)

_DEFAULT_JWT_SECRET = "dev-secret-change"


def is_production() -> bool:
    """True when ENV or APP_ENV is set to production."""
    for name in ("ENV", "APP_ENV"):
        val = (os.getenv(name) or "").strip().lower()
        if val == "production":
            return True
    return False


def validate_production_secrets() -> None:
    """
    Fail fast in production when default or missing security secrets are detected.

    Raises:
        SystemExit: When required production secrets are missing or insecure.
    """
    if not is_production():
        return

    errors: list[str] = []
    if settings.jwt_secret == _DEFAULT_JWT_SECRET:
        errors.append("JWT_SECRET must be set to a strong random value in production")
    if not encryption_uses_dedicated_env_key():
        errors.append(
            "Set APP_DATA_ENCRYPTION_KEY or BROKER_SECRET_KEY (Fernet key) in production"
        )

    if errors:
        for msg in errors:
            logger.critical("Production security check failed: %s", msg)
        sys.exit(1)
