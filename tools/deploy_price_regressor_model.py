#!/usr/bin/env python3
# ruff: noqa: PLC0415 -- deferred imports are intentional in this CLI tool
"""
Train and deploy the price regressor for MLPriceService.

Reads from the same historical-dataset CSV produced by ``build_historical_dataset.py``
(the verdict-classifier training data) and trains a regression model that predicts
``actual_pnl_pct`` — the real backtest exit return — instead of the rule-based EMA9
target distance used previously.

Feature contract:
  Writes a ``price_model_random_forest.price_features.json`` manifest alongside the pkl
  so MLPriceService can align inference features with training columns at load time.

Writes:
  - models/price_model_random_forest.pkl
  - models/price_model_random_forest.price_features.json
  - Registers + activates ``price_regressor`` in ``ml_models`` when --register-db is given.

Usage (repo root, .venv):
  python tools/deploy_price_regressor_model.py \\
      --training-csv data/ml_training_data_verdict_classifier.csv
  python tools/deploy_price_regressor_model.py \\
      --training-csv data/ml_training_data_verdict_classifier.csv --register-db
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ml_training_metadata import (  # noqa: E402
    PRICE_TARGET_FEATURE_COLUMNS,
    PRICE_TARGET_LABEL_COLUMN,
)

DEFAULT_MODEL_PATH = ROOT / "models" / "price_model_random_forest.pkl"
DEFAULT_TRAINING_CSV = ROOT / "data" / "training" / "verdict_classifier.csv"
_LABEL_COL = PRICE_TARGET_LABEL_COLUMN


def load_training_frame(csv_path: Path) -> pd.DataFrame:
    """
    Load and validate the historical dataset CSV.

    Validates that at least the label column and some curated features are present, and
    that the label is finite. MaxHold filtering and feature selection happen inside the
    shared trainer (``services.ml_training_service.train_price_regressor``).

    Raises ValueError if the label column is missing.
    """
    df = pd.read_csv(csv_path)

    if _LABEL_COL not in df.columns:
        raise ValueError(
            f"Training CSV is missing the '{_LABEL_COL}' column. "
            "Run build_historical_dataset.py to regenerate."
        )
    present = [c for c in PRICE_TARGET_FEATURE_COLUMNS if c in df.columns]
    if not present:
        raise ValueError(
            "Training CSV has none of the curated price features "
            f"{list(PRICE_TARGET_FEATURE_COLUMNS)}. Run build_historical_dataset.py."
        )

    df = df[np.isfinite(df[_LABEL_COL])]
    return df.reset_index(drop=True)


def train_and_save(
    frame: pd.DataFrame,
    *,
    model_path: Path,
) -> tuple[str, float]:
    """
    Train via the shared legacy trainer (curated features + MaxHold filter + manifest).

    Delegating here keeps the script and the admin UI training path on a single
    implementation. Returns (path, r2).
    """
    from services.ml_training_service import MLTrainingService

    trainer = MLTrainingService(models_dir=str(model_path.parent))
    return trainer.train_price_regressor(
        df=frame,
        target_column=_LABEL_COL,
        model_type="random_forest",
        model_save_path=model_path,
        hyperparameters={"n_estimators": 120, "max_depth": 12},
    )


def register_in_db(
    *, model_path: str, r2: float, training_csv: Path, version: str = "v1.0"
) -> None:
    """Persist job + model rows in the DB registry."""
    from dotenv import load_dotenv

    load_dotenv()
    from sqlalchemy import select

    from src.infrastructure.db.models import MLModel, MLTrainingJob
    from src.infrastructure.db.session import SessionLocal
    from src.infrastructure.db.timezone_utils import ist_now

    db = SessionLocal()
    try:
        job = MLTrainingJob(
            started_by=1,
            status="completed",
            model_type="price_regressor",
            algorithm="random_forest",
            training_data_path=training_csv.as_posix(),
            completed_at=ist_now(),
            model_path=model_path,
            accuracy=float(r2),
            logs=f"deploy_price_regressor_model.py R2={r2:.4f} label=actual_pnl_pct",
        )
        db.add(job)
        db.flush()

        stmt = select(MLModel).where(
            MLModel.model_type == "price_regressor",
            MLModel.version == version,
        )
        existing = db.execute(stmt).scalar_one_or_none()
        if existing:
            row = existing
            row.model_path = model_path
            row.accuracy = float(r2)
            row.training_job_id = job.id
            row.training_data_through_date = date.today()
            row.is_active = True
        else:
            row = MLModel(
                model_type="price_regressor",
                version=version,
                model_path=model_path,
                training_job_id=job.id,
                created_by=1,
                accuracy=float(r2),
                is_active=True,
                training_data_through_date=date.today(),
            )
            db.add(row)
            db.flush()

        others = db.execute(
            select(MLModel).where(
                MLModel.model_type == "price_regressor",
                MLModel.id != row.id,
            )
        ).scalars()
        for other in others:
            other.is_active = False

        db.commit()
        print(f"Registered and activated ml_models id={row.id} version={version}")
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--training-csv",
        type=Path,
        default=DEFAULT_TRAINING_CSV,
        help=f"Historical dataset CSV with actual_pnl_pct (default: {DEFAULT_TRAINING_CSV})",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help=f"Output pickle path (default: {DEFAULT_MODEL_PATH})",
    )
    parser.add_argument(
        "--register-db",
        action="store_true",
        help="Register model in ml_models and set active (requires DB_URL)",
    )
    args = parser.parse_args()

    csv_path = args.training_csv.resolve()
    if not csv_path.is_file():
        print(
            f"ERROR: Training CSV not found at {csv_path}\n"
            "Run: python scripts/build_historical_dataset.py "
            "--out data/ml_training_data_verdict_classifier.csv",
            file=sys.stderr,
        )
        return 1

    print(f"Loading training data from: {csv_path}")
    frame = load_training_frame(csv_path)
    print(
        f"Training rows: {len(frame)} "
        f"(label mean={frame[_LABEL_COL].mean():.2f}%, std={frame[_LABEL_COL].std():.2f}%)"
    )

    model_path, r2 = train_and_save(frame, model_path=args.model_path.resolve())
    print(f"Saved: {model_path}")
    print(f"Hold-out R2: {r2:.4f}")

    from services.ml_price_service import MLPriceService

    svc = MLPriceService(target_model_path=model_path)
    print(f"MLPriceService target_model_loaded: {svc.target_model_loaded}")
    print(f"MLPriceService feature_cols: {svc.feature_cols}")

    if args.register_db:
        register_in_db(
            model_path=model_path,
            r2=r2,
            training_csv=csv_path,
        )

    return 0 if svc.target_model_loaded else 1


if __name__ == "__main__":
    raise SystemExit(main())
