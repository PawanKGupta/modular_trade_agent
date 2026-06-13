from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.hash import pbkdf2_sha256

from .config import settings

_PASSLIB_HASH_PREFIXES = (
    "$pbkdf2-sha256$",
    "$2a$",
    "$2b$",
    "$2y$",
    "$bcrypt-sha256$",
)


def is_passlib_password_hash(value: str) -> bool:
    """True when stored value looks like a passlib/bcrypt hash."""
    if not value:
        return False
    return any(value.startswith(p) for p in _PASSLIB_HASH_PREFIXES)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a password against a stored hash.

    Uses PBKDF2-HMAC-SHA256 (via passlib.pbkdf2_sha256), which avoids
    bcrypt's 72-byte limit and backend-specific issues.
    """
    return pbkdf2_sha256.verify(plain, hashed)


def hash_password(plain: str) -> str:
    """
    Hash a password using PBKDF2-HMAC-SHA256 with configured round count.
    """
    return pbkdf2_sha256.using(rounds=settings.password_hash_rounds).hash(plain)


def password_needs_rehash(hashed: str) -> bool:
    """True when hash uses fewer rounds than configured or is legacy bcrypt."""
    if not hashed.startswith("$pbkdf2-sha256$"):
        return True
    try:
        current_rounds = pbkdf2_sha256.get_rounds(hashed)
        return current_rounds < settings.password_hash_rounds
    except Exception:
        return True


def create_jwt_token(
    subject: str,
    *,
    extra: dict[str, Any] | None = None,
    expires_minutes: int | None = None,
    expires_days: int | None = None,
    token_version: int | None = None,
) -> str:
    """Create a signed JWT token."""
    if expires_minutes is None and expires_days is None:
        expires_minutes = settings.jwt_access_minutes

    exp = datetime.now(tz=UTC)
    if expires_minutes is not None:
        exp += timedelta(minutes=expires_minutes)
    if expires_days is not None:
        exp += timedelta(days=expires_days)

    to_encode: dict[str, Any] = {"sub": subject, "exp": exp}
    if token_version is not None:
        to_encode["tv"] = token_version
    if extra:
        to_encode.update(extra)

    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None
