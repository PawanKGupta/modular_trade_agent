from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from src.application.services.ml_incremental_training import subset_for_incremental_training
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.ml_model_repository import MLModelRepository
from src.infrastructure.persistence.ml_training_job_repository import (
    MLTrainingJobRepository,
)

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    """Normalize nested metadata for JSON logging columns."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, date):
        return value.isoformat()
    return value


@dataclass(slots=True)
class TrainingJobConfig:
    """Normalized configuration for running a training job."""

    model_type: str
    algorithm: str
    training_data_path: str
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    notes: str | None = None
    auto_activate: bool = False
    incremental_training: bool = True
    training_run_end_date: date | None = None


class MLTrainingService:
    """Orchestrate admin ML training via sklearn-backed ``services/ml_training_service``."""

    def __init__(self, db: Session, artifact_dir: str | Path | None = None) -> None:
        self.db = db
        self.job_repo = MLTrainingJobRepository(db)
        self.model_repo = MLModelRepository(db)
        self.artifact_dir = Path(artifact_dir) if artifact_dir else Path("models")
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def sklearn_trainer_factory(self):  # noqa: ANN201
        """Return the legacy sklearn orchestrator used by ``trade_agent`` exports."""
        from services.ml_training_service import (  # noqa: PLC0415
            MLTrainingService as LegacyTrainer,
        )

        return LegacyTrainer(str(self.artifact_dir))

    def resolve_training_csv(self, raw_path: str) -> Path:
        """Absolute path to the CSV as seen by the API worker (respects cwd, e.g. /app)."""
        candidate = Path(raw_path)
        if candidate.is_absolute():
            return candidate.resolve()
        return (Path.cwd() / candidate).resolve()

    def start_training_job(self, *, started_by: int, config: TrainingJobConfig):
        """Persist a new training job in pending state."""
        return self.job_repo.create(
            started_by=started_by,
            model_type=config.model_type,
            algorithm=config.algorithm,
            training_data_path=config.training_data_path,
        )

    def run_training_job(self, job_id: int, config: TrainingJobConfig) -> None:
        """Execute sklearn training + persist deterministic artifacts/metadata."""
        job = self.job_repo.update_status(job_id, status="running")
        incremental_diag: dict[str, Any] | None = None

        try:
            csv_path = self.resolve_training_csv(config.training_data_path)
            if not csv_path.is_file():
                raise FileNotFoundError(f"Training CSV not found at {csv_path}")

            raw_frame = pd.read_csv(csv_path)
            version = self._next_semantic_version(config.model_type)
            run_through = config.training_run_end_date or ist_now().date()

            active = self.model_repo.get_active(config.model_type)
            prior_through = (
                active.training_data_through_date
                if (
                    active
                    and config.incremental_training
                    and getattr(active, "training_data_through_date", None) is not None
                )
                else None
            )

            train_frame, incremental_diag = subset_for_incremental_training(
                raw_frame,
                train_through=run_through,
                incremental=config.incremental_training,
                prior_through_inclusive=prior_through,
            )

            model_dir = self.artifact_dir / config.model_type
            model_dir.mkdir(parents=True, exist_ok=True)
            algo_slug = config.algorithm.replace(" ", "_")
            artifact_prefix = model_dir / f"{algo_slug}-{version}"
            target_pickle = artifact_prefix.with_suffix(".pkl")

            trainer = self.sklearn_trainer_factory()

            hp_filtered = {
                key: val
                for key, val in config.hyperparameters.items()
                if key not in ("test_size", "random_state", "target_column")
            }

            if config.model_type == "verdict_classifier":
                if config.algorithm not in ("random_forest", "xgboost", "logistic_regression"):
                    raise ValueError(
                        f"'{config.algorithm}' unsupported for verdict_classifier training jobs"
                    )
                model_disk_path, accuracy = trainer.train_verdict_classifier(
                    df=train_frame,
                    test_size=float(config.hyperparameters.get("test_size", 0.2)),
                    model_type=config.algorithm,
                    random_state=int(config.hyperparameters.get("random_state", 42)),
                    model_save_path=str(target_pickle.resolve()),
                    hyperparameters=hp_filtered or None,
                )
                metric_summary = accuracy
            elif config.model_type == "price_regressor":
                if config.algorithm not in ("random_forest", "xgboost"):
                    raise ValueError(
                        f"'{config.algorithm}' unsupported for price_regressor training jobs"
                    )
                target_column = str(config.hyperparameters.get("target_column", "actual_pnl_pct"))
                model_disk_path, r_squared = trainer.train_price_regressor(
                    df=train_frame,
                    target_column=target_column,
                    test_size=float(config.hyperparameters.get("test_size", 0.2)),
                    model_type=config.algorithm,
                    random_state=int(config.hyperparameters.get("random_state", 42)),
                    model_save_path=str(target_pickle.resolve()),
                    hyperparameters=hp_filtered or None,
                )
                metric_summary = float(r_squared)
            else:
                raise ValueError(f"Unsupported admin model_type: {config.model_type}")

            resolved_pickled = Path(model_disk_path).resolve()
            watermark = date.fromisoformat(str(incremental_diag["max_date"]))

            feature_sidecar = resolved_pickled.with_name(f"{resolved_pickled.stem}_features.txt")

            manifest = {
                "model_type": config.model_type,
                "algorithm": config.algorithm,
                "version": version,
                "training_csv": csv_path.as_posix(),
                "incremental_diag": incremental_diag,
                "metrics": {"accuracy_like": metric_summary},
                "training_data_through_date": watermark.isoformat(),
                "artifacts": {
                    "model_pickled_joblib": resolved_pickled.as_posix(),
                    "feature_columns_text": (
                        feature_sidecar.as_posix() if feature_sidecar.is_file() else None
                    ),
                },
                "notes": config.notes,
            }

            manifest_path = artifact_prefix.with_suffix(".meta.json")
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            log_preview = json.dumps({"manifest_path": manifest_path.as_posix(), **manifest})

            self.job_repo.update_status(
                job_id,
                status="completed",
                model_path=str(resolved_pickled),
                accuracy=float(metric_summary),
                logs=log_preview[:15800],
            )

            replacement_active_candidates = self.model_repo.get_active(config.model_type)

            persisted_model = self.model_repo.create(
                model_type=config.model_type,
                version=version,
                model_path=str(resolved_pickled),
                training_job_id=job.id,
                created_by=job.started_by,
                accuracy=float(metric_summary),
                training_data_through_date=watermark,
                is_active=False,
            )

            if config.auto_activate or replacement_active_candidates is None:
                self.model_repo.set_active(persisted_model.id)
        except Exception as exc:
            failure_payload = _json_safe(
                {
                    "error": str(exc),
                    "incremental_diag": incremental_diag,
                    "incremental_requested": getattr(config, "incremental_training", None),
                    "incremental_through": getattr(config, "training_run_end_date", None),
                }
            )
            self.job_repo.update_status(
                job_id,
                status="failed",
                error_message=str(exc),
                logs=json.dumps(failure_payload)[:15800],
            )
            logger.warning(
                "ML training job %s failed (%s): %s",
                job_id,
                type(exc).__name__,
                exc,
            )

    def _next_semantic_version(self, model_type: str) -> str:
        existing = self.model_repo.list(model_type=model_type)
        if not existing:
            return "v1"

        def _digits(version: str) -> int:
            match = re.search(r"(\d+)", version)
            return int(match.group(1)) if match else 0

        next_num = max(_digits(model.version) for model in existing) + 1
        return f"v{next_num}"
