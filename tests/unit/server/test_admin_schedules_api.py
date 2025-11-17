# ruff: noqa: PLC0415

"""
Unit tests for Admin Service Schedule Management API endpoints

Tests for:
- GET /admin/schedules
- GET /admin/schedules/{task_name}
- PUT /admin/schedules/{task_name}
- POST /admin/schedules/{task_name}/enable
- POST /admin/schedules/{task_name}/disable
"""

from datetime import time

import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from src.infrastructure.db.models import ServiceSchedule, UserRole
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.user_repository import UserRepository


@pytest.fixture
def client(db_session):
    """Create test client with database session"""
    from server.app.core.deps import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session):
    """Create an admin user for testing"""
    return UserRepository(db_session).create_user(
        email="admin@example.com",
        password="password123",
        role=UserRole.ADMIN,
    )


@pytest.fixture
def normal_user(db_session):
    """Create a normal user for testing"""
    return UserRepository(db_session).create_user(
        email="user@example.com",
        password="password123",
        role=UserRole.USER,
    )


@pytest.fixture
def sample_schedule(db_session):
    """Create a sample schedule for testing"""
    schedule = ServiceSchedule(
        task_name="premarket_retry",
        schedule_time=time(9, 0),
        enabled=True,
        is_hourly=False,
        is_continuous=False,
        end_time=None,
        description="Retries failed orders",
        created_at=ist_now(),
        updated_at=ist_now(),
    )
    db_session.add(schedule)
    db_session.commit()
    db_session.refresh(schedule)
    return schedule


def login(client: TestClient, email: str, password: str) -> str:
    """Helper to login and get token"""
    # Try signup first (in case user doesn't exist)
    signup_response = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password},
    )
    # If user already exists (409), that's fine - just proceed to login
    # If signup succeeded (200), we can use that token or login
    if signup_response.status_code == 200:
        return signup_response.json()["access_token"]

    # User exists, so login
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


def test_list_schedules_requires_admin(client, db_session, normal_user):
    """Test that listing schedules requires admin privileges"""
    token = login(client, normal_user.email, "password123")

    response = client.get(
        "/api/v1/admin/schedules",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_list_schedules_success(client, db_session, admin_user, sample_schedule):
    """Test successfully listing all schedules"""
    token = login(client, admin_user.email, "password123")

    response = client.get(
        "/api/v1/admin/schedules",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "schedules" in data
    assert len(data["schedules"]) >= 1
    assert any(s["task_name"] == "premarket_retry" for s in data["schedules"])


def test_get_schedule_requires_admin(client, db_session, normal_user):
    """Test that getting a schedule requires admin privileges"""
    token = login(client, normal_user.email, "password123")

    response = client.get(
        "/api/v1/admin/schedules/premarket_retry",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_get_schedule_success(client, db_session, admin_user, sample_schedule):
    """Test successfully getting a specific schedule"""
    token = login(client, admin_user.email, "password123")

    response = client.get(
        "/api/v1/admin/schedules/premarket_retry",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["task_name"] == "premarket_retry"
    assert data["schedule_time"] == "09:00"
    assert data["enabled"] is True


def test_get_schedule_not_found(client, db_session, admin_user):
    """Test getting a non-existent schedule"""
    token = login(client, admin_user.email, "password123")

    response = client.get(
        "/api/v1/admin/schedules/nonexistent_task",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_update_schedule_requires_admin(client, db_session, normal_user):
    """Test that updating a schedule requires admin privileges"""
    token = login(client, normal_user.email, "password123")

    response = client.put(
        "/api/v1/admin/schedules/premarket_retry",
        headers={"Authorization": f"Bearer {token}"},
        json={"schedule_time": "10:00", "enabled": True},
    )
    assert response.status_code == 403


def test_update_schedule_success(client, db_session, admin_user, sample_schedule):
    """Test successfully updating a schedule"""
    token = login(client, admin_user.email, "password123")

    response = client.put(
        "/api/v1/admin/schedules/premarket_retry",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "schedule_time": "10:00",
            "enabled": True,
            "is_hourly": False,
            "is_continuous": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["schedule"]["schedule_time"] == "10:00"
    assert data["requires_restart"] is True


def test_update_schedule_invalid_time_format(client, db_session, admin_user, sample_schedule):
    """Test updating schedule with invalid time format"""
    token = login(client, admin_user.email, "password123")

    response = client.put(
        "/api/v1/admin/schedules/premarket_retry",
        headers={"Authorization": f"Bearer {token}"},
        json={"schedule_time": "invalid", "enabled": True},
    )
    assert response.status_code == 400
    assert "format" in response.json()["detail"].lower()


def test_enable_schedule_success(client, db_session, admin_user, sample_schedule):
    """Test successfully enabling a schedule"""
    # First disable it
    sample_schedule.enabled = False
    db_session.commit()

    token = login(client, admin_user.email, "password123")

    response = client.post(
        "/api/v1/admin/schedules/premarket_retry/enable",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["schedule"]["enabled"] is True


def test_disable_schedule_success(client, db_session, admin_user, sample_schedule):
    """Test successfully disabling a schedule"""
    token = login(client, admin_user.email, "password123")

    response = client.post(
        "/api/v1/admin/schedules/premarket_retry/disable",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["schedule"]["enabled"] is False
