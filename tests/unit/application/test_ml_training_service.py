# ruff: noqa: PLC0415

import json
from pathlib import Path

import pytest

from src.application.services.ml_training_service import MLTrainingService, TrainingJobConfig
from src.infrastructure.db.models import UserRole
from src.infrastructure.persistence.user_repository import UserRepository


@pytest.fixture
def admin_user(db_session):
    return UserRepository(db_session).create_user(
        email="admin@example.com", password="Admin@123", role=UserRole.ADMIN
    )


@pytest.fixture
def training_service(db_session, tmp_path: Path):
    artifact_dir = tmp_path / "models"
    return MLTrainingService(db_session, artifact_dir=artifact_dir)


def test_start_training_job_creates_pending_job(training_service, admin_user):
    config = TrainingJobConfig(
        model_type="verdict_classifier",
        algorithm="xgboost",
        training_data_path="data/mock.csv",
    )

    job = training_service.start_training_job(started_by=admin_user.id, config=config)

    assert job.id is not None
    assert job.status == "pending"
    assert job.model_type == "verdict_classifier"
    assert job.algorithm == "xgboost"


def test_run_training_job_creates_model_and_artifact(training_service, admin_user, tmp_path):
    config = TrainingJobConfig(
        model_type="verdict_classifier",
        algorithm="xgboost",
        training_data_path="data/mock.csv",
        hyperparameters={"max_depth": 6},
        auto_activate=True,
    )
    job = training_service.start_training_job(started_by=admin_user.id, config=config)

    training_service.run_training_job(job.id, config)

    stored_job = training_service.job_repo.get(job.id)
    assert stored_job.status == "completed"
    assert stored_job.accuracy is not None
    assert stored_job.model_path is not None
    artifact_path = Path(stored_job.model_path)
    assert artifact_path.exists()
    artifact = json.loads(artifact_path.read_text())
    assert artifact["model_type"] == "verdict_classifier"

    models = training_service.model_repo.list(model_type="verdict_classifier")
    assert len(models) == 1
    assert models[0].is_active is True


def test_run_training_job_failure_updates_status(training_service, admin_user, monkeypatch):
    config = TrainingJobConfig(
        model_type="verdict_classifier",
        algorithm="random_forest",
        training_data_path="data/mock.csv",
    )
    job = training_service.start_training_job(started_by=admin_user.id, config=config)

    def _fail(*_, **__):
        raise RuntimeError("boom")

    monkeypatch.setattr(training_service, "_write_model_artifact", _fail)

    with pytest.raises(RuntimeError):
        training_service.run_training_job(job.id, config)

    stored_job = training_service.job_repo.get(job.id)
    assert stored_job.status == "failed"
    assert stored_job.error_message == "boom"
