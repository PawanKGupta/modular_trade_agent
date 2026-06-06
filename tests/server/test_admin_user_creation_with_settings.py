"""
Test that admin user creation automatically creates default UserSettings
Bug fix: Previously, newly created users didn't have UserSettings until they manually saved settings
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient
from tests.support.auth_flow import signup_and_verify_payload


def _make_client() -> TestClient:
    """In-memory DB with explicit schema reset (avoids CI 'no such table: users' flakes)."""
    os.environ["DB_URL"] = "sqlite:///:memory:"
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if root not in sys.path:
        sys.path.append(root)

    import src.infrastructure.db.models  # noqa: F401, PLC0415
    from src.infrastructure.db.base import Base
    from src.infrastructure.db.session import engine

    try:
        Base.metadata.drop_all(bind=engine)
    except Exception:
        pass
    Base.metadata.create_all(bind=engine)

    from server.app.main import app  # noqa: PLC0415

    return TestClient(app)


def _signup_and_promote_admin(client: TestClient, email: str) -> dict:
    """Create user via signup and promote to admin; return auth headers."""
    from src.infrastructure.db.models import UserRole, Users  # noqa: PLC0415
    from src.infrastructure.db.session import SessionLocal  # noqa: PLC0415

    _auth_tokens = signup_and_verify_payload(client, None, {"email": email, "password": "Testpass123!", "name": "Admin User"})
    token = _auth_tokens["access_token"]

    with SessionLocal() as db:
        user = db.query(Users).filter(Users.email == email).first()
        assert user is not None
        user.role = UserRole.ADMIN
        user.is_active = True
        db.commit()

    return {"Authorization": f"Bearer {token}"}


@pytest.mark.unit
def test_admin_create_user_creates_default_settings():
    """
    BUG FIX: When admin creates a new user, UserSettings should be automatically created.

    Previously: UserSettings was not created → "User settings not found" error when starting service
    Now: UserSettings is auto-created with default paper trading mode
    """
    client = _make_client()
    admin_headers = _signup_and_promote_admin(client, "admin@test.com")

    response = client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={
            "email": "newuser@test.com",
            "password": "Testpass123!",
            "name": "New User",
            "role": "user",
        },
    )

    assert response.status_code == 200
    user_id = response.json()["id"]

    from src.infrastructure.db.models import UserSettings  # noqa: PLC0415
    from src.infrastructure.db.session import SessionLocal  # noqa: PLC0415

    with SessionLocal() as db:
        user_settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        assert user_settings is not None, "BUG: UserSettings should be auto-created for new users!"
        assert user_settings.trade_mode.value == "paper"


@pytest.mark.unit
def test_signup_also_creates_default_settings():
    """
    REGRESSION TEST: Signup flow should continue to create default UserSettings.
    This was already working correctly.
    """
    client = _make_client()

    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "signupuser@test.com", "password": "Testpass123!", "name": "Signup User"},
    )

    assert response.status_code == 200

    from src.infrastructure.db.models import Users, UserSettings  # noqa: PLC0415
    from src.infrastructure.db.session import SessionLocal  # noqa: PLC0415

    with SessionLocal() as db:
        user = db.query(Users).filter(Users.email == "signupuser@test.com").first()
        assert user is not None

        user_settings = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
        assert user_settings is not None, "UserSettings should be auto-created during signup"
        assert user_settings.trade_mode.value == "paper"


@pytest.mark.unit
def test_service_can_find_settings_for_new_user():
    """
    USER SCENARIO TEST: After admin creates a user, trading service finds their settings.

    Before fix: SettingsRepository.get_by_user_id() returned None → ValueError
    After fix: SettingsRepository.get_by_user_id() returns auto-created settings → Success
    """
    client = _make_client()
    admin_headers = _signup_and_promote_admin(client, "admin2@test.com")

    response = client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={
            "email": "serviceuser@test.com",
            "password": "Testpass123!",
            "name": "Service User",
            "role": "user",
        },
    )

    assert response.status_code == 200
    user_id = response.json()["id"]

    from src.infrastructure.db.session import SessionLocal  # noqa: PLC0415
    from src.infrastructure.persistence.settings_repository import (
        SettingsRepository,  # noqa: PLC0415
    )

    with SessionLocal() as db:
        settings_repo = SettingsRepository(db)
        settings = settings_repo.get_by_user_id(user_id)

        assert settings is not None, "BUG: Service cannot find settings for newly created user!"
        assert settings.user_id == user_id
        assert settings.trade_mode.value == "paper"
