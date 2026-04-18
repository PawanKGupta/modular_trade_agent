from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet, InvalidToken


class MissingDedicatedEncryptionKeyError(ValueError):
    """Raised when DB secret persistence lacks APP_DATA_ENCRYPTION_KEY or BROKER_SECRET_KEY."""


def _fernet_key_material() -> bytes:
    """
    Symmetric key material for Fernet (URL-safe base64-encoded 32-byte key).

    Priority:
      1) APP_DATA_ENCRYPTION_KEY — preferred dedicated key for all at-rest secrets
      2) BROKER_SECRET_KEY — backward compatible alias used for broker credentials
      3) Derive from JWT secret (dev / tests only; not for production payment or broker secrets)
    """
    for env_name in ("APP_DATA_ENCRYPTION_KEY", "BROKER_SECRET_KEY"):
        raw = os.getenv(env_name, "") or ""
        raw = raw.strip()
        if raw:
            return raw.encode("utf-8")
    fallback = os.getenv("JWT_SECRET") or os.getenv("jwt_secret") or "dev-secret-change"
    derived = base64.urlsafe_b64encode(fallback.encode("utf-8").ljust(32, b"_")[:32])
    return derived


def encryption_uses_dedicated_env_key() -> bool:
    """True when a non-JWT-derived Fernet key is configured (production-style)."""
    return bool(
        (os.getenv("APP_DATA_ENCRYPTION_KEY", "") or "").strip()
        or (os.getenv("BROKER_SECRET_KEY", "") or "").strip()
    )


def assert_db_secret_encryption_allowed() -> None:
    """
    Require a dedicated env Fernet key before writing payment or broker secrets to the database.

    Prevents relying on the JWT-derived dev key for ciphertext that must survive restarts.
    """
    if not encryption_uses_dedicated_env_key():
        raise MissingDedicatedEncryptionKeyError(
            "Set APP_DATA_ENCRYPTION_KEY (preferred) or BROKER_SECRET_KEY to a Fernet key "
            "(generate via cryptography.fernet.Fernet.generate_key) before storing encrypted "
            "API secrets in the database."
        )


def get_fernet() -> Fernet:
    return Fernet(_fernet_key_material())


def encrypt_blob(data: bytes) -> bytes:
    return get_fernet().encrypt(data)


def decrypt_blob(token: bytes) -> bytes | None:
    try:
        return get_fernet().decrypt(token)
    except (InvalidToken, TypeError):
        return None
