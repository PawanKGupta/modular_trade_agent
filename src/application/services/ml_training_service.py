from __future__ import annotations

import json
import logging
import re
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from services.ml_training_metadata import (
    bulk_analysis_training_path_error,
    validate_training_csv_for_model_type,
)
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

    def validate_training_csv_for_ml(self, csv_path: Path) -> None:
        """
        Reject trade_agent bulk screener exports mistaken for ML training files.

        Raises:
            ValueError: When ``csv_path`` matches bulk export patterns or headers.
        """
        message = bulk_analysis_training_path_error(csv_path)
        if message:
            raise ValueError(message)

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
            self.validate_training_csv_for_ml(csv_path)

            raw_frame = pd.read_csv(csv_path)
            target_column = str(config.hyperparameters.get("target_column", "actual_pnl_pct"))
            validate_training_csv_for_model_type(
                raw_frame,
                config.model_type,
                target_column=target_column,
            )
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
            verdict_manifest_path = resolved_pickled.with_name(
                f"{resolved_pickled.stem}.verdict_features.json"
            )

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
                    "verdict_features_manifest": (
                        verdict_manifest_path.as_posix()
                        if verdict_manifest_path.is_file()
                        else None
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
                try:
                    self.deploy_to_canonical(persisted_model.id)
                except Exception as deploy_exc:
                    logger.warning(
                        "Auto-activate: model %s active in DB but canonical deploy failed: %s",
                        persisted_model.id,
                        deploy_exc,
                    )
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

    # Maps model_type → canonical pkl stem under self.artifact_dir.parent
    _CANONICAL_STEM: dict[str, str] = {
        "verdict_classifier": "verdict_model_random_forest",
    }

    def deploy_to_canonical(self, model_id: int) -> Path:
        """Copy a versioned model artifact to the canonical runtime path.

        MLVerdictService always loads from models/verdict_model_random_forest.pkl
        (and its two companion files). This method bridges the DB registry to the
        runtime by overwriting those canonical files with the activated version.

        Returns the canonical pkl path that was written.
        Raises ValueError if model_id not found or model_type has no canonical mapping.
        """
        model = self.model_repo.get(model_id)
        if model is None:
            raise ValueError(f"Model {model_id} not found")

        stem = self._CANONICAL_STEM.get(model.model_type)
        if stem is None:
            raise ValueError(
                f"No canonical path registered for model_type '{model.model_type}'. "
                f"Known types: {list(self._CANONICAL_STEM)}"
            )

        src_pkl = Path(model.model_path)
        if not src_pkl.is_file():
            raise FileNotFoundError(
                f"Model artifact not found on disk: {src_pkl}. "
                "Re-train or restore the file before activating."
            )

        canonical_dir = self.artifact_dir.parent  # models/
        dst_pkl = canonical_dir / f"{stem}.pkl"

        shutil.copy2(src_pkl, dst_pkl)
        logger.info("Deployed %s → %s", src_pkl.name, dst_pkl)

        # Copy companion sidecars when present (features txt + verdict manifest)
        for src_suffix, dst_suffix in (
            ("_features.txt", "_features.txt"),
            (".verdict_features.json", ".verdict_features.json"),
        ):
            src_side = src_pkl.with_name(src_pkl.stem + src_suffix)
            dst_side = canonical_dir / f"{stem}{dst_suffix}"
            if src_side.is_file():
                shutil.copy2(src_side, dst_side)
                logger.info("Deployed sidecar %s → %s", src_side.name, dst_side.name)

        return dst_pkl

    def register_external_model(  # noqa: PLR0913
        self,
        *,
        registered_by: int,
        model_type: str,
        model_path: str,
        version: str,
        accuracy: float | None = None,
        training_data_through_date: date | None = None,
        notes: str | None = None,
        auto_activate: bool = False,
    ):
        """Register a model artifact trained outside the UI into the DB registry.

        Creates a synthetic completed import job so the FK constraint is satisfied,
        then creates the model row. Optionally deploys to the canonical runtime path.
        Returns the persisted MLModel.
        """
        src = Path(model_path)
        if not src.is_file():
            raise FileNotFoundError(
                f"Model artifact not found: {model_path}. "
                "Provide the absolute path as it appears inside the container."
            )

        # Synthetic import job — satisfies the NOT NULL FK without polluting the
        # training job list with a pending/running entry.
        job = self.job_repo.create(
            started_by=registered_by,
            model_type=model_type,
            algorithm="external_import",
            training_data_path=model_path,
        )
        self.job_repo.update_status(
            job.id,
            status="completed",
            model_path=model_path,
            accuracy=accuracy,
            logs=f"Registered externally via admin API. notes={notes!r}",
        )

        model = self.model_repo.create(
            model_type=model_type,
            version=version,
            model_path=model_path,
            training_job_id=job.id,
            created_by=registered_by,
            accuracy=accuracy,
            is_active=False,
            training_data_through_date=training_data_through_date,
        )

        if auto_activate:
            self.model_repo.set_active(model.id)
            try:
                self.deploy_to_canonical(model.id)
            except Exception as exc:
                logger.warning(
                    "register_external_model: model %s set active but canonical deploy failed: %s",
                    model.id,
                    exc,
                )
            model = self.model_repo.get(model.id)

        logger.info(
            "Registered external model %s/%s (id=%s) from %s",
            model_type,
            version,
            model.id,
            model_path,
        )
        return model

    def activate_and_deploy(self, model_id: int) -> tuple:
        """Set model active in DB and deploy artifact to the canonical runtime path.

        Returns (updated_model, canonical_pkl_path).
        """
        updated_model = self.model_repo.set_active(model_id)
        canonical_path = self.deploy_to_canonical(model_id)
        return updated_model, canonical_path
