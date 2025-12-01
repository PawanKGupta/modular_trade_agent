# ruff: noqa: E402, PLC0415, E501

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.routers import ml as ml_router
from server.app.routers.ml import get_ml_training_service
from src.application.services.ml_training_service import MLTrainingService, TrainingJobConfig
from src.infrastructure.db.models import UserRole
from src.infrastructure.persistence.user_repository import UserRepository


@pytest.fixture
def admin_user(db_session):
    return UserRepository(db_session).create_user(
        email="admin@example.com", password="Admin@123", role=UserRole.ADMIN
    )


@pytest.fixture
def normal_user(db_session):
    return UserRepository(db_session).create_user(
        email="user@example.com", password="User@123", role=UserRole.USER
    )


@pytest.fixture
def client(db_session):
    from server.app.core.deps import get_db

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
def ml_service(db_session, tmp_path):
    service = MLTrainingService(db_session, artifact_dir=tmp_path / "models")

    def override_service():
        return service

    app.dependency_overrides[get_ml_training_service] = override_service

    original_runner = ml_router._run_training_job_async

    def immediate_runner(job_id: int, config_data: dict):
        service.run_training_job(job_id, TrainingJobConfig(**config_data))

    ml_router._run_training_job_async = immediate_runner
    yield service
    app.dependency_overrides.pop(get_ml_training_service, None)
    ml_router._run_training_job_async = original_runner


def login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def wait_for_models(model_repo, timeout: float = 2.0):
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        models = model_repo.list()
        if models:
            return models
        time.sleep(0.05)
    return model_repo.list()


class TestMLTrainingAPI:
    def test_non_admin_cannot_start_training(self, client: TestClient, normal_user, ml_service):
        token = login(client, normal_user.email, "User@123")
        response = client.post(
            "/api/v1/admin/ml/train",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model_type": "verdict_classifier",
                "algorithm": "xgboost",
                "training_data_path": "data/mock.csv",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Admin only"

    def test_admin_can_start_training_job(self, client: TestClient, admin_user, ml_service):
        token = login(client, admin_user.email, "Admin@123")
        response = client.post(
            "/api/v1/admin/ml/train",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model_type": "verdict_classifier",
                "algorithm": "xgboost",
                "training_data_path": "data/mock.csv",
                "hyperparameters": {"max_depth": 6},
                "auto_activate": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] in ("pending", "completed")
        jobs = ml_service.job_repo.list()
        assert len(jobs) == 1
        assert wait_for_models(ml_service.model_repo)

    def test_list_jobs_endpoint(self, client: TestClient, admin_user, ml_service):
        token = login(client, admin_user.email, "Admin@123")
        # Seed a job
        client.post(
            "/api/v1/admin/ml/train",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model_type": "verdict_classifier",
                "algorithm": "xgboost",
                "training_data_path": "data/mock.csv",
            },
        )

        response = client.get(
            "/api/v1/admin/ml/jobs",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) >= 1

    def test_activate_model(self, client: TestClient, admin_user, ml_service):
        token = login(client, admin_user.email, "Admin@123")
        client.post(
            "/api/v1/admin/ml/train",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model_type": "verdict_classifier",
                "algorithm": "xgboost",
                "training_data_path": "data/mock.csv",
                "auto_activate": False,
            },
        )
        models = wait_for_models(ml_service.model_repo)
        assert models
        model = models[0]

        response = client.post(
            f"/api/v1/admin/ml/models/{model.id}/activate",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["model"]["is_active"] is True
