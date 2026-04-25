"""Tests for Razorpay credential resolution (env vs encrypted DB)."""

from types import SimpleNamespace

import pytest

from server.app.core import crypto as crypto_mod
from src.application.services import razorpay_credentials as rz


@pytest.fixture
def fake_settings(monkeypatch):
    st = SimpleNamespace(
        razorpay_use_db_only=False,
        razorpay_key_id="",
        razorpay_key_secret="",
        razorpay_webhook_secret="",
    )
    monkeypatch.setattr(rz, "settings", st)
    return st


def test_resolve_key_id_env_over_db(fake_settings, monkeypatch):
    fake_settings.razorpay_key_id = "  rzp_env  "
    row = SimpleNamespace(
        razorpay_key_id="rzp_db",
        razorpay_key_secret_encrypted=None,
        razorpay_webhook_secret_encrypted=None,
    )
    assert rz.resolve_razorpay_key_id(row) == "rzp_env"


def test_resolve_key_id_db_when_env_empty(fake_settings):
    row = SimpleNamespace(
        razorpay_key_id="rzp_db",
        razorpay_key_secret_encrypted=None,
        razorpay_webhook_secret_encrypted=None,
    )
    assert rz.resolve_razorpay_key_id(row) == "rzp_db"


def test_resolve_key_id_db_only_ignores_env(fake_settings):
    fake_settings.razorpay_use_db_only = True
    fake_settings.razorpay_key_id = "  rzp_env  "
    row = SimpleNamespace(
        razorpay_key_id="rzp_db",
        razorpay_key_secret_encrypted=None,
        razorpay_webhook_secret_encrypted=None,
    )
    assert rz.resolve_razorpay_key_id(row) == "rzp_db"


def test_resolve_key_secret_db_only_ignores_env(fake_settings, monkeypatch):
    fake_settings.razorpay_use_db_only = True
    fake_settings.razorpay_key_secret = "should_not_use"
    row = SimpleNamespace(
        razorpay_key_id=None,
        razorpay_key_secret_encrypted=b"blob",
        razorpay_webhook_secret_encrypted=None,
    )

    def _fake_decrypt(b: bytes) -> bytes:
        assert b == b"blob"
        return b"secret_from_db"

    monkeypatch.setattr("src.application.services.razorpay_credentials.decrypt_blob", _fake_decrypt)
    assert rz.resolve_razorpay_key_secret(row) == "secret_from_db"


def test_resolve_key_secret_env_wins(fake_settings, monkeypatch):
    fake_settings.razorpay_key_secret = "secret_env"
    row = SimpleNamespace(
        razorpay_key_id=None,
        razorpay_key_secret_encrypted=b"blob",
        razorpay_webhook_secret_encrypted=None,
    )
    assert rz.resolve_razorpay_key_secret(row) == "secret_env"


def test_encryption_dedicated_key_detection(monkeypatch):
    monkeypatch.delenv("APP_DATA_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("BROKER_SECRET_KEY", raising=False)
    assert crypto_mod.encryption_uses_dedicated_env_key() is False
    monkeypatch.setenv(
        "APP_DATA_ENCRYPTION_KEY", "x" * 32
    )  # truthy for env check (not a valid Fernet key)
    assert crypto_mod.encryption_uses_dedicated_env_key() is True


def test_assert_db_secret_encryption_allowed_raises_without_dedicated_key(monkeypatch):
    monkeypatch.delenv("APP_DATA_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("BROKER_SECRET_KEY", raising=False)
    with pytest.raises(crypto_mod.MissingDedicatedEncryptionKeyError):
        crypto_mod.assert_db_secret_encryption_allowed()
