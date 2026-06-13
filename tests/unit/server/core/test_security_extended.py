"""Tests for password security helpers."""

from server.app.core import security


def test_is_passlib_password_hash():
    hashed = security.hash_password("TestPass123!")
    assert security.is_passlib_password_hash(hashed)
    assert not security.is_passlib_password_hash("plaintext")


def test_hash_includes_configured_rounds(monkeypatch):
    from server.app.core import config

    monkeypatch.setattr(config.settings, "password_hash_rounds", 100000)
    hashed = security.hash_password("RoundTest123!")
    assert "$pbkdf2-sha256$100000$" in hashed


def test_password_needs_rehash_when_rounds_low(monkeypatch):
    from passlib.hash import pbkdf2_sha256

    from server.app.core import config

    monkeypatch.setattr(config.settings, "password_hash_rounds", 500000)
    low = pbkdf2_sha256.using(rounds=29000).hash("x")
    assert security.password_needs_rehash(low)


def test_jwt_token_version_embedded():
    token = security.create_jwt_token("1", extra={"uid": 1}, token_version=3)
    payload = security.decode_token(token)
    assert payload is not None
    assert payload["tv"] == 3
