from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status

from server.app.routers import auth
from src.infrastructure.db.models import UserRole


class DummyUser(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            email=kwargs.get("email", "user@example.com"),
            name=kwargs.get("name", "User"),
            role=kwargs.get("role", UserRole.USER),
            is_active=kwargs.get("is_active", True),
            password_hash=kwargs.get("password_hash", "$2b$12$dummy.hash.here"),
        )


class DummyUserRepo:
    def __init__(self, db):
        self.db = db
        self.by_email = None
        self.by_id = None
        self.created_user = None
        self.password_set_user = None
        self.password_set_value = None

    def get_by_email(self, email):
        return self.by_email

    def get_by_id(self, user_id):
        return self.by_id

    def create_user(self, email, password, name, role):
        self.created_user = SimpleNamespace(
            id=42, email=email, name=name, role=role, password_hash="hashed"
        )
        return self.created_user

    def set_password(self, user, password):
        self.password_set_user = user
        self.password_set_value = password


class DummySettingsRepo:
    def __init__(self, db):
        self.db = db
        self.ensured_user_ids = []

    def ensure_default(self, user_id):
        self.ensured_user_ids.append(user_id)


@pytest.fixture
def user_repo(monkeypatch):
    repo = DummyUserRepo(db=None)
    monkeypatch.setattr(auth, "UserRepository", lambda db: repo)
    return repo


@pytest.fixture
def settings_repo(monkeypatch):
    repo = DummySettingsRepo(db=None)
    monkeypatch.setattr(auth, "SettingsRepository", lambda db: repo)
    return repo


@pytest.fixture
def mock_jwt_creation(monkeypatch):
    tokens = SimpleNamespace(access="access_token_123", refresh="refresh_token_456")

    def create_token(subject, *, extra=None, expires_minutes=None, expires_days=None):
        if extra and extra.get("type") == "refresh":
            return tokens.refresh
        return tokens.access

    monkeypatch.setattr(auth, "create_jwt_token", create_token)
    return tokens


@pytest.fixture
def mock_jwt_decode(monkeypatch):
    decoded_data = {"uid": 1, "type": "refresh", "sub": "1"}

    def decode_token(token):
        if token == "invalid_token":
            return None
        if token == "expired_token":
            return None
        return decoded_data

    monkeypatch.setattr(auth, "decode_token", decode_token)
    return decoded_data


@pytest.fixture
def mock_verify_password(monkeypatch):
    state = SimpleNamespace(verified=True)

    def verify(pwd, hashed):
        return state.verified

    monkeypatch.setattr(auth, "verify_password", verify)
    return state


@pytest.fixture
def mock_settings(monkeypatch):
    class DummySettings:
        jwt_refresh_days = 30

    monkeypatch.setattr(auth, "settings", DummySettings())


# Signup tests
def test_signup_success(user_repo, settings_repo, mock_jwt_creation, mock_settings):
    user_repo.by_email = None  # No existing user
    payload = auth.SignupRequest(email="new@example.com", password="password123", name="New User")

    result = auth.signup(payload, db=None)

    assert result.access_token == "access_token_123"
    assert result.refresh_token == "refresh_token_456"
    assert user_repo.created_user.email == "new@example.com"
    assert user_repo.created_user.name == "New User"
    assert settings_repo.ensured_user_ids == [42]


def test_signup_duplicate_email(user_repo, settings_repo):
    existing_user = DummyUser(email="existing@example.com")
    user_repo.by_email = existing_user
    payload = auth.SignupRequest(email="existing@example.com", password="password123")

    with pytest.raises(HTTPException) as exc:
        auth.signup(payload, db=None)

    assert exc.value.status_code == status.HTTP_409_CONFLICT
    assert "Email already registered" in exc.value.detail
    assert user_repo.created_user is None


def test_signup_exception_handling(user_repo, settings_repo, mock_settings):
    user_repo.by_email = None

    def boom(*_, **__):
        raise RuntimeError("Database error")

    user_repo.create_user = boom
    payload = auth.SignupRequest(email="new@example.com", password="password123")

    with pytest.raises(HTTPException) as exc:
        auth.signup(payload, db=None)

    assert exc.value.status_code == 500
    assert "Signup failed" in exc.value.detail


# Login tests
def test_login_success(user_repo, mock_jwt_creation, mock_verify_password, mock_settings):
    user = DummyUser(id=1, email="test@example.com", password_hash="$2b$12$hashed.password")
    user_repo.by_email = user

    payload = auth.LoginRequest(email="test@example.com", password="correct_password")
    result = auth.login(payload, db=None)

    assert result.access_token == "access_token_123"
    assert result.refresh_token == "refresh_token_456"


def test_login_user_not_found(user_repo):
    user_repo.by_email = None
    payload = auth.LoginRequest(email="nonexistent@example.com", password="password")

    with pytest.raises(HTTPException) as exc:
        auth.login(payload, db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid credentials" in exc.value.detail


def test_login_invalid_password_bcrypt(user_repo, mock_verify_password, mock_settings):
    user = DummyUser(password_hash="$2b$12$hashed.password")
    user_repo.by_email = user
    mock_verify_password.verified = False  # Password verification fails

    payload = auth.LoginRequest(email="test@example.com", password="wrong_password")

    with pytest.raises(HTTPException) as exc:
        auth.login(payload, db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid credentials" in exc.value.detail


def test_login_legacy_password_upgrade(user_repo, mock_jwt_creation, mock_settings):
    user = DummyUser(id=1, password_hash="plaintext_password")  # Non-bcrypt hash
    user_repo.by_email = user

    payload = auth.LoginRequest(email="test@example.com", password="plaintext_password")
    result = auth.login(payload, db=None)

    assert result.access_token == "access_token_123"
    assert user_repo.password_set_user == user
    assert user_repo.password_set_value == "plaintext_password"


def test_login_legacy_password_mismatch(user_repo, mock_settings):
    user = DummyUser(password_hash="old_plaintext")  # Non-bcrypt hash
    user_repo.by_email = user

    payload = auth.LoginRequest(email="test@example.com", password="wrong_password")

    with pytest.raises(HTTPException) as exc:
        auth.login(payload, db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid credentials" in exc.value.detail


def test_login_empty_password_hash(user_repo, mock_settings):
    user = DummyUser(password_hash="")  # Empty password hash
    user_repo.by_email = user

    payload = auth.LoginRequest(email="test@example.com", password="any_password")

    with pytest.raises(HTTPException) as exc:
        auth.login(payload, db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid credentials" in exc.value.detail


def test_login_exception_handling(user_repo, mock_settings):
    def boom(*_, **__):
        raise RuntimeError("DB error")

    user_repo.get_by_email = boom
    payload = auth.LoginRequest(email="test@example.com", password="password")

    with pytest.raises(HTTPException) as exc:
        auth.login(payload, db=None)

    assert exc.value.status_code == 500
    assert "Login failed" in exc.value.detail


# Me endpoint tests
def test_me_success():
    user = DummyUser(id=5, email="me@example.com", name="Me User", role=UserRole.ADMIN)

    result = auth.me(current=user)

    assert result.id == 5
    assert result.email == "me@example.com"
    assert result.name == "Me User"
    assert result.roles == ["admin"]


def test_me_user_role():
    user = DummyUser(id=1, email="user@example.com", role=UserRole.USER)

    result = auth.me(current=user)

    assert result.roles == ["user"]


# Refresh token tests
def test_refresh_success(user_repo, mock_jwt_creation, mock_jwt_decode, mock_settings):
    user = DummyUser(id=1, is_active=True)
    user_repo.by_id = user

    payload = auth.RefreshRequest(refresh_token="valid_refresh_token")
    result = auth.refresh_token(payload, db=None)

    assert result.access_token == "access_token_123"
    assert result.refresh_token == "refresh_token_456"


def test_refresh_missing_token(mock_settings):
    payload = auth.RefreshRequest(refresh_token="")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, db=None)

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Missing refresh token" in exc.value.detail


def test_refresh_invalid_token(user_repo, mock_jwt_decode, mock_settings, monkeypatch):
    def decode_none(token):
        return None

    monkeypatch.setattr(auth, "decode_token", decode_none)
    payload = auth.RefreshRequest(refresh_token="invalid_token")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid refresh token" in exc.value.detail


def test_refresh_wrong_token_type(user_repo, mock_settings, monkeypatch):
    def decode_access_token(token):
        return {"uid": 1, "type": "access"}  # Not a refresh token

    monkeypatch.setattr(auth, "decode_token", decode_access_token)
    payload = auth.RefreshRequest(refresh_token="access_token")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid refresh token" in exc.value.detail


def test_refresh_missing_uid(user_repo, mock_settings, monkeypatch):
    def decode_no_uid(token):
        return {"type": "refresh"}  # Missing uid

    monkeypatch.setattr(auth, "decode_token", decode_no_uid)
    payload = auth.RefreshRequest(refresh_token="token")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid refresh token" in exc.value.detail


def test_refresh_user_not_found(user_repo, mock_jwt_decode, mock_settings):
    user_repo.by_id = None  # User doesn't exist

    payload = auth.RefreshRequest(refresh_token="valid_token")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Inactive user" in exc.value.detail


def test_refresh_inactive_user(user_repo, mock_jwt_decode, mock_settings):
    user = DummyUser(id=1, is_active=False)
    user_repo.by_id = user

    payload = auth.RefreshRequest(refresh_token="valid_token")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Inactive user" in exc.value.detail


def test_refresh_exception_handling(user_repo, mock_settings, monkeypatch):
    def boom(*_, **__):
        raise RuntimeError("DB error")

    monkeypatch.setattr(auth, "decode_token", boom)
    payload = auth.RefreshRequest(refresh_token="token")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, db=None)

    assert exc.value.status_code == 500
    assert "Refresh failed" in exc.value.detail


# Additional edge case tests for better coverage


def test_signup_exception_from_settings_repo(
    user_repo, settings_repo, mock_jwt_creation, mock_settings
):
    user_repo.by_email = None

    def boom(user_id):
        raise RuntimeError("Settings error")

    settings_repo.ensure_default = boom
    payload = auth.SignupRequest(email="new@example.com", password="password123")

    with pytest.raises(HTTPException) as exc:
        auth.signup(payload, db=None)

    assert exc.value.status_code == 500
    assert "Signup failed" in exc.value.detail


def test_signup_exception_from_jwt_creation(user_repo, settings_repo, mock_settings, monkeypatch):
    user_repo.by_email = None

    def boom(*_, **__):
        raise RuntimeError("JWT error")

    monkeypatch.setattr(auth, "create_jwt_token", boom)
    payload = auth.SignupRequest(email="new@example.com", password="password123")

    with pytest.raises(HTTPException) as exc:
        auth.signup(payload, db=None)

    assert exc.value.status_code == 500
    assert "Signup failed" in exc.value.detail


def test_signup_exception_from_get_by_email(user_repo, settings_repo, mock_settings):
    def boom(email):
        raise RuntimeError("DB connection error")

    user_repo.get_by_email = boom
    payload = auth.SignupRequest(email="new@example.com", password="password123")

    with pytest.raises(HTTPException) as exc:
        auth.signup(payload, db=None)

    assert exc.value.status_code == 500
    assert "Signup failed" in exc.value.detail


def test_login_bcrypt_hash_prefix_2a(
    user_repo, mock_jwt_creation, mock_verify_password, mock_settings
):
    user = DummyUser(id=1, password_hash="$2a$12$hashed.password")  # Different bcrypt prefix
    user_repo.by_email = user

    payload = auth.LoginRequest(email="test@example.com", password="correct_password")
    result = auth.login(payload, db=None)

    assert result.access_token == "access_token_123"


def test_login_bcrypt_hash_prefix_2y(
    user_repo, mock_jwt_creation, mock_verify_password, mock_settings
):
    user = DummyUser(id=1, password_hash="$2y$12$hashed.password")  # Different bcrypt prefix
    user_repo.by_email = user

    payload = auth.LoginRequest(email="test@example.com", password="correct_password")
    result = auth.login(payload, db=None)

    assert result.access_token == "access_token_123"


def test_login_none_password_hash(user_repo, mock_settings):
    user = DummyUser(password_hash=None)  # None password hash
    user_repo.by_email = user

    payload = auth.LoginRequest(email="test@example.com", password="any_password")

    with pytest.raises(HTTPException) as exc:
        auth.login(payload, db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid credentials" in exc.value.detail


def test_login_exception_from_jwt_creation(
    user_repo, mock_verify_password, mock_settings, monkeypatch
):
    user = DummyUser(id=1, password_hash="$2b$12$hashed.password")
    user_repo.by_email = user

    def boom(*_, **__):
        raise RuntimeError("JWT creation error")

    monkeypatch.setattr(auth, "create_jwt_token", boom)
    payload = auth.LoginRequest(email="test@example.com", password="correct_password")

    with pytest.raises(HTTPException) as exc:
        auth.login(payload, db=None)

    assert exc.value.status_code == 500
    assert "Login failed" in exc.value.detail


def test_login_exception_from_set_password(user_repo, mock_jwt_creation, mock_settings):
    user = DummyUser(id=1, password_hash="plaintext_password")  # Legacy password
    user_repo.by_email = user

    def boom(user, password):
        raise RuntimeError("Password update error")

    user_repo.set_password = boom
    payload = auth.LoginRequest(email="test@example.com", password="plaintext_password")

    with pytest.raises(HTTPException) as exc:
        auth.login(payload, db=None)

    assert exc.value.status_code == 500
    assert "Login failed" in exc.value.detail


def test_me_with_none_name():
    user = DummyUser(id=1, email="test@example.com", name=None, role=UserRole.USER)

    result = auth.me(current=user)

    assert result.id == 1
    assert result.email == "test@example.com"
    assert result.name is None
    assert result.roles == ["user"]


def test_refresh_exception_from_get_by_id(user_repo, mock_jwt_decode, mock_settings):
    def boom(user_id):
        raise RuntimeError("DB lookup error")

    user_repo.get_by_id = boom
    payload = auth.RefreshRequest(refresh_token="valid_token")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, db=None)

    assert exc.value.status_code == 500
    assert "Refresh failed" in exc.value.detail


def test_refresh_exception_from_jwt_creation(
    user_repo, mock_jwt_decode, mock_settings, monkeypatch
):
    user = DummyUser(id=1, is_active=True)
    user_repo.by_id = user

    def boom(*_, **__):
        raise RuntimeError("JWT creation error")

    monkeypatch.setattr(auth, "create_jwt_token", boom)
    payload = auth.RefreshRequest(refresh_token="valid_token")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, db=None)

    assert exc.value.status_code == 500
    assert "Refresh failed" in exc.value.detail


def test_refresh_none_uid_after_decode(user_repo, mock_settings, monkeypatch):
    def decode_none_uid(token):
        return {"type": "refresh", "uid": None}  # uid is None

    monkeypatch.setattr(auth, "decode_token", decode_none_uid)
    payload = auth.RefreshRequest(refresh_token="token")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid refresh token" in exc.value.detail


def test_refresh_empty_dict_decode(user_repo, mock_settings, monkeypatch):
    def decode_empty(token):
        return {}  # Empty dict, no type or uid

    monkeypatch.setattr(auth, "decode_token", decode_empty)
    payload = auth.RefreshRequest(refresh_token="token")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid refresh token" in exc.value.detail


def test_signup_http_exception_propagation(user_repo, settings_repo):
    user_repo.by_email = None

    def create_with_http_error(*_, **__):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service down")

    user_repo.create_user = create_with_http_error
    payload = auth.SignupRequest(email="new@example.com", password="password123")

    with pytest.raises(HTTPException) as exc:
        auth.signup(payload, db=None)

    assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "Service down" in exc.value.detail
