from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.hash import bcrypt

from .config import settings


def _truncate_for_bcrypt(password: str) -> str:
    # bcrypt limits to 72 bytes; truncate to avoid backend errors
    try:
        b = password.encode("utf-8")[:72]
        return b.decode("utf-8", errors="ignore")
    except Exception:
        # Fallback best-effort
        return password[:72]


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return bcrypt.hash(_truncate_for_bcrypt(plain))


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
