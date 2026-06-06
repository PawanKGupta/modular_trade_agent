from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet, InvalidToken


class MissingDedicatedEncryptionKeyError(ValueError):
    """Raised when storing encrypted DB secrets without a dedicated Fernet env key."""


def _fernet_key_material() -> bytes:
    """
    Symmetric key material for Fernet (URL-safe base64-encoded 32-byte key).

    One Fernet key encrypts broker creds and Razorpay secrets in the DB. Set either env name
    to the same value (only one is required):

      1) APP_DATA_ENCRYPTION_KEY
      2) BROKER_SECRET_KEY (legacy name; same key material as above if you use both names)
      3) Derive from JWT secret (dev / tests only; not for production)
    """
    for env_name in ("APP_DATA_ENCRYPTION_KEY", "BROKER_SECRET_KEY"):
        raw = os.getenv(env_name, "") or ""
        raw = raw.strip()
        if raw:
            return raw.encode("utf-8")
    fallback = os.getenv("JWT_SECRET") or os.getenv("jwt_secret") or "dev-secret-change"
    derived = base64.urlsafe_b64encode(fallback.encode("utf-8").ljust(32, b"_")[:32])
    return derived


# Backward-compatible name used by unit tests and any older imports.
_get_or_create_key = _fernet_key_material


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
            "Set one Fernet key: BROKER_SECRET_KEY or APP_DATA_ENCRYPTION_KEY (same key for "
            "broker + Razorpay DB secrets; only one variable needed). Generate with "
            "cryptography.fernet.Fernet.generate_key()."
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
