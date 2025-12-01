from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status

from server.app.core import deps


class DummyUser:
    def __init__(self):
        self.is_active = True
        self.role = "USER"
        self.id = 1


class DummyUserRepo:
    def __init__(self, user):
        self._user = user

    def get_by_id(self, user_id: int):
        return self._user


class DummyCredentials:
    def __init__(self, token, scheme="Bearer"):
        self.credentials = token
        self.scheme = scheme


@pytest.fixture
def stub_user(monkeypatch):
    user = DummyUser()
    monkeypatch.setattr(deps, "UserRepository", lambda db: DummyUserRepo(user))
    return SimpleNamespace(user=user, session=SimpleNamespace())


def _token(payload: dict) -> str:
    return f"token:{payload}"


def test_get_current_user_success(monkeypatch, stub_user):
    stub_user.user.role = "user"

    def fake_decode(token):
        assert token == "valid-token"
        return {"uid": "1"}

    monkeypatch.setattr(deps, "decode_token", fake_decode)
    creds = DummyCredentials("valid-token")
    user = deps.get_current_user(credentials=creds, db=stub_user.session)
    assert user is stub_user.user


@pytest.mark.parametrize(
    "credentials,expected_status",
    [
        (None, status.HTTP_401_UNAUTHORIZED),
        (DummyCredentials("x", scheme="Basic"), status.HTTP_401_UNAUTHORIZED),
    ],
)
def test_get_current_user_missing_credentials(credentials, expected_status, stub_user):
    with pytest.raises(HTTPException) as exc:
        deps.get_current_user(credentials=credentials, db=stub_user.session)
    assert exc.value.status_code == expected_status


def test_get_current_user_invalid_token(monkeypatch, stub_user):
    monkeypatch.setattr(deps, "decode_token", lambda _: None)
    with pytest.raises(HTTPException) as exc:
        deps.get_current_user(credentials=DummyCredentials("bad"), db=stub_user.session)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_missing_uid(monkeypatch, stub_user):
    monkeypatch.setattr(deps, "decode_token", lambda _: {"uid": ""})
    with pytest.raises(HTTPException):
        deps.get_current_user(credentials=DummyCredentials("bad"), db=stub_user.session)


def test_get_current_user_inactive(monkeypatch, stub_user):
    stub_user.user.is_active = False

    monkeypatch.setattr(deps, "decode_token", lambda _: {"uid": "1"})
    with pytest.raises(HTTPException) as exc:
        deps.get_current_user(credentials=DummyCredentials("bad"), db=stub_user.session)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_require_admin_success(stub_user):
    stub_user.user.role = deps.UserRole.ADMIN
    assert deps.require_admin(stub_user.user) is stub_user.user


def test_require_admin_forbidden(stub_user):
    stub_user.user.role = deps.UserRole.USER
    with pytest.raises(HTTPException) as exc:
        deps.require_admin(stub_user.user)
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN


def test_get_db_yields_from_session(monkeypatch):
    sequence = []

    def fake_get_session():
        sequence.append("start")
        yield "db-session"
        sequence.append("end")

    monkeypatch.setattr(deps, "get_session", fake_get_session)
    generator = deps.get_db()
    assert next(generator) == "db-session"
    with pytest.raises(StopIteration):
        next(generator)
    assert sequence == ["start", "end"]
