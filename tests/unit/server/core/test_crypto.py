import base64
import os

import pytest

from server.app.core import crypto


def _fresh_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8")


def test_get_or_create_key_prefers_broker_secret(monkeypatch):
    key = _fresh_key()
    monkeypatch.setenv("BROKER_SECRET_KEY", key)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    derived = crypto._get_or_create_key()
    assert derived == key.encode("utf-8")


def test_get_or_create_key_uses_jwt_secret(monkeypatch):
    monkeypatch.delenv("BROKER_SECRET_KEY", raising=False)
    monkeypatch.setenv("JWT_SECRET", "myjwt")
    expected = base64.urlsafe_b64encode(b"myjwt".ljust(32, b"_")[:32])
    assert crypto._get_or_create_key() == expected


def test_get_or_create_key_default(monkeypatch):
    monkeypatch.delenv("BROKER_SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("jwt_secret", raising=False)
    key = crypto._get_or_create_key()
    assert len(key) == 44  # urlsafe base64 over 32 bytes
    assert key == base64.urlsafe_b64encode(b"dev-secret-change".ljust(32, b"_")[:32])


def test_encrypt_decrypt_roundtrip(monkeypatch):
    key = _fresh_key()
    monkeypatch.setenv("BROKER_SECRET_KEY", key)
    token = crypto.encrypt_blob(b"hello-world")
    assert crypto.decrypt_blob(token) == b"hello-world"


@pytest.mark.parametrize("token", [b"", b"junk", b"!!"])
def test_decrypt_blob_handles_invalid_tokens(monkeypatch, token):
    key = _fresh_key()
    monkeypatch.setenv("BROKER_SECRET_KEY", key)
    assert crypto.decrypt_blob(token) is None

