import base64
import os

import pytest

from server.app.core import crypto


def _fresh_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8")


def test_get_or_create_key_prefers_broker_secret(monkeypatch):
    monkeypatch.delenv("APP_DATA_ENCRYPTION_KEY", raising=False)
    key = _fresh_key()
    monkeypatch.setenv("BROKER_SECRET_KEY", key)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    derived = crypto._get_or_create_key()
    assert derived == key.encode("utf-8")


def test_get_or_create_key_uses_jwt_secret(monkeypatch):
    monkeypatch.delenv("APP_DATA_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("BROKER_SECRET_KEY", raising=False)
    monkeypatch.setenv("JWT_SECRET", "myjwt")
    expected = base64.urlsafe_b64encode(b"myjwt".ljust(32, b"_")[:32])
    assert crypto._get_or_create_key() == expected


def test_get_or_create_key_default(monkeypatch):
    monkeypatch.delenv("APP_DATA_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("BROKER_SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("jwt_secret", raising=False)
    key = crypto._get_or_create_key()
    assert len(key) == 44  # urlsafe base64 over 32 bytes
    assert key == base64.urlsafe_b64encode(b"dev-secret-change".ljust(32, b"_")[:32])


def test_get_or_create_key_uses_lowercase_jwt_secret(monkeypatch):
    """Test that lowercase jwt_secret env var is also checked"""
    monkeypatch.delenv("APP_DATA_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("BROKER_SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("jwt_secret", "lowercase-secret")
    expected = base64.urlsafe_b64encode(b"lowercase-secret".ljust(32, b"_")[:32])
    assert crypto._get_or_create_key() == expected


def test_decrypt_blob_with_type_error(monkeypatch):
    """Test decrypt_blob handles TypeError (e.g., from None input)"""
    monkeypatch.delenv("APP_DATA_ENCRYPTION_KEY", raising=False)
    key = _fresh_key()
    monkeypatch.setenv("BROKER_SECRET_KEY", key)

    # The function catches TypeError, so this should return None
    # We'll test with an invalid type that causes TypeError
    class BadType:
        pass

    result = crypto.decrypt_blob(BadType())  # type: ignore
    assert result is None


def test_encrypt_decrypt_roundtrip(monkeypatch):
    monkeypatch.delenv("APP_DATA_ENCRYPTION_KEY", raising=False)
    key = _fresh_key()
    monkeypatch.setenv("BROKER_SECRET_KEY", key)
    token = crypto.encrypt_blob(b"hello-world")
    assert crypto.decrypt_blob(token) == b"hello-world"


@pytest.mark.parametrize("token", [b"", b"junk", b"!!"])
def test_decrypt_blob_handles_invalid_tokens(monkeypatch, token):
    monkeypatch.delenv("APP_DATA_ENCRYPTION_KEY", raising=False)
    key = _fresh_key()
    monkeypatch.setenv("BROKER_SECRET_KEY", key)
    assert crypto.decrypt_blob(token) is None
