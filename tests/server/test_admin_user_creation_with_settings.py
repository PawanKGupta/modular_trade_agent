"""
Test that admin user creation automatically creates default UserSettings
Bug fix: Previously, newly created users didn't have UserSettings until they manually saved settings
"""

import os

os.environ["DB_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient  # noqa: E402

from server.app.main import app  # noqa: E402
from src.infrastructure.db.models import UserRole, Users, UserSettings  # noqa: E402
from src.infrastructure.db.session import SessionLocal  # noqa: E402
from src.infrastructure.persistence.settings_repository import SettingsRepository  # noqa: E402


def _signup_and_promote_admin(email: str) -> tuple[TestClient, dict]:
    """Helper to create and promote an admin user"""
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "testpass123", "name": "Admin User"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    # Promote to admin
    with SessionLocal() as db:
        user = db.query(Users).filter(Users.email == email).first()
        user.role = UserRole.ADMIN
        user.is_active = True
        db.commit()

    headers = {"Authorization": f"Bearer {token}"}
    return client, headers


def test_admin_create_user_creates_default_settings():
    """
    BUG FIX: When admin creates a new user, UserSettings should be automatically created.

    Previously: UserSettings was not created → "User settings not found" error when starting service
    Now: UserSettings is auto-created with default paper trading mode
    """
    client, admin_headers = _signup_and_promote_admin("admin@test.com")

    # Admin creates a new user
    response = client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={
            "email": "newuser@test.com",
            "password": "testpass123",
            "name": "New User",
            "role": "user",
        },
    )

    assert response.status_code == 200
    user_id = response.json()["id"]

    # Verify UserSettings was automatically created (THIS WAS THE BUG - it didn't exist)
    with SessionLocal() as db:
        user_settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        assert user_settings is not None, "BUG: UserSettings should be auto-created for new users!"
        assert user_settings.trade_mode.value == "paper"  # Default mode

        print(f"✅ Fix verified: UserSettings auto-created for user_id={user_id}")


def test_signup_also_creates_default_settings():
    """
    REGRESSION TEST: Signup flow should continue to create default UserSettings.
    This was already working correctly.
    """
    client = TestClient(app)

    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "signupuser@test.com", "password": "testpass123", "name": "Signup User"},
    )

    assert response.status_code == 200

    # Verify UserSettings was automatically created
    with SessionLocal() as db:
        user = db.query(Users).filter(Users.email == "signupuser@test.com").first()
        assert user is not None

        user_settings = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
        assert user_settings is not None, "UserSettings should be auto-created during signup"
        assert user_settings.trade_mode.value == "paper"

        print(f"✅ Regression test passed: UserSettings auto-created for user_id={user.id}")


def test_service_can_find_settings_for_new_user():
    """
    USER SCENARIO TEST: After admin creates a user, trading service finds their settings.

    Before fix: SettingsRepository.get_by_user_id() returned None → ValueError
    After fix: SettingsRepository.get_by_user_id() returns auto-created settings → Success
    """
    client, admin_headers = _signup_and_promote_admin("admin2@test.com")

    # Admin creates a new user
    response = client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={
            "email": "serviceuser@test.com",
            "password": "testpass123",
            "name": "Service User",
            "role": "user",
        },
    )

    assert response.status_code == 200
    user_id = response.json()["id"]

    # Simulate what the service does: try to get user settings
    with SessionLocal() as db:
        settings_repo = SettingsRepository(db)
        settings = settings_repo.get_by_user_id(user_id)

        # Before fix: settings would be None here, causing:
        # "ValueError: User settings not found for user_id=X"
        assert settings is not None, "BUG: Service cannot find settings for newly created user!"
        assert settings.user_id == user_id
        assert settings.trade_mode.value == "paper"

        print(f"✅ User scenario verified: Service can find settings for user_id={user_id}")
