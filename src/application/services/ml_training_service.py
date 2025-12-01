from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.infrastructure.persistence.ml_model_repository import MLModelRepository
from src.infrastructure.persistence.ml_training_job_repository import (
    MLTrainingJobRepository,
)


@dataclass(slots=True)
class TrainingJobConfig:
    """Normalized configuration for running a training job."""

    model_type: str
    algorithm: str
    training_data_path: str
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    notes: str | None = None
    auto_activate: bool = False


class MLTrainingService:
    """Orchestrates ML training jobs and model versioning."""

    def __init__(self, db: Session, artifact_dir: str | Path | None = None) -> None:
        self.db = db
        self.job_repo = MLTrainingJobRepository(db)
        self.model_repo = MLModelRepository(db)
        self.artifact_dir = Path(artifact_dir) if artifact_dir else Path("models")
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def start_training_job(self, *, started_by: int, config: TrainingJobConfig):
        """Persist a new training job in pending state."""
        return self.job_repo.create(
            started_by=started_by,
            model_type=config.model_type,
            algorithm=config.algorithm,
            training_data_path=config.training_data_path,
        )

    def run_training_job(self, job_id: int, config: TrainingJobConfig) -> None:
        """Execute the training workflow and store resulting model artifacts."""
        # Mark job as running
        job = self.job_repo.update_status(job_id, status="running")
        try:
            version = self._next_version(config.model_type)
            accuracy = self._simulate_accuracy(config)
            artifact_path = self._write_model_artifact(
                model_type=config.model_type,
                algorithm=config.algorithm,
                version=version,
                training_data_path=config.training_data_path,
                hyperparameters=config.hyperparameters,
                notes=config.notes,
                metrics={"accuracy": accuracy},
            )
            logs = self._build_training_logs(config=config, version=version, accuracy=accuracy)

            # Record completion and metrics
            self.job_repo.update_status(
                job_id,
                status="completed",
                model_path=str(artifact_path),
                accuracy=accuracy,
                logs=logs,
            )

            # Persist model version
            is_first_model = self.model_repo.get_active(config.model_type) is None
            model = self.model_repo.create(
                model_type=config.model_type,
                version=version,
                model_path=str(artifact_path),
                training_job_id=job.id,
                created_by=job.started_by,
                accuracy=accuracy,
                is_active=False,
            )
            if config.auto_activate or is_first_model:
                self.model_repo.set_active(model.id)
        except Exception as exc:  # pragma: no cover - defensive, but tested via failure path
            self.job_repo.update_status(job_id, status="failed", error_message=str(exc))
            raise

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _next_version(self, model_type: str) -> str:
        """Return the next semantic version for a model type."""
        existing_models = self.model_repo.list(model_type=model_type)
        if not existing_models:
            return "v1"

        def _version_to_int(version: str) -> int:
            match = re.search(r"(\d+)", version)
            return int(match.group(1)) if match else 0

        max_version = max(_version_to_int(model.version) for model in existing_models)
        return f"v{max_version + 1}"

    def _simulate_accuracy(self, config: TrainingJobConfig) -> float:
        """Derive a deterministic accuracy score based on inputs."""
        base = 0.70
        if config.algorithm == "xgboost":
            base = 0.79
        elif config.algorithm == "random_forest":
            base = 0.75
        elif config.algorithm == "logistic_regression":
            base = 0.68

        hyperparam_boost = min(0.1, 0.02 * len(config.hyperparameters))
        accuracy = min(0.99, base + hyperparam_boost)
        return round(accuracy, 4)

    def _write_model_artifact(  # noqa: PLR0913
        self,
        *,
        model_type: str,
        algorithm: str,
        version: str,
        training_data_path: str,
        hyperparameters: dict[str, Any],
        notes: str | None,
        metrics: dict[str, Any],
    ) -> Path:
        """Persist a JSON artifact describing the trained model."""
        model_dir = self.artifact_dir / model_type
        model_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = model_dir / f"{algorithm}-{version}.json"
        payload = {
            "model_type": model_type,
            "algorithm": algorithm,
            "version": version,
            "training_data": training_data_path,
            "hyperparameters": hyperparameters,
            "notes": notes,
            "metrics": metrics,
        }
        artifact_path.write_text(json.dumps(payload, indent=2))
        return artifact_path

    def _build_training_logs(
        self, *, config: TrainingJobConfig, version: str, accuracy: float
    ) -> str:
        """Create a concise log string for audit/history."""
        hyper_count = len(config.hyperparameters)
        return (
            f"Training completed for {config.model_type} ({config.algorithm}) "
            f"version {version}. Accuracy={accuracy:.4f}. "
            f"Hyperparameters tuned={hyper_count}. "
            f"Data={config.training_data_path}."
        )
