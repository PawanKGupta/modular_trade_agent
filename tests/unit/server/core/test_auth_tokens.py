from datetime import timedelta

from server.app.core.auth_tokens import (
    VERIFICATION_TOKEN_HOURS,
    auth_sent_at,
    is_verification_expired,
)
from src.infrastructure.db.timezone_utils import ist_now_naive


def test_is_verification_expired_when_sent_at_missing():
    assert is_verification_expired(None) is True


def test_is_verification_expired_when_within_window():
    assert is_verification_expired(auth_sent_at()) is False


def test_is_verification_expired_when_past_window():
    old = ist_now_naive() - timedelta(hours=VERIFICATION_TOKEN_HOURS + 1)
    assert is_verification_expired(old) is True
