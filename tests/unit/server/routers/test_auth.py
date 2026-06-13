from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, status
from pydantic import ValidationError

from server.app.routers import auth
from server.app.schemas.auth import SignupRequest
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
            email_verified_at=kwargs.get("email_verified_at", None),
            email_verification_token_hash=kwargs.get("email_verification_token_hash", None),
            email_verification_sent_at=kwargs.get("email_verification_sent_at", None),
            password_reset_token_hash=kwargs.get("password_reset_token_hash", None),
            password_reset_expires_at=kwargs.get("password_reset_expires_at", None),
            mobile_number=kwargs.get("mobile_number", None),
            token_version=kwargs.get("token_version", 0),
            must_change_password=kwargs.get("must_change_password", False),
            mfa_enabled=kwargs.get("mfa_enabled", False),
            mfa_secret_encrypted=kwargs.get("mfa_secret_encrypted", None),
            mfa_backup_codes_hash=kwargs.get("mfa_backup_codes_hash", None),
            deleted_at=kwargs.get("deleted_at", None),
        )


def verified_dummy(**kwargs):
    from src.infrastructure.db.timezone_utils import ist_now

    if "email_verified_at" not in kwargs:
        kwargs["email_verified_at"] = ist_now()
    return DummyUser(**kwargs)


def _mock_request():
    r = MagicMock()
    r.headers = {"X-Forwarded-For": "127.0.0.1"}
    r.cookies = {}
    r.client = MagicMock(host="127.0.0.1")
    r.url = MagicMock(path="/api/v1/auth/login")
    return r


class DummyDB:
    def commit(self):
        return None

    def refresh(self, _obj):
        return None


class DummyUserRepo:
    def __init__(self, db):
        self.db = db
        self.by_email = None
        self.by_id = None
        self.created_user = None
        self.password_set_user = None
        self.password_set_value = None
        self.updated_unverified_user = None

    def get_by_email(self, email):
        return self.by_email

    def get_by_id(self, user_id):
        return self.by_id

    def create_user(self, email, password, name, role):
        self.created_user = SimpleNamespace(
            id=42,
            email=email,
            name=name,
            role=role,
            password_hash="hashed",
            email_verified_at=None,
            email_verification_token_hash=None,
            email_verification_sent_at=None,
            password_reset_token_hash=None,
            password_reset_expires_at=None,
        )
        return self.created_user

    def create_pending_verification_user(
        self, email, password, name, token_hash, sent_at, role=UserRole.USER, mobile_number=None
    ):
        self.created_user = SimpleNamespace(
            id=42,
            email=email,
            name=name,
            role=role,
            password_hash="hashed",
            email_verified_at=None,
            email_verification_token_hash=token_hash,
            email_verification_sent_at=sent_at,
            password_reset_token_hash=None,
            password_reset_expires_at=None,
            mobile_number=mobile_number,
        )
        return self.created_user

    def update_unverified_signup_credentials(self, user, *, password, name, mobile_number=None):
        user.name = name
        user.mobile_number = mobile_number
        self.updated_unverified_user = user
        self.password_set_user = user
        self.password_set_value = password
        return user

    def update_profile(
        self,
        user,
        *,
        email=None,
        mobile_number=None,
        update_email=False,
        update_mobile=False,
        reset_email_verification=False,
    ):
        if update_mobile:
            user.mobile_number = mobile_number
        if update_email and email is not None:
            user.email = email
        if reset_email_verification:
            user.email_verified_at = None
            user.email_verification_token_hash = None
            user.email_verification_sent_at = None
        return user

    def set_password(self, user, password):
        self.password_set_user = user
        self.password_set_value = password

    def bump_token_version(self, user):
        user.token_version = getattr(user, "token_version", 0) + 1

    def set_password_reset_token(self, user, token_hash, expires_at):
        user.password_reset_token_hash = token_hash
        user.password_reset_expires_at = expires_at

    def clear_password_reset_token(self, user):
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None

    def find_by_reset_token_hash(self, token_hash):
        if (
            self.by_email
            and getattr(self.by_email, "password_reset_token_hash", None) == token_hash
        ):
            return self.by_email
        return None

    def set_verification_token(self, user, token_hash, sent_at):
        user.email_verification_token_hash = token_hash
        user.email_verification_sent_at = sent_at

    def clear_verification(self, user):
        from src.infrastructure.db.timezone_utils import ist_now

        user.email_verified_at = ist_now()
        user.email_verification_token_hash = None
        user.email_verification_sent_at = None

    def find_by_verification_token_hash(self, token_hash):
        if (
            self.by_email
            and getattr(self.by_email, "email_verification_token_hash", None) == token_hash
        ):
            return self.by_email
        return None


class DummySettingsRepo:
    def __init__(self, db):
        self.db = db
        self.ensured_user_ids = []

    def ensure_default(self, user_id):
        self.ensured_user_ids.append(user_id)


@pytest.fixture(autouse=True)
def mock_refresh_repo(monkeypatch):
    class _Repo:
        def revoke_all_for_user(self, user_id):
            return 0

    monkeypatch.setattr(auth, "RefreshTokenRepository", lambda db: _Repo())
    monkeypatch.setattr(auth, "record_audit", lambda *a, **k: None)
    monkeypatch.setattr(auth, "record_audit_user", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def auth_request(monkeypatch):
    req = MagicMock()
    req.headers = {"X-Forwarded-For": "127.0.0.1"}
    req.cookies = {}
    req.client = MagicMock(host="127.0.0.1")
    req.url.path = "/api/v1/auth/login"
    monkeypatch.setattr(auth, "check_rate_limit", lambda *a, **k: None)
    monkeypatch.setattr(auth, "record_rate_limit_failure", lambda *a, **k: None)
    monkeypatch.setattr(auth, "clear_rate_limit", lambda *a, **k: None)
    monkeypatch.setattr("server.app.core.auth_cookies.validate_csrf", lambda r: True)
    return req


@pytest.fixture(autouse=True)
def auth_response():
    return MagicMock()


@pytest.fixture(autouse=True)
def mock_rotate_refresh_autouse(monkeypatch):
    def _rotate(db, user, refresh_raw, response=None):
        return auth.TokenResponse(
            access_token="access_token_123",
            refresh_token="refresh_token_456",
        )

    monkeypatch.setattr(auth, "rotate_refresh_token", _rotate)


@pytest.fixture(autouse=True)
def mock_issue_tokens_autouse(monkeypatch):
    def _issue(db, user, response=None):
        return auth.TokenResponse(
            access_token="access_token_123",
            refresh_token="refresh_token_456",
        )

    monkeypatch.setattr(auth, "issue_tokens", _issue)


@pytest.fixture
def mock_issue_tokens(monkeypatch):
    def _issue(db, user, response=None):
        return auth.TokenResponse(
            access_token="access_token_123",
            refresh_token="refresh_token_456",
        )

    monkeypatch.setattr(auth, "issue_tokens", _issue)


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


@pytest.fixture(autouse=True)
def mock_settings_autouse(monkeypatch):
    class DummySettings:
        jwt_refresh_days = 30
        rate_limit_enabled = False
        rate_limit_login_max = 5
        rate_limit_refresh_max = 20
        rate_limit_window_seconds = 900
        auth_use_cookies = False

    monkeypatch.setattr(auth, "settings", DummySettings())


@pytest.fixture
def mock_settings(monkeypatch):
    class DummySettings:
        jwt_refresh_days = 30
        rate_limit_enabled = False
        rate_limit_login_max = 5
        rate_limit_refresh_max = 20
        rate_limit_window_seconds = 900
        auth_use_cookies = False

    monkeypatch.setattr(auth, "settings", DummySettings())


@pytest.fixture
def mock_auth_email(monkeypatch):
    """Replace AuthEmailService with an in-memory recorder (unit tests)."""
    from tests.support.mock_auth_email import install_mock_auth_email_service

    return install_mock_auth_email_service(monkeypatch)


@pytest.fixture
def dummy_db():
    return DummyDB()


# Signup tests
def test_signup_success(user_repo, settings_repo, mock_settings, mock_auth_email, dummy_db):
    user_repo.by_email = None  # No existing user
    payload = auth.SignupRequest(email="new@example.com", password="Password123!", name="New User")

    result = auth.signup(payload, db=dummy_db)

    assert "verification link" in result.message.lower()
    assert user_repo.created_user.email == "new@example.com"
    assert user_repo.created_user.name == "New User"
    assert user_repo.created_user.email_verification_token_hash is not None
    assert user_repo.created_user.email_verification_sent_at is not None
    assert settings_repo.ensured_user_ids == [42]
    assert len(mock_auth_email.verify) == 1


def test_signup_duplicate_verified_email(user_repo, settings_repo):
    from src.infrastructure.db.timezone_utils import ist_now

    existing_user = DummyUser(email="existing@example.com", email_verified_at=ist_now())
    user_repo.by_email = existing_user
    payload = auth.SignupRequest(
        email="existing@example.com", password="Password123!", name="Existing"
    )

    with pytest.raises(HTTPException) as exc:
        auth.signup(payload, db=DummyDB())

    assert exc.value.status_code == status.HTTP_409_CONFLICT
    assert "Email already registered" in exc.value.detail
    assert user_repo.created_user is None


def test_signup_unverified_duplicate_resends(user_repo, settings_repo, mock_auth_email, dummy_db):
    existing_user = DummyUser(
        email="pending@example.com",
        email_verified_at=None,
        email_verification_token_hash="pending-hash",
    )
    user_repo.by_email = existing_user
    payload = auth.SignupRequest(
        email="pending@example.com", password="Password123!", name="Pending"
    )

    result = auth.signup(payload, db=dummy_db)

    assert "verification link" in result.message.lower()
    assert user_repo.created_user is None
    assert user_repo.updated_unverified_user is existing_user
    assert existing_user.name == "Pending"
    assert user_repo.password_set_value == "Password123!"
    assert len(mock_auth_email.verify) == 1


def test_signup_exception_handling(user_repo, settings_repo, mock_settings):
    user_repo.by_email = None

    def boom(*_, **__):
        raise RuntimeError("Database error")

    user_repo.create_pending_verification_user = boom
    payload = auth.SignupRequest(email="new@example.com", password="Password123!", name="New User")

    with pytest.raises(HTTPException) as exc:
        auth.signup(payload, db=DummyDB())

    assert exc.value.status_code == 500
    assert "Signup failed" in exc.value.detail


# Login tests
def test_login_blocks_unverified_user(user_repo, mock_verify_password, mock_settings):
    user = DummyUser(
        password_hash="$2b$12$hashed.password",
        email_verified_at=None,
        email_verification_token_hash="pending-hash",
    )
    user_repo.by_email = user
    payload = auth.LoginRequest(email="test@example.com", password="correct_password")

    with pytest.raises(HTTPException) as exc:
        auth.login(payload, _mock_request(), MagicMock(), db=None)

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    assert "verify your email" in exc.value.detail.lower()


def test_login_success(
    user_repo, mock_issue_tokens, mock_verify_password, mock_settings
):
    user = verified_dummy(id=1, email="test@example.com", password_hash="$2b$12$hashed.password")
    user_repo.by_email = user

    payload = auth.LoginRequest(email="test@example.com", password="correct_password")
    result = auth.login(payload, _mock_request(), MagicMock(), db=None)

    assert result.access_token == "access_token_123"
    assert result.refresh_token == "refresh_token_456"


def test_login_user_not_found(user_repo):
    user_repo.by_email = None
    payload = auth.LoginRequest(email="nonexistent@example.com", password="password")

    with pytest.raises(HTTPException) as exc:
        auth.login(payload, _mock_request(), MagicMock(), db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid credentials" in exc.value.detail


def test_login_invalid_password_bcrypt(
    user_repo, mock_verify_password, mock_settings
):
    user = DummyUser(password_hash="$2b$12$hashed.password")
    user_repo.by_email = user
    mock_verify_password.verified = False

    payload = auth.LoginRequest(email="test@example.com", password="wrong_password")

    with pytest.raises(HTTPException) as exc:
        auth.login(payload, _mock_request(), MagicMock(), db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid credentials" in exc.value.detail


def test_login_legacy_plaintext_rejected(user_repo, mock_settings):
    user = verified_dummy(id=1, password_hash="plaintext_password")
    user_repo.by_email = user
    payload = auth.LoginRequest(email="test@example.com", password="plaintext_password")

    with pytest.raises(HTTPException) as exc:
        auth.login(payload, _mock_request(), MagicMock(), db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_login_legacy_password_mismatch(user_repo, mock_settings):
    user = DummyUser(password_hash="old_plaintext")
    user_repo.by_email = user

    payload = auth.LoginRequest(email="test@example.com", password="wrong_password")

    with pytest.raises(HTTPException) as exc:
        auth.login(payload, _mock_request(), MagicMock(), db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid credentials" in exc.value.detail


def test_login_empty_password_hash(user_repo, mock_settings):
    user = DummyUser(password_hash="")
    user_repo.by_email = user
    payload = auth.LoginRequest(email="test@example.com", password="any_password")
    with pytest.raises(HTTPException) as exc:
        auth.login(payload, _mock_request(), MagicMock(), db=None)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_login_exception_handling(user_repo, mock_settings):
    def boom(*_, **__):
        raise RuntimeError("DB error")

    user_repo.get_by_email = boom
    payload = auth.LoginRequest(email="test@example.com", password="password")
    with pytest.raises(HTTPException) as exc:
        auth.login(payload, _mock_request(), MagicMock(), db=None)
    assert exc.value.status_code == 500


# Me endpoint tests
def test_me_success():
    from src.infrastructure.db.timezone_utils import ist_now

    user = DummyUser(
        id=5,
        email="me@example.com",
        name="Me User",
        role=UserRole.ADMIN,
        email_verified_at=ist_now(),
    )

    result = auth.me(current=user)

    assert result.id == 5
    assert result.email == "me@example.com"
    assert result.name == "Me User"
    assert result.roles == ["admin"]
    assert result.email_verified is True


def test_me_user_role():
    user = DummyUser(id=1, email="user@example.com", role=UserRole.USER)

    result = auth.me(current=user)

    assert result.roles == ["user"]


# Refresh token tests
def test_refresh_success(
    user_repo, mock_jwt_decode, mock_settings
):
    user = verified_dummy(id=1, is_active=True)
    user_repo.by_id = user
    payload = auth.RefreshRequest(refresh_token="valid_refresh_token")
    result = auth.refresh_token(payload, _mock_request(), MagicMock(), db=None)
    assert result.access_token == "access_token_123"


def test_refresh_missing_token(mock_settings):
    payload = auth.RefreshRequest(refresh_token="")
    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, _mock_request(), MagicMock(), db=None)
    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST


def test_refresh_invalid_token(
    user_repo, mock_jwt_decode, mock_settings, monkeypatch
):
    def decode_none(token):
        return None

    monkeypatch.setattr(auth, "decode_token", decode_none)
    payload = auth.RefreshRequest(refresh_token="invalid_token")
    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, _mock_request(), MagicMock(), db=None)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_refresh_wrong_token_type(user_repo, mock_settings, monkeypatch):
    def decode_access_token(token):
        return {"uid": 1, "type": "access"}  # Not a refresh token

    monkeypatch.setattr(auth, "decode_token", decode_access_token)
    payload = auth.RefreshRequest(refresh_token="access_token")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, _mock_request(), MagicMock(), db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid refresh token" in exc.value.detail


def test_refresh_missing_uid(user_repo, mock_settings, monkeypatch):
    def decode_no_uid(token):
        return {"type": "refresh"}  # Missing uid

    monkeypatch.setattr(auth, "decode_token", decode_no_uid)
    payload = auth.RefreshRequest(refresh_token="token")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, _mock_request(), MagicMock(), db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid refresh token" in exc.value.detail


def test_refresh_user_not_found(user_repo, mock_jwt_decode, mock_settings):
    user_repo.by_id = None  # User doesn't exist

    payload = auth.RefreshRequest(refresh_token="valid_token")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, _mock_request(), MagicMock(), db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Inactive user" in exc.value.detail


def test_refresh_inactive_user(user_repo, mock_jwt_decode, mock_settings):
    user = DummyUser(id=1, is_active=False)
    user_repo.by_id = user

    payload = auth.RefreshRequest(refresh_token="valid_token")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, _mock_request(), MagicMock(), db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Inactive user" in exc.value.detail


def test_refresh_exception_handling(user_repo, mock_settings, monkeypatch):
    def boom(*_, **__):
        raise RuntimeError("DB error")

    monkeypatch.setattr(auth, "decode_token", boom)
    payload = auth.RefreshRequest(refresh_token="token")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, _mock_request(), MagicMock(), db=None)

    assert exc.value.status_code == 500
    assert "Refresh failed" in exc.value.detail


# Additional edge case tests for better coverage


def test_signup_exception_from_settings_repo(user_repo, settings_repo, mock_settings):
    user_repo.by_email = None

    def boom(user_id):
        raise RuntimeError("Settings error")

    settings_repo.ensure_default = boom
    payload = auth.SignupRequest(email="new@example.com", password="Password123!", name="New User")

    with pytest.raises(HTTPException) as exc:
        auth.signup(payload, db=DummyDB())

    assert exc.value.status_code == 500
    assert "Signup failed" in exc.value.detail


def test_signup_exception_from_jwt_creation(user_repo, mock_settings, monkeypatch):
    """verify-email issues JWT; failure surfaces from token creation."""
    from server.app.core.auth_tokens import auth_sent_at, hash_token

    def boom(*_, **__):
        raise RuntimeError("JWT error")

    monkeypatch.setattr(auth, "issue_tokens", boom)
    token = "verify-token"
    user = DummyUser(email="user@example.com")
    user.email_verification_token_hash = hash_token(token)
    user.email_verification_sent_at = auth_sent_at()
    user_repo = DummyUserRepo(db=None)
    user_repo.find_by_verification_token_hash = lambda h: user if h == hash_token(token) else None
    monkeypatch.setattr(auth, "UserRepository", lambda db: user_repo)
    payload = auth.VerifyEmailRequest(token=token)

    with pytest.raises(RuntimeError, match="JWT error"):
        auth.verify_email(payload, MagicMock(), db=DummyDB())


def test_signup_exception_from_get_by_email(user_repo, settings_repo, mock_settings):
    def boom(email):
        raise RuntimeError("DB connection error")

    user_repo.get_by_email = boom
    payload = auth.SignupRequest(email="new@example.com", password="Password123!", name="New User")

    with pytest.raises(HTTPException) as exc:
        auth.signup(payload, db=DummyDB())

    assert exc.value.status_code == 500
    assert "Signup failed" in exc.value.detail


def test_login_bcrypt_hash_prefix_2a(
    user_repo, mock_issue_tokens, mock_verify_password, mock_settings
):
    user = verified_dummy(id=1, password_hash="$2a$12$hashed.password")
    user_repo.by_email = user
    payload = auth.LoginRequest(email="test@example.com", password="correct_password")
    result = auth.login(payload, _mock_request(), MagicMock(), db=None)
    assert result.access_token == "access_token_123"


def test_login_bcrypt_hash_prefix_2y(
    user_repo, mock_issue_tokens, mock_verify_password, mock_settings
):
    user = verified_dummy(id=1, password_hash="$2y$12$hashed.password")
    user_repo.by_email = user
    payload = auth.LoginRequest(email="test@example.com", password="correct_password")
    result = auth.login(payload, _mock_request(), MagicMock(), db=None)
    assert result.access_token == "access_token_123"


def test_login_none_password_hash(user_repo, mock_settings):
    user = DummyUser(password_hash=None)
    user_repo.by_email = user
    payload = auth.LoginRequest(email="test@example.com", password="any_password")
    with pytest.raises(HTTPException) as exc:
        auth.login(payload, _mock_request(), MagicMock(), db=None)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_login_exception_from_jwt_creation(
    user_repo, mock_verify_password, mock_settings, monkeypatch
):
    user = verified_dummy(id=1, password_hash="$2b$12$hashed.password")
    user_repo.by_email = user

    def boom(*_, **__):
        raise RuntimeError("JWT creation error")

    monkeypatch.setattr(auth, "issue_tokens", boom)
    payload = auth.LoginRequest(email="test@example.com", password="correct_password")
    with pytest.raises(HTTPException) as exc:
        auth.login(payload, _mock_request(), MagicMock(), db=None)
    assert exc.value.status_code == 500


def test_login_legacy_plaintext_no_upgrade(user_repo, mock_settings):
    user = DummyUser(id=1, password_hash="plaintext_password")
    user_repo.by_email = user
    payload = auth.LoginRequest(email="test@example.com", password="plaintext_password")
    with pytest.raises(HTTPException) as exc:
        auth.login(payload, _mock_request(), MagicMock(), db=None)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


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
        auth.refresh_token(payload, _mock_request(), MagicMock(), db=None)

    assert exc.value.status_code == 500
    assert "Refresh failed" in exc.value.detail


def test_refresh_exception_from_jwt_creation(
    user_repo, mock_jwt_decode, mock_settings, monkeypatch
):
    user = verified_dummy(id=1, is_active=True)
    user_repo.by_id = user

    def boom(*_, **__):
        raise RuntimeError("JWT creation error")

    monkeypatch.setattr(auth, "rotate_refresh_token", boom)
    payload = auth.RefreshRequest(refresh_token="valid_token")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, _mock_request(), MagicMock(), db=None)

    assert exc.value.status_code == 500
    assert "Refresh failed" in exc.value.detail


def test_refresh_none_uid_after_decode(user_repo, mock_settings, monkeypatch):
    def decode_none_uid(token):
        return {"type": "refresh", "uid": None}  # uid is None

    monkeypatch.setattr(auth, "decode_token", decode_none_uid)
    payload = auth.RefreshRequest(refresh_token="token")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, _mock_request(), MagicMock(), db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid refresh token" in exc.value.detail


def test_refresh_empty_dict_decode(user_repo, mock_settings, monkeypatch):
    def decode_empty(token):
        return {}  # Empty dict, no type or uid

    monkeypatch.setattr(auth, "decode_token", decode_empty)
    payload = auth.RefreshRequest(refresh_token="token")

    with pytest.raises(HTTPException) as exc:
        auth.refresh_token(payload, _mock_request(), MagicMock(), db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid refresh token" in exc.value.detail


def test_signup_http_exception_propagation(user_repo, settings_repo):
    user_repo.by_email = None

    def create_with_http_error(*_, **__):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service down")

    user_repo.create_pending_verification_user = create_with_http_error
    payload = auth.SignupRequest(email="new@example.com", password="Password123!", name="New User")

    with pytest.raises(HTTPException) as exc:
        auth.signup(payload, db=DummyDB())

    assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "Service down" in exc.value.detail


def test_signup_rejects_weak_password():
    with pytest.raises(ValidationError):
        SignupRequest(email="new@example.com", password="short1!", name="User")
    with pytest.raises(ValidationError):
        SignupRequest(email="new@example.com", password="secret123!", name="User")


def test_signup_rejects_disposable_email():
    with pytest.raises(ValidationError) as exc:
        SignupRequest(email="user@mailinator.com", password="Password123!", name="User")
    assert "Disposable email addresses are not allowed" in str(exc.value)


def test_update_profile_rejects_disposable_email():
    from server.app.schemas.auth import UpdateProfileRequest

    with pytest.raises(ValidationError) as exc:
        UpdateProfileRequest(email="user@mailinator.com", current_password="Password123!")
    assert "Disposable email addresses are not allowed" in str(exc.value)


def test_signup_rejects_empty_name():
    with pytest.raises(ValidationError):
        SignupRequest(email="new@example.com", password="Password123!", name="   ")


def test_login_rejects_inactive_user(user_repo, mock_settings):
    user = DummyUser(is_active=False)
    user_repo.by_email = user
    payload = auth.LoginRequest(email="test@example.com", password="password")

    with pytest.raises(HTTPException) as exc:
        auth.login(payload, _mock_request(), MagicMock(), db=None)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid credentials" in exc.value.detail


def test_change_password_success(user_repo, mock_verify_password):
    user = DummyUser(password_hash="$pbkdf2-sha256$hashed")
    mock_verify_password.verified = True
    payload = auth.ChangePasswordRequest(
        current_password="OldPass123",
        new_password="NewPass456!",
    )

    result = auth.change_password(payload, _mock_request(), current=user, db=DummyDB())

    assert result.message == "Password updated successfully"
    assert user_repo.password_set_value == "NewPass456!"


def test_change_password_wrong_current(user_repo, mock_verify_password):
    user = DummyUser(password_hash="$pbkdf2-sha256$hashed")
    mock_verify_password.verified = False
    payload = auth.ChangePasswordRequest(
        current_password="wrong",
        new_password="NewPass456!",
    )

    with pytest.raises(HTTPException) as exc:
        auth.change_password(payload, _mock_request(), current=user, db=DummyDB())

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Current password is incorrect" in exc.value.detail


def test_forgot_password_always_200(user_repo, mock_auth_email, dummy_db):
    user_repo.by_email = None
    payload = auth.ForgotPasswordRequest(email="missing@example.com")

    result = auth.forgot_password(payload, _mock_request(), db=dummy_db)

    assert "If an account exists" in result.message


def test_forgot_password_sends_email_when_user_exists(user_repo, mock_auth_email, dummy_db):
    user = DummyUser(email="user@example.com")
    user_repo.by_email = user
    payload = auth.ForgotPasswordRequest(email="user@example.com")

    auth.forgot_password(payload, _mock_request(), db=dummy_db)

    assert len(mock_auth_email.reset) == 1
    assert mock_auth_email.reset[0][0] == "user@example.com"


def test_reset_password_valid_token(user_repo, mock_verify_password, dummy_db):
    from server.app.core.auth_tokens import hash_token, reset_expiry

    token = "reset-token-value"
    user = DummyUser(email="user@example.com")
    user.password_reset_token_hash = hash_token(token)
    user.password_reset_expires_at = reset_expiry()
    user_repo.by_email = user
    user_repo.find_by_reset_token_hash = lambda h: user if h == hash_token(token) else None

    payload = auth.ResetPasswordRequest(token=token, new_password="NewPass456!")
    result = auth.reset_password(payload, db=dummy_db)

    assert result.message == "Password reset successfully"
    assert user_repo.password_set_value == "NewPass456!"


def test_verify_email_success(user_repo, mock_jwt_creation, dummy_db):
    from server.app.core.auth_tokens import auth_sent_at, hash_token

    token = "verify-token"
    user = DummyUser(email="user@example.com")
    user.email_verification_token_hash = hash_token(token)
    user.email_verification_sent_at = auth_sent_at()
    user_repo.find_by_verification_token_hash = lambda h: user if h == hash_token(token) else None

    payload = auth.VerifyEmailRequest(token=token)
    result = auth.verify_email(payload, MagicMock(), db=dummy_db)

    assert result.access_token == "access_token_123"
    assert result.refresh_token == "refresh_token_456"
    assert user.email_verified_at is not None


def test_verify_email_expired_token(user_repo, dummy_db):
    from datetime import timedelta

    from server.app.core.auth_tokens import VERIFICATION_TOKEN_HOURS, hash_token
    from src.infrastructure.db.timezone_utils import ist_now_naive

    token = "expired-verify-token"
    user = DummyUser(email="user@example.com")
    user.email_verification_token_hash = hash_token(token)
    user.email_verification_sent_at = ist_now_naive() - timedelta(
        hours=VERIFICATION_TOKEN_HOURS + 1
    )
    user_repo.find_by_verification_token_hash = lambda h: user if h == hash_token(token) else None

    payload = auth.VerifyEmailRequest(token=token)

    with pytest.raises(HTTPException) as exc:
        auth.verify_email(payload, MagicMock(), db=dummy_db)

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid or expired verification link" in exc.value.detail


def test_resend_verification_public(user_repo, mock_auth_email, dummy_db):
    user = DummyUser(
        email="pending@example.com",
        email_verified_at=None,
        email_verification_token_hash="hash",
    )
    user_repo.by_email = user
    payload = auth.ResendVerificationRequest(email="pending@example.com")

    result = auth.resend_verification(payload, _mock_request(), db=dummy_db)

    assert "verification link" in result.message.lower()
    assert len(mock_auth_email.verify) == 1


def test_reset_password_expired_token(user_repo, dummy_db):
    from datetime import timedelta

    from server.app.core.auth_tokens import hash_token
    from src.infrastructure.db.timezone_utils import ist_now_naive

    token = "expired-token"
    user = DummyUser(email="user@example.com")
    user.password_reset_token_hash = hash_token(token)
    user.password_reset_expires_at = ist_now_naive() - timedelta(hours=2)
    user_repo.find_by_reset_token_hash = lambda h: user if h == hash_token(token) else None

    payload = auth.ResetPasswordRequest(token=token, new_password="NewPass456!")

    with pytest.raises(HTTPException) as exc:
        auth.reset_password(payload, db=dummy_db)

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid or expired reset link" in exc.value.detail


def test_me_unverified_user():
    user = DummyUser(email="user@example.com", email_verified_at=None)
    user.email_verification_token_hash = "abc123"
    result = auth.me(current=user)
    assert result.email_verified is False


def test_me_legacy_user_grandfathered_via_migration_backfill():
    from src.infrastructure.db.timezone_utils import ist_now

    user = DummyUser(email="legacy@example.com", email_verified_at=ist_now())
    result = auth.me(current=user)
    assert result.email_verified is True


def test_me_user_without_verified_at_is_not_verified():
    user = DummyUser(email="broken@example.com", email_verified_at=None)
    user.email_verification_token_hash = None
    result = auth.me(current=user)
    assert result.email_verified is False


def test_signup_with_optional_mobile(
    user_repo, settings_repo, mock_settings, mock_auth_email, dummy_db
):
    user_repo.by_email = None
    payload = auth.SignupRequest(
        email="new@example.com",
        password="Password123!",
        name="New User",
        mobile_number="9876543210",
    )

    auth.signup(payload, db=dummy_db)

    assert user_repo.created_user.mobile_number == "9876543210"


def test_signup_rejects_invalid_mobile():
    with pytest.raises(ValidationError):
        auth.SignupRequest(
            email="new@example.com",
            password="Password123!",
            name="New User",
            mobile_number="12345",
        )


def test_signup_unverified_resubmit_updates_mobile(
    user_repo, settings_repo, mock_auth_email, dummy_db
):
    existing_user = DummyUser(
        email="pending@example.com",
        email_verified_at=None,
        email_verification_token_hash="pending-hash",
        mobile_number="9876543210",
    )
    user_repo.by_email = existing_user
    payload = auth.SignupRequest(
        email="pending@example.com",
        password="Password123!",
        name="Pending",
        mobile_number="9123456789",
    )

    auth.signup(payload, db=dummy_db)

    assert existing_user.mobile_number == "9123456789"


def test_update_profile_mobile_only(user_repo, mock_auth_email, dummy_db):
    user = verified_dummy(id=1, email="user@example.com", mobile_number=None)
    payload = auth.UpdateProfileRequest(mobile_number="9876543210")

    result = auth.update_profile(payload, _mock_request(), current=user, db=dummy_db)

    assert user.mobile_number == "9876543210"
    assert result.verification_required is False
    assert result.email_verified is True
    assert len(mock_auth_email.verify) == 0


def test_update_profile_clears_mobile(user_repo, dummy_db):
    user = verified_dummy(id=1, email="user@example.com", mobile_number="9876543210")
    payload = auth.UpdateProfileRequest(mobile_number="")

    result = auth.update_profile(payload, _mock_request(), current=user, db=dummy_db)

    assert user.mobile_number is None
    assert result.verification_required is False


def test_update_profile_email_change_requires_verification(
    user_repo, mock_auth_email, mock_verify_password, dummy_db
):
    mock_verify_password.verified = True
    user = verified_dummy(id=1, email="old@example.com")
    user_repo.by_email = user
    payload = auth.UpdateProfileRequest(
        email="new@example.com",
        current_password="Password123!",
    )

    result = auth.update_profile(payload, _mock_request(), current=user, db=dummy_db)

    assert user.email == "new@example.com"
    assert user.email_verified_at is None
    assert result.verification_required is True
    assert result.email_verified is False
    assert len(mock_auth_email.verify) == 1
    assert mock_auth_email.verify[0][0] == "new@example.com"


def test_update_profile_email_change_requires_password(user_repo, dummy_db):
    user = verified_dummy(id=1, email="old@example.com")
    payload = auth.UpdateProfileRequest(email="new@example.com")

    with pytest.raises(HTTPException) as exc:
        auth.update_profile(payload, _mock_request(), current=user, db=dummy_db)

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc.value.detail == auth.PROFILE_EMAIL_PASSWORD_REQUIRED
    assert user.email == "old@example.com"


def test_update_profile_email_change_wrong_password(user_repo, mock_verify_password, dummy_db):
    mock_verify_password.verified = False
    user = verified_dummy(id=1, email="old@example.com")
    payload = auth.UpdateProfileRequest(
        email="new@example.com",
        current_password="WrongPassword123!",
    )

    with pytest.raises(HTTPException) as exc:
        auth.update_profile(payload, _mock_request(), current=user, db=dummy_db)

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert user.email == "old@example.com"


def test_update_profile_email_change_smtp_failure_rolls_back(
    user_repo, monkeypatch, mock_verify_password, dummy_db
):
    mock_verify_password.verified = True
    user = verified_dummy(id=1, email="old@example.com")
    user_repo.by_email = user

    class FailingEmailService:
        def is_smtp_configured(self):
            return True

        def send_verification_email(self, to_email, token):
            return False

    monkeypatch.setattr(auth, "AuthEmailService", FailingEmailService)
    payload = auth.UpdateProfileRequest(
        email="new@example.com",
        current_password="Password123!",
    )

    with pytest.raises(HTTPException) as exc:
        auth.update_profile(payload, _mock_request(), current=user, db=dummy_db)

    assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert user.email == "old@example.com"
    assert user.email_verified_at is not None


def test_update_profile_duplicate_email(user_repo, mock_verify_password, dummy_db):
    mock_verify_password.verified = True
    user = verified_dummy(id=1, email="user@example.com")
    taken = verified_dummy(id=2, email="taken@example.com")

    def lookup(email):
        if email == "taken@example.com":
            return taken
        if email == "user@example.com":
            return user
        return None

    user_repo.get_by_email = lookup
    payload = auth.UpdateProfileRequest(
        email="taken@example.com",
        current_password="Password123!",
    )

    with pytest.raises(HTTPException) as exc:
        auth.update_profile(payload, _mock_request(), current=user, db=dummy_db)

    assert exc.value.status_code == status.HTTP_409_CONFLICT


def test_me_includes_mobile_number():
    user = verified_dummy(email="user@example.com", mobile_number="9876543210")
    result = auth.me(current=user)
    assert result.mobile_number == "9876543210"
