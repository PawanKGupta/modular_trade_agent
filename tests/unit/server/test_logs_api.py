# ruff: noqa: E402, PLC0415, E501

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.app.core.deps import get_db
from server.app.main import app
from src.infrastructure.db.models import UserRole
from src.infrastructure.persistence.error_log_repository import ErrorLogRepository
from src.infrastructure.persistence.service_log_repository import ServiceLogRepository
from src.infrastructure.persistence.user_repository import UserRepository


@pytest.fixture
def admin_user(db_session):
    return UserRepository(db_session).create_user(
        email="admin-logs@example.com",
        password="Admin@123",
        role=UserRole.ADMIN,
    )


@pytest.fixture
def normal_user(db_session):
    return UserRepository(db_session).create_user(
        email="user-logs@example.com",
        password="User@123",
        role=UserRole.USER,
    )


@pytest.fixture
def other_user(db_session):
    return UserRepository(db_session).create_user(
        email="other-logs@example.com",
        password="Other@123",
        role=UserRole.USER,
    )


@pytest.fixture
def client(db_session):
    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seed_logs(db_session, normal_user, other_user):
    log_repo = ServiceLogRepository(db_session)
    error_repo = ErrorLogRepository(db_session)

    log_repo.create(
        user_id=normal_user.id,
        level="INFO",
        module="worker.analysis",
        message="Analysis task completed",
        context={"task": "analysis"},
    )
    log_repo.create(
        user_id=other_user.id,
        level="ERROR",
        module="worker.sell",
        message="Sell task failed",
        context={"task": "sell"},
    )

    user_error = error_repo.create(
        user_id=normal_user.id,
        error_type="ValueError",
        error_message="Something bad happened",
        traceback="Traceback info",
        context={"task": "analysis"},
    )
    error_repo.create(
        user_id=other_user.id,
        error_type="RuntimeError",
        error_message="Other user failure",
        traceback="Traceback info",
    )

    return {"user_error_id": user_error.id}


def login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


class TestUserLogAPI:
    def test_user_can_fetch_own_logs(self, client: TestClient, normal_user, seed_logs):
        token = login(client, normal_user.email, "User@123")
        response = client.get(
            "/api/v1/user/logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 1
        assert data["logs"][0]["module"] == "worker.analysis"

    def test_user_can_fetch_error_logs(self, client: TestClient, normal_user, seed_logs):
        token = login(client, normal_user.email, "User@123")
        response = client.get(
            "/api/v1/user/logs/errors",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["errors"]) == 1
        assert data["errors"][0]["error_type"] == "ValueError"


class TestAdminLogAPI:
    def test_admin_can_fetch_all_logs(self, client: TestClient, admin_user, normal_user, seed_logs):
        token = login(client, admin_user.email, "Admin@123")
        response = client.get(
            "/api/v1/admin/logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) >= 2

        user_filtered = client.get(
            "/api/v1/admin/logs",
            headers={"Authorization": f"Bearer {token}"},
            params={"user_id": normal_user.id},
        )
        assert user_filtered.status_code == 200
        user_data = user_filtered.json()
        assert len(user_data["logs"]) == 1
        assert user_data["logs"][0]["user_id"] == normal_user.id

    def test_admin_can_resolve_error(self, client: TestClient, admin_user, seed_logs, normal_user):
        token = login(client, admin_user.email, "Admin@123")
        response = client.post(
            "/api/v1/admin/logs/errors/{}/resolve".format(seed_logs["user_error_id"]),
            headers={"Authorization": f"Bearer {token}"},
            json={"notes": "Investigated and resolved."},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["error"]["resolved"] is True
        assert payload["error"]["resolution_notes"] == "Investigated and resolved."

    def test_non_admin_cannot_access_admin_logs(self, client: TestClient, normal_user):
        token = login(client, normal_user.email, "User@123")
        response = client.get(
            "/api/v1/admin/logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
