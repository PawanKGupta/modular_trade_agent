"""Guard against using trade_agent bulk exports as ML training CSVs."""

from __future__ import annotations

import pandas as pd
import pytest

from services.ml_training_metadata import (
    bulk_analysis_training_path_error,
    is_bulk_analysis_export_path,
)
from src.application.services.ml_training_service import MLTrainingService, TrainingJobConfig
from src.infrastructure.db.models import UserRole
from src.infrastructure.persistence.user_repository import UserRepository
from tests.support.test_users import create_verified_user


@pytest.fixture
def admin_user(db_session):
    return create_verified_user(
        UserRepository(db_session),
        email="bulk-guard-admin@example.com",
        password="Admin@123",
        role=UserRole.ADMIN,
    )


def test_is_bulk_analysis_export_path_detects_final_export():
    assert is_bulk_analysis_export_path("analysis_results/bulk_analysis_final_20260522_013532.csv")


def test_is_bulk_analysis_export_path_allows_ml_training_file():
    assert not is_bulk_analysis_export_path("data/ml_training_data_20260522.csv")


def test_bulk_analysis_training_path_error_by_filename(tmp_path, monkeypatch):
    monkeypatch.delenv("ML_ALLOW_BULK_ANALYSIS_TRAINING_CSV", raising=False)
    bulk = tmp_path / "bulk_analysis_final_20260522.csv"
    bulk.write_text("ticker,final_verdict\nA.NS,buy\n", encoding="utf-8")
    err = bulk_analysis_training_path_error(bulk)
    assert err is not None
    assert "bulk_analysis_final" in err


def test_bulk_analysis_training_path_error_by_header(tmp_path, monkeypatch):
    monkeypatch.delenv("ML_ALLOW_BULK_ANALYSIS_TRAINING_CSV", raising=False)
    path = tmp_path / "my_export.csv"
    pd.DataFrame(
        {
            "ticker": ["A.NS"],
            "final_verdict": ["buy"],
            "backtest_mode": ["integrated"],
            "combined_score": [40.0],
            "rsi": [25.0],
        }
    ).to_csv(path, index=False)
    err = bulk_analysis_training_path_error(path)
    assert err is not None
    assert "label" in err.lower()


def test_bulk_analysis_guard_skipped_with_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_ALLOW_BULK_ANALYSIS_TRAINING_CSV", "true")
    bulk = tmp_path / "bulk_analysis_final_test.csv"
    bulk.write_text("x\n", encoding="utf-8")
    assert bulk_analysis_training_path_error(bulk) is None


def test_ml_training_service_validate_raises(db_session, tmp_path, monkeypatch):
    monkeypatch.delenv("ML_ALLOW_BULK_ANALYSIS_TRAINING_CSV", raising=False)
    bulk = tmp_path / "bulk_analysis_final_x.csv"
    bulk.write_text("ticker,status\nX,ok\n", encoding="utf-8")
    service = MLTrainingService(db_session, artifact_dir=tmp_path / "models")
    with pytest.raises(ValueError, match="bulk screener"):
        service.validate_training_csv_for_ml(bulk)


def test_run_training_job_rejects_bulk_path(db_session, admin_user, tmp_path, monkeypatch):
    monkeypatch.delenv("ML_ALLOW_BULK_ANALYSIS_TRAINING_CSV", raising=False)
    bulk = tmp_path / "bulk_analysis_final_job.csv"
    pd.DataFrame(
        {"ticker": ["A"], "final_verdict": ["buy"], "backtest_mode": ["integrated"]}
    ).to_csv(bulk, index=False)
    service = MLTrainingService(db_session, artifact_dir=tmp_path / "models")
    config = TrainingJobConfig(
        model_type="verdict_classifier",
        algorithm="random_forest",
        training_data_path=str(bulk),
    )
    job = service.start_training_job(started_by=admin_user.id, config=config)
    service.run_training_job(job.id, config=config)
    failed = service.job_repo.get(job.id)
    assert failed.status == "failed"
    assert failed.error_message is not None
    assert "bulk" in failed.error_message.lower()
