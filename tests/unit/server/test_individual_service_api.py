# ruff: noqa: PLC0415

"""
Unit tests for Individual Service Management API endpoints

Tests for:
- GET /service/individual/status
- POST /service/individual/start
- POST /service/individual/stop
- POST /service/individual/run-once
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from src.infrastructure.db.models import UserRole
from src.infrastructure.persistence.user_repository import UserRepository
from tests.support.test_users import create_verified_user


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
def sample_user(db_session):
    """Create a sample user for testing"""
    return create_verified_user(
        UserRepository(db_session),
        email="test@example.com",
        password="Password123!",
        role=UserRole.USER,
    )


def login(client: TestClient, db_session, email: str, password: str) -> str:
    from tests.support.auth_flow import get_access_token

    return get_access_token(client, db_session, email, password)


def test_get_individual_services_status_requires_auth(client):
    """Test that getting individual services status requires authentication"""
    response = client.get("/api/v1/user/service/individual/status")
    assert response.status_code == 401


def test_get_individual_services_status_success(client, db_session, sample_user):
    """Test successfully getting individual services status"""
    token = login(client, db_session, sample_user.email, "Password123!")

    with patch(
        "src.application.services.individual_service_manager.IndividualServiceManager.get_status"
    ) as mock_get_status:
        mock_get_status.return_value = {
            "premarket_retry": {
                "is_running": False,
                "started_at": None,
                "last_execution_at": None,
                "next_execution_at": None,
                "process_id": None,
                "schedule_enabled": True,
            }
        }

        response = client.get(
            "/api/v1/user/service/individual/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "services" in data
        assert "premarket_retry" in data["services"]


def test_start_individual_service_requires_auth(client):
    """Test that starting individual service requires authentication"""
    response = client.post(
        "/api/v1/user/service/individual/start",
        json={"task_name": "premarket_retry"},
    )
    assert response.status_code == 401


def test_start_individual_service_success(client, db_session, sample_user):
    """Test successfully starting an individual service"""
    token = login(client, db_session, sample_user.email, "Password123!")

    with patch(
        "src.application.services.individual_service_manager.IndividualServiceManager.start_service"
    ) as mock_start:
        mock_start.return_value = (True, "Service started successfully")

        response = client.post(
            "/api/v1/user/service/individual/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"task_name": "premarket_retry"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "started" in data["message"].lower()


def test_start_individual_service_failure(client, db_session, sample_user):
    """Test starting individual service when it fails"""
    token = login(client, db_session, sample_user.email, "Password123!")

    with patch(
        "src.application.services.individual_service_manager.IndividualServiceManager.start_service"
    ) as mock_start:
        mock_start.return_value = (False, "Unified service is running")

        response = client.post(
            "/api/v1/user/service/individual/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"task_name": "premarket_retry"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


def test_stop_individual_service_success(client, db_session, sample_user):
    """Test successfully stopping an individual service"""
    token = login(client, db_session, sample_user.email, "Password123!")

    with patch(
        "src.application.services.individual_service_manager.IndividualServiceManager.stop_service"
    ) as mock_stop:
        mock_stop.return_value = (True, "Service stopped successfully")

        response = client.post(
            "/api/v1/user/service/individual/stop",
            headers={"Authorization": f"Bearer {token}"},
            json={"task_name": "premarket_retry"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "stopped" in data["message"].lower()


def test_run_task_once_success(client, db_session, sample_user):
    """Test successfully running a task once"""
    token = login(client, db_session, sample_user.email, "Password123!")

    with (
        patch(
            "src.application.services.individual_service_manager.IndividualServiceManager.run_once"
        ) as mock_run_once,
        patch(
            "src.application.services.conflict_detection_service.ConflictDetectionService.check_conflict"
        ) as mock_check_conflict,
    ):
        mock_check_conflict.return_value = (False, "")
        mock_run_once.return_value = (True, "Task execution started", {"execution_id": 123})

        response = client.post(
            "/api/v1/user/service/individual/run-once",
            headers={"Authorization": f"Bearer {token}"},
            json={"task_name": "premarket_retry", "execution_type": "run_once"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["execution_id"] == 123
        assert data["has_conflict"] is False


def test_run_task_once_with_conflict(client, db_session, sample_user):
    """Test running a task once when there's a conflict"""
    token = login(client, db_session, sample_user.email, "Password123!")

    with (
        patch(
            "src.application.services.individual_service_manager.IndividualServiceManager.run_once"
        ) as mock_run_once,
        patch(
            "src.application.services.conflict_detection_service.ConflictDetectionService.check_conflict"
        ) as mock_check_conflict,
    ):
        mock_check_conflict.return_value = (
            True,
            "Task is currently running in unified service",
        )
        mock_run_once.return_value = (True, "Task execution started", {"execution_id": 123})

        response = client.post(
            "/api/v1/user/service/individual/run-once",
            headers={"Authorization": f"Bearer {token}"},
            json={"task_name": "premarket_retry"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["has_conflict"] is True
        assert data["conflict_message"] is not None
