#!/usr/bin/env python3
"""
Train and deploy the default price regressor for MLPriceService.

Uses the same feature names and column order as ``MLPriceService._extract_target_features``
so inference ``list(features.values())`` matches sklearn training columns.

Writes:
  - models/price_model_random_forest.pkl
  - data/ml_training_data_price.csv (bootstrap training set)
  - Registers + activates ``price_regressor`` in ``ml_models`` when DB_URL is set.

Usage (repo root, .venv):
  python tools/deploy_price_regressor_model.py
  python tools/deploy_price_regressor_model.py --register-db
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Must match services/ml_price_service.py::_extract_target_features dict key order.
PRICE_TARGET_FEATURE_COLUMNS = [
    "current_price",
    "rsi_10",
    "ema200",
    "recent_high",
    "recent_low",
    "volume_ratio",
    "alignment_score",
    "volatility",
    "momentum",
    "resistance_distance",
]

DEFAULT_MODEL_PATH = ROOT / "models" / "price_model_random_forest.pkl"
DEFAULT_TRAINING_CSV = ROOT / "data" / "ml_training_data_price.csv"


def _rows_from_bulk_exports() -> list[dict[str, float]]:
    """Best-effort rows from analysis_results bulk CSVs (rule-based target % as label)."""
    rows: list[dict[str, float]] = []
    results_dir = ROOT / "analysis_results"
    if not results_dir.is_dir():
        return rows

    for path in sorted(results_dir.glob("bulk_analysis_final_*.csv")):
        try:
            frame = pd.read_csv(path)
        except (OSError, ValueError):
            continue
        needed = {"last_close", "target", "rsi"}
        if not needed.issubset(frame.columns):
            continue
        for _, r in frame.iterrows():
            try:
                price = float(r["last_close"])
                target = float(r["target"])
            except (TypeError, ValueError):
                continue
            if price <= 0 or target <= 0 or not np.isfinite(price) or not np.isfinite(target):
                continue
            vol_ratio = 1.0
            if "today_vol" in frame.columns and "avg_vol" in frame.columns:
                try:
                    avg_v = float(r["avg_vol"])
                    today_v = float(r["today_vol"])
                    if avg_v > 0:
                        vol_ratio = today_v / avg_v
                except (TypeError, ValueError):
                    pass
            score = float(r.get("combined_score", 5) or 5)
            rows.append(
                {
                    "current_price": price,
                    "rsi_10": float(r["rsi"]),
                    "ema200": price * (0.92 if r.get("is_above_ema200") else 1.02),
                    "recent_high": price * 1.05,
                    "recent_low": price * 0.95,
                    "volume_ratio": vol_ratio,
                    "alignment_score": min(10.0, max(0.0, score)),
                    "volatility": 2.5,
                    "momentum": 1.0,
                    "resistance_distance": max(0.0, (target - price) / price * 100),
                    "actual_pnl_pct": (target / price - 1.0) * 100.0,
                }
            )
    return rows


def build_training_frame(
    *, n_synthetic: int = 1200, seed: int = 42, end_date: date | None = None
) -> pd.DataFrame:
    """Bootstrap training data aligned with MLPriceService feature contract."""
    rng = np.random.default_rng(seed)
    end = end_date or date.today()
    start = end - timedelta(days=900)
    span_days = max((end - start).days, 1)
    n_tail = min(max(n_synthetic // 10, 40), n_synthetic // 2)
    n_main = n_synthetic - n_tail
    tail_days = min(14, span_days + 1)

    def _feature_block(price: float) -> dict[str, float]:
        rsi_10 = float(rng.uniform(15.0, 45.0))
        ema200 = price * float(rng.uniform(0.88, 1.05))
        recent_high = price * float(rng.uniform(1.01, 1.12))
        recent_low = price * float(rng.uniform(0.88, 0.99))
        volume_ratio = float(rng.uniform(0.6, 2.5))
        alignment_score = float(rng.uniform(2.0, 10.0))
        volatility = float(rng.uniform(0.8, 5.5))
        momentum = float(rng.uniform(-8.0, 12.0))
        resistance_distance = (recent_high - price) / price * 100.0
        base_pnl = (
            4.0
            + 0.35 * alignment_score
            + 0.25 * momentum
            - 0.08 * volatility
            - 0.05 * abs(rsi_10 - 28.0)
            + 0.5 * min(max(resistance_distance, 0), 15)
        )
        return {
            "current_price": price,
            "rsi_10": rsi_10,
            "ema200": ema200,
            "recent_high": recent_high,
            "recent_low": recent_low,
            "volume_ratio": volume_ratio,
            "alignment_score": alignment_score,
            "volatility": volatility,
            "momentum": momentum,
            "resistance_distance": resistance_distance,
            "actual_pnl_pct": base_pnl + float(rng.normal(0, 1.5)),
        }

    rows: list[dict] = []
    for _ in range(n_main):
        entry = start + timedelta(days=int(rng.integers(0, span_days + 1)))
        row = {"ticker": f"STOCK{len(rows) % 50}.NS", "entry_date": entry.isoformat()}
        row.update(_feature_block(float(rng.uniform(80.0, 4000.0))))
        rows.append(row)

    for j in range(n_tail):
        entry = end - timedelta(days=j % tail_days)
        row = {"ticker": f"STOCK{len(rows) % 50}.NS", "entry_date": entry.isoformat()}
        row.update(_feature_block(float(rng.uniform(80.0, 4000.0))))
        rows.append(row)

    synthetic = pd.DataFrame(rows)
    bulk_rows = _rows_from_bulk_exports()
    if bulk_rows:
        bulk_frame = pd.DataFrame(bulk_rows)
        if "entry_date" not in bulk_frame.columns:
            bulk_frame["entry_date"] = end.isoformat()
        synthetic = pd.concat([synthetic, bulk_frame], ignore_index=True)

    return synthetic[PRICE_TARGET_FEATURE_COLUMNS + ["actual_pnl_pct", "entry_date", "ticker"]]


def train_and_save(
    frame: pd.DataFrame,
    *,
    model_path: Path,
    training_csv: Path,
) -> tuple[str, float]:
    from services.ml_training_service import MLTrainingService

    training_csv.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(training_csv, index=False)

    trainer = MLTrainingService(models_dir=str(model_path.parent))
    path, r2 = trainer.train_price_regressor(
        df=frame,
        target_column="actual_pnl_pct",
        model_type="random_forest",
        model_save_path=model_path,
        hyperparameters={"n_estimators": 120, "max_depth": 12},
    )
    return path, r2


def register_in_db(*, model_path: str, r2: float, training_csv: Path, version: str = "v1.0") -> None:
    """Persist job + model rows without importing server/persistence package __init__."""
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
            logs=f"deploy_price_regressor_model.py bootstrap R2={r2:.4f}",
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
        "--model-path",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help=f"Output pickle path (default: {DEFAULT_MODEL_PATH})",
    )
    parser.add_argument(
        "--training-csv",
        type=Path,
        default=DEFAULT_TRAINING_CSV,
        help=f"Saved training CSV (default: {DEFAULT_TRAINING_CSV})",
    )
    parser.add_argument(
        "--register-db",
        action="store_true",
        help="Register model in ml_models and set active (requires DB_URL)",
    )
    parser.add_argument("--synthetic-rows", type=int, default=1200)
    args = parser.parse_args()

    frame = build_training_frame(n_synthetic=args.synthetic_rows)
    print(f"Training rows: {len(frame)} (bulk-augmented: {len(frame) > args.synthetic_rows})")

    model_path, r2 = train_and_save(
        frame, model_path=args.model_path.resolve(), training_csv=args.training_csv.resolve()
    )
    print(f"Saved: {model_path}")
    print(f"Hold-out R2: {r2:.4f}")

    from services.ml_price_service import MLPriceService

    svc = MLPriceService(target_model_path=model_path)
    print(f"MLPriceService target_model_loaded: {svc.target_model_loaded}")

    if args.register_db:
        register_in_db(
            model_path=model_path,
            r2=r2,
            training_csv=args.training_csv.resolve(),
        )

    return 0 if svc.target_model_loaded else 1


if __name__ == "__main__":
    raise SystemExit(main())
