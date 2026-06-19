# ruff: noqa: PLC0415

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from services.ml_verdict_feature_manifest import (
    load_verdict_feature_manifest,
    verdict_feature_manifest_path,
)
from src.application.services.ml_training_service import MLTrainingService, TrainingJobConfig
from src.infrastructure.db.models import UserRole
from src.infrastructure.persistence.ml_model_repository import MLModelRepository
from src.infrastructure.persistence.user_repository import UserRepository
from tests.support.test_users import create_verified_user


def _write_verdict_csv(path: Path) -> None:
    rows = []
    for idx in range(40):
        day = date(2026, 1, 1) + timedelta(days=idx)
        rows.append(
            {
                "entry_date": day.isoformat(),
                "rsi": float(idx % 50),
                "label": "buy" if idx % 2 == 0 else "watch",
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


@pytest.fixture
def admin_user(db_session):
    return create_verified_user(
        UserRepository(db_session),
        email="admin@example.com",
        password="Admin@123",
        role=UserRole.ADMIN,
    )


@pytest.fixture
def training_service(db_session, tmp_path: Path):
    artifact_dir = tmp_path / "models"
    return MLTrainingService(db_session, artifact_dir=artifact_dir)


def test_start_training_job_creates_pending_job(training_service, admin_user):
    config = TrainingJobConfig(
        model_type="verdict_classifier",
        algorithm="random_forest",
        training_data_path="data/mock.csv",
    )

    job = training_service.start_training_job(started_by=admin_user.id, config=config)

    assert job.id is not None
    assert job.status == "pending"
    assert job.model_type == "verdict_classifier"
    assert job.algorithm == "random_forest"


def test_run_training_job_creates_model_and_artifact(training_service, admin_user, tmp_path: Path):
    csv_path = tmp_path / "verdict_train.csv"
    _write_verdict_csv(csv_path)

    config = TrainingJobConfig(
        model_type="verdict_classifier",
        algorithm="random_forest",
        training_data_path=str(csv_path),
        hyperparameters={"n_estimators": 20},
        auto_activate=True,
        incremental_training=False,
    )
    job = training_service.start_training_job(started_by=admin_user.id, config=config)

    training_service.run_training_job(job.id, config)

    stored_job = training_service.job_repo.get(job.id)
    assert stored_job.status == "completed"
    assert stored_job.accuracy is not None
    assert stored_job.model_path is not None
    model_path = Path(stored_job.model_path)
    assert model_path.exists()
    assert model_path.suffix == ".pkl"

    mf_path = verdict_feature_manifest_path(model_path)
    assert mf_path.is_file(), "train_verdict_classifier should emit .verdict_features.json"
    loaded = load_verdict_feature_manifest(model_path)
    assert loaded is not None and len(loaded["feature_names"]) >= 1

    models = training_service.model_repo.list(model_type="verdict_classifier")
    assert len(models) == 1
    assert models[0].is_active is True
    assert models[0].training_data_through_date == date(2026, 2, 9)


def test_run_training_job_incremental_second_pass(training_service, admin_user, tmp_path: Path):
    csv_path = tmp_path / "verdict_train_span.csv"
    rows = []
    for idx in range(15):
        day = date(2026, 2, 1) + timedelta(days=idx)
        rows.append(
            {
                "entry_date": day.isoformat(),
                "rsi": float(idx),
                "label": "buy" if idx % 2 == 0 else "watch",
            }
        )
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    baseline_config = TrainingJobConfig(
        model_type="verdict_classifier",
        algorithm="random_forest",
        training_data_path=str(csv_path),
        hyperparameters={"n_estimators": 10},
        incremental_training=False,
        auto_activate=True,
        training_run_end_date=date(2026, 2, 10),
    )
    job1 = training_service.start_training_job(started_by=admin_user.id, config=baseline_config)
    training_service.run_training_job(job1.id, baseline_config)

    repo = MLModelRepository(training_service.db)
    active_after_first = repo.get_active("verdict_classifier")
    assert active_after_first and active_after_first.training_data_through_date == date(2026, 2, 10)

    follow_config = TrainingJobConfig(
        model_type="verdict_classifier",
        algorithm="random_forest",
        training_data_path=str(csv_path),
        hyperparameters={"n_estimators": 12},
        incremental_training=True,
        auto_activate=False,
        training_run_end_date=date(2026, 2, 15),
    )
    job2 = training_service.start_training_job(started_by=admin_user.id, config=follow_config)
    training_service.run_training_job(job2.id, follow_config)

    all_models = sorted(repo.list(model_type="verdict_classifier"), key=lambda m: m.id)
    latest_model = all_models[-1]
    assert latest_model.training_data_through_date == date(2026, 2, 15)
    assert latest_model.is_active is False
    first_row = repo.get(active_after_first.id)
    assert first_row is not None and first_row.is_active


def test_deploy_to_canonical_copies_pkl_and_sidecars(training_service, admin_user, tmp_path: Path):
    """deploy_to_canonical copies the versioned pkl + companion files to the canonical paths."""
    csv_path = tmp_path / "verdict_train.csv"
    _write_verdict_csv(csv_path)

    config = TrainingJobConfig(
        model_type="verdict_classifier",
        algorithm="random_forest",
        training_data_path=str(csv_path),
        hyperparameters={"n_estimators": 10},
        auto_activate=False,
        incremental_training=False,
    )
    job = training_service.start_training_job(started_by=admin_user.id, config=config)
    training_service.run_training_job(job.id, config)

    models = training_service.model_repo.list(model_type="verdict_classifier")
    assert models, "a model should have been persisted"
    model = models[0]

    canonical_pkl = training_service.deploy_to_canonical(model.id)
    assert canonical_pkl.is_file(), "canonical pkl must exist after deploy"
    assert canonical_pkl.name == "verdict_model_random_forest.pkl"

    # Verify the canonical pkl content matches the source (same bytes)
    src_pkl = Path(model.model_path)
    assert canonical_pkl.read_bytes() == src_pkl.read_bytes()


def test_activate_and_deploy_sets_db_flag_and_deploys(training_service, admin_user, tmp_path: Path):
    """activate_and_deploy marks active in DB and deploys canonical artifact."""
    csv_path = tmp_path / "verdict_train.csv"
    _write_verdict_csv(csv_path)

    # Train v1 with auto_activate so it becomes the active baseline.
    config_v1 = TrainingJobConfig(
        model_type="verdict_classifier",
        algorithm="random_forest",
        training_data_path=str(csv_path),
        hyperparameters={"n_estimators": 10},
        auto_activate=True,
        incremental_training=False,
    )
    job1 = training_service.start_training_job(started_by=admin_user.id, config=config_v1)
    training_service.run_training_job(job1.id, config_v1)

    # Train v2 without auto_activate — it stays inactive because v1 is active.
    config_v2 = TrainingJobConfig(
        model_type="verdict_classifier",
        algorithm="random_forest",
        training_data_path=str(csv_path),
        hyperparameters={"n_estimators": 12},
        auto_activate=False,
        incremental_training=False,
    )
    job2 = training_service.start_training_job(started_by=admin_user.id, config=config_v2)
    training_service.run_training_job(job2.id, config_v2)

    models = sorted(
        training_service.model_repo.list(model_type="verdict_classifier"), key=lambda m: m.id
    )
    v2 = models[-1]
    assert not v2.is_active, "v2 should be inactive before activate_and_deploy"

    updated, canonical_path = training_service.activate_and_deploy(v2.id)

    assert updated.is_active
    assert canonical_path.is_file()
    assert canonical_path.name == "verdict_model_random_forest.pkl"
    # v1 must have been deactivated
    v1 = training_service.model_repo.get(models[0].id)
    assert not v1.is_active


def test_deploy_to_canonical_missing_artifact_raises(training_service, admin_user, tmp_path: Path):
    """deploy_to_canonical raises FileNotFoundError when model pkl is gone from disk."""
    csv_path = tmp_path / "verdict_train.csv"
    _write_verdict_csv(csv_path)

    config = TrainingJobConfig(
        model_type="verdict_classifier",
        algorithm="random_forest",
        training_data_path=str(csv_path),
        hyperparameters={"n_estimators": 10},
        auto_activate=False,
        incremental_training=False,
    )
    job = training_service.start_training_job(started_by=admin_user.id, config=config)
    training_service.run_training_job(job.id, config)

    models = training_service.model_repo.list(model_type="verdict_classifier")
    model = models[0]

    # Remove the pkl from disk to simulate a missing artifact.
    Path(model.model_path).unlink()

    with pytest.raises(FileNotFoundError):
        training_service.deploy_to_canonical(model.id)


def test_run_training_job_failure_updates_status(training_service, admin_user, tmp_path: Path):
    csv_path = tmp_path / "verdict_train.csv"
    _write_verdict_csv(csv_path)

    config = TrainingJobConfig(
        model_type="verdict_classifier",
        algorithm="random_forest",
        training_data_path=str(csv_path),
    )
    job = training_service.start_training_job(started_by=admin_user.id, config=config)

    def _boom_factory():
        raise RuntimeError("boom")

    training_service.sklearn_trainer_factory = _boom_factory  # type: ignore[method-assign]

    # Failures are recorded on the job; exceptions are not re-raised (background-safe).
    training_service.run_training_job(job.id, config)

    stored_job = training_service.job_repo.get(job.id)
    assert stored_job.status == "failed"
    assert stored_job.error_message == "boom"
