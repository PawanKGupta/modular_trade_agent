from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt
from jose.exceptions import JWTError

from server.app.core import security


class DummySettings:
    jwt_secret = "unit-secret"
    jwt_algorithm = "HS256"
    jwt_access_minutes = 30


@pytest.fixture(autouse=True)
def dummy_settings(monkeypatch):
    monkeypatch.setattr(security, "settings", DummySettings())


# Phase 4: Removed _truncate_for_bcrypt tests - function no longer exists
# We migrated from bcrypt to pbkdf2_sha256 which doesn't have the 72-byte limit
# These tests are no longer relevant


def test_hash_and_verify_password():
    hashed = security.hash_password("SuperSecret123")
    assert hashed != "SuperSecret123"
    assert security.verify_password("SuperSecret123", hashed)
    assert not security.verify_password("wrong", hashed)


def test_create_jwt_token_uses_default_minutes():
    token = security.create_jwt_token("user-123")
    payload = jwt.decode(token, DummySettings.jwt_secret, algorithms=[DummySettings.jwt_algorithm])
    assert payload["sub"] == "user-123"
    exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
    assert exp > datetime.now(tz=UTC)
    assert exp - datetime.now(tz=UTC) <= timedelta(minutes=DummySettings.jwt_access_minutes + 1)


def test_create_jwt_token_custom_exp_and_extra(monkeypatch):
    token = security.create_jwt_token(
        "u1", extra={"role": "admin"}, expires_minutes=1, expires_days=1
    )
    payload = jwt.decode(token, DummySettings.jwt_secret, algorithms=[DummySettings.jwt_algorithm])
    assert payload["role"] == "admin"
    exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
    delta = exp - datetime.now(tz=UTC)
    assert delta > timedelta(days=1)


def test_decode_token_success(monkeypatch):
    token = jwt.encode(
        {"sub": "abc"}, DummySettings.jwt_secret, algorithm=DummySettings.jwt_algorithm
    )
    assert security.decode_token(token)["sub"] == "abc"


def test_decode_token_failure(monkeypatch):
    class FakeJWT:
        def decode(self, *_, **__):
            raise JWTError("bad token")

    monkeypatch.setattr(security, "jwt", FakeJWT())
    assert security.decode_token("invalid") is None
