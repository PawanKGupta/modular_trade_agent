# ruff: noqa: E402, PLC0415, E501

from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.routers import ml as ml_router
from server.app.routers.ml import get_ml_training_service
from src.application.services.ml_training_service import MLTrainingService, TrainingJobConfig
from src.infrastructure.db.models import UserRole
from src.infrastructure.persistence.user_repository import UserRepository


def _write_verdict_csv(path: Path) -> None:
    rows = []
    for idx in range(30):
        day = date(2026, 3, 1) + timedelta(days=idx)
        rows.append(
            {
                "entry_date": day.isoformat(),
                "rsi": float(idx % 30),
                "label": "buy" if idx % 2 == 0 else "watch",
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


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
    csv_path = tmp_path / "verdict_train.csv"
    _write_verdict_csv(csv_path)
    service = MLTrainingService(db_session, artifact_dir=tmp_path / "models")
    service._fixture_training_csv = csv_path  # type: ignore[attr-defined]

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
    def test_admin_train_rejected_when_csv_missing(
        self, client: TestClient, admin_user, ml_service, tmp_path: Path
    ):
        """Missing CSV path yields 400 and no orphaned background failure noise."""
        token = login(client, admin_user.email, "Admin@123")
        phantom = tmp_path / "does_not_exist_verdict.csv"
        assert not phantom.exists()
        response = client.post(
            "/api/v1/admin/ml/train",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model_type": "verdict_classifier",
                "algorithm": "random_forest",
                "training_data_path": str(phantom),
            },
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()

    def test_non_admin_cannot_start_training(self, client: TestClient, normal_user, ml_service):
        token = login(client, normal_user.email, "User@123")
        csv_path = ml_service._fixture_training_csv
        response = client.post(
            "/api/v1/admin/ml/train",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model_type": "verdict_classifier",
                "algorithm": "random_forest",
                "training_data_path": str(csv_path),
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Admin only"

    def test_admin_can_start_training_job(self, client: TestClient, admin_user, ml_service):
        token = login(client, admin_user.email, "Admin@123")
        csv_path = ml_service._fixture_training_csv
        response = client.post(
            "/api/v1/admin/ml/train",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model_type": "verdict_classifier",
                "algorithm": "random_forest",
                "training_data_path": str(csv_path),
                "hyperparameters": {"n_estimators": 20},
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
        csv_path = ml_service._fixture_training_csv
        # Seed a job
        client.post(
            "/api/v1/admin/ml/train",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model_type": "verdict_classifier",
                "algorithm": "random_forest",
                "training_data_path": str(csv_path),
                "incremental_training": False,
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
        csv_path = ml_service._fixture_training_csv
        client.post(
            "/api/v1/admin/ml/train",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model_type": "verdict_classifier",
                "algorithm": "random_forest",
                "training_data_path": str(csv_path),
                "auto_activate": False,
                "incremental_training": False,
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
