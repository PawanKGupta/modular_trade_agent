import hashlib
import secrets
from datetime import datetime, timedelta

from src.infrastructure.db.timezone_utils import as_ist_aware, ist_now, ist_now_naive

RESET_TOKEN_HOURS = 1
RATE_LIMIT_SECONDS = 60


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def reset_expiry(hours: int = RESET_TOKEN_HOURS) -> datetime:
    """Expiry timestamp stored on user rows (naive IST wall clock)."""
    return ist_now_naive() + timedelta(hours=hours)


def auth_sent_at() -> datetime:
    """Timestamp when an auth email/token was issued (naive IST wall clock)."""
    return ist_now_naive()


def is_rate_limited(last_sent_at: datetime | None) -> bool:
    if last_sent_at is None:
        return False
    elapsed = (ist_now() - as_ist_aware(last_sent_at)).total_seconds()
    return elapsed < RATE_LIMIT_SECONDS


def is_expired(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return True
    return as_ist_aware(expires_at) < ist_now()


def is_still_valid(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return False
    return as_ist_aware(expires_at) > ist_now()
