"""
Regression tests: training with a ``sample_weight`` column but no ``position_id``.

Before the fix, the traditional (non-GroupKFold) split path passed the *full*
sample-weight array to ``model.fit`` while X/y were the 80% train split, raising
``ValueError: sample_weight.shape == (N,), expected (M,)``. This guards both the
verdict classifier and the price regressor against that mismatch.
"""

# ruff: noqa: E402 -- project root on path before services imports

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from services.ml_training_metadata import PRICE_TARGET_FEATURE_COLUMNS
from services.ml_training_service import MLTrainingService


def _frame_with_sample_weight(n: int = 120) -> pd.DataFrame:
    """Rows carrying sample_weight + entry_date but NO position_id (traditional split)."""
    rng = np.random.default_rng(7)
    rows = []
    for idx in range(n):
        day = date(2026, 1, 1) + timedelta(days=idx)
        row = {
            "ticker": f"S{idx % 6}.NS",
            "entry_date": day.isoformat(),
            "actual_pnl_pct": float(rng.normal(2.0, 5.0)),
            "exit_reason": "EMA9",
            "label": "buy" if idx % 2 == 0 else "avoid",
            "sample_weight": float(rng.uniform(0.5, 3.0)),
        }
        for col_idx, col in enumerate(PRICE_TARGET_FEATURE_COLUMNS):
            row[col] = float((idx + col_idx) % 9) + 0.5
        rows.append(row)
    return pd.DataFrame(rows)


def test_price_regressor_handles_sample_weight_without_position_id(tmp_path: Path):
    df = _frame_with_sample_weight()
    assert "position_id" not in df.columns
    assert "sample_weight" in df.columns

    trainer = MLTrainingService(models_dir=str(tmp_path))
    model_path, r2 = trainer.train_price_regressor(
        df=df,
        target_column="actual_pnl_pct",
        model_type="random_forest",
        model_save_path=tmp_path / "price.pkl",
        hyperparameters={"n_estimators": 10},
    )
    assert Path(model_path).is_file()
    assert isinstance(r2, float)


def test_verdict_classifier_handles_sample_weight_without_position_id(tmp_path: Path):
    df = _frame_with_sample_weight()

    trainer = MLTrainingService(models_dir=str(tmp_path))
    model_path, accuracy = trainer.train_verdict_classifier(
        df=df,
        model_type="random_forest",
        model_save_path=tmp_path / "verdict.pkl",
        hyperparameters={"n_estimators": 10},
    )
    assert Path(model_path).is_file()
    assert 0.0 <= accuracy <= 1.0
