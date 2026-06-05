import hashlib
import secrets
from datetime import timedelta

from src.infrastructure.db.timezone_utils import ist_now

RESET_TOKEN_HOURS = 1
RATE_LIMIT_SECONDS = 60


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def reset_expiry(hours: int = RESET_TOKEN_HOURS):
    return ist_now() + timedelta(hours=hours)


def is_rate_limited(last_sent_at) -> bool:
    if last_sent_at is None:
        return False
    elapsed = (ist_now() - last_sent_at).total_seconds()
    return elapsed < RATE_LIMIT_SECONDS
