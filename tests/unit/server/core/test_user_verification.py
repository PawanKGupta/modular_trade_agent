from types import SimpleNamespace

from server.app.core.user_verification import user_is_email_verified
from src.infrastructure.db.timezone_utils import ist_now


def test_user_is_email_verified_when_timestamp_set():
    user = SimpleNamespace(email_verified_at=ist_now())
    assert user_is_email_verified(user) is True


def test_user_is_email_verified_false_without_timestamp_even_without_token():
    user = SimpleNamespace(email_verified_at=None, email_verification_token_hash=None)
    assert user_is_email_verified(user) is False


def test_user_is_email_verified_false_when_pending_token():
    user = SimpleNamespace(email_verified_at=None, email_verification_token_hash="abc")
    assert user_is_email_verified(user) is False
