"""TOTP MFA helpers for Rebound account login."""

from __future__ import annotations

import hashlib
import json
import secrets

import pyotp

from .crypto import decrypt_blob, encrypt_blob


def generate_totp_secret() -> str:
    """Return a base32 TOTP secret for provisioning."""
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str, issuer: str = "Rebound") -> str:
    """Provisioning URI for authenticator apps."""
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, code: str, *, valid_window: int = 1) -> bool:
    """Verify a 6-digit TOTP code."""
    if not secret or not code:
        return False
    normalized = code.strip().replace(" ", "")
    if not normalized.isdigit() or len(normalized) != 6:
        return False
    return pyotp.TOTP(secret).verify(normalized, valid_window=valid_window)


def encrypt_mfa_secret(secret: str) -> bytes:
    return encrypt_blob(secret.encode("utf-8"))


def decrypt_mfa_secret(encrypted: bytes | None) -> str | None:
    if not encrypted:
        return None
    raw = decrypt_blob(encrypted)
    if raw is None:
        return None
    return raw.decode("utf-8")


def generate_backup_codes(count: int = 8) -> list[str]:
    """Generate one-time backup codes."""
    return [secrets.token_hex(4).upper() for _ in range(count)]


def hash_backup_codes(codes: list[str]) -> list[str]:
    return [hashlib.sha256(c.encode("utf-8")).hexdigest() for c in codes]


def verify_backup_code(code: str, hashed_codes: list[str]) -> int | None:
    """
    Verify a backup code against stored hashes.

    Returns:
        Index of matched hash for removal, or None if invalid.
    """
    normalized = code.strip().replace(" ", "").upper()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    for i, h in enumerate(hashed_codes):
        if h == digest:
            return i
    return None


def backup_codes_to_json(hashed: list[str]) -> str:
    return json.dumps(hashed)


def backup_codes_from_json(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return list(data) if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []
