from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet, InvalidToken


def _get_or_create_key() -> bytes:
    """
    Derive or generate a symmetric key for local encryption.
    Priority:
      1) BROKER_SECRET_KEY (base64 urlsafe 32 bytes)
      2) Derive from APP_SECRET_KEY/JWT secret (not as strong; for dev only)
      3) Generate ephemeral key (non-persistent; tests)
    """
    env_key = os.getenv("BROKER_SECRET_KEY")
    if env_key:
        return env_key.encode("utf-8")
    fallback = os.getenv("JWT_SECRET") or os.getenv("jwt_secret") or "dev-secret-change"
    # Derive a 32-byte urlsafe base64 key from fallback
    derived = base64.urlsafe_b64encode(fallback.encode("utf-8").ljust(32, b"_")[:32])
    return derived


def get_fernet() -> Fernet:
    return Fernet(_get_or_create_key())


def encrypt_blob(data: bytes) -> bytes:
    return get_fernet().encrypt(data)


def decrypt_blob(token: bytes) -> bytes | None:
    try:
        return get_fernet().decrypt(token)
    except (InvalidToken, TypeError):
        return None
