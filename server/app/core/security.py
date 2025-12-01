from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.hash import pbkdf2_sha256

from .config import settings


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a password against a stored hash.

    Uses PBKDF2-HMAC-SHA256 (via passlib.pbkdf2_sha256), which avoids
    bcrypt's 72-byte limit and backend-specific issues.
    """
    return pbkdf2_sha256.verify(plain, hashed)


def hash_password(plain: str) -> str:
    """
    Hash a password using PBKDF2-HMAC-SHA256.

    This avoids bcrypt-specific limitations while remaining secure for
    application-level password storage.
    """
    return pbkdf2_sha256.hash(plain)


def create_jwt_token(
    subject: str,
    *,
    extra: dict[str, Any] | None = None,
    expires_minutes: int | None = None,
    expires_days: int | None = None,
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
    if extra:
        to_encode.update(extra)

    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None
