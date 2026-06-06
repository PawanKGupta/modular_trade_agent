"""Bulk analysis CSV columns (e.g. backtest_mode) must not become ML training features."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from services.ml_training_metadata import (
    BULK_ANALYSIS_CSV_METADATA,
    select_training_feature_columns,
    verdict_classifier_exclude_columns,
)
from services.ml_training_service import MLTrainingService


def test_backtest_mode_in_bulk_metadata_set():
    assert "backtest_mode" in BULK_ANALYSIS_CSV_METADATA


def test_select_training_feature_columns_drops_backtest_mode_and_strings():
    df = pd.DataFrame(
        {
            "ticker": ["A.NS", "B.NS"],
            "entry_date": ["2026-01-01", "2026-01-02"],
            "label": ["buy", "watch"],
            "backtest_mode": ["integrated", "simple_fallback"],
            "final_verdict": ["buy", "watch"],
            "backtest": ["{'score': 50}", "{'score': 0}"],
            "rsi": [28.0, 31.0],
            "dip_depth_from_20d_high_pct": [5.0, 3.0],
        }
    )
    cols = select_training_feature_columns(df, verdict_classifier_exclude_columns())
    assert "backtest_mode" not in cols
    assert "final_verdict" not in cols
    assert "backtest" not in cols
    assert "rsi" in cols
    assert "dip_depth_from_20d_high_pct" in cols


def test_train_verdict_classifier_ignores_backtest_mode_column(tmp_path):
    rows = []
    for idx in range(24):
        rows.append(
            {
                "entry_date": f"2026-01-{idx + 1:02d}",
                "label": "buy" if idx % 2 == 0 else "watch",
                "backtest_mode": "integrated",
                "final_verdict": "buy",
                "status": "success",
                "rsi": float(20 + idx),
                "volume_ratio": 1.1,
            }
        )
    df = pd.DataFrame(rows)
    svc = MLTrainingService(models_dir=str(tmp_path))
    model_path, _acc = svc.train_verdict_classifier(
        df=df,
        test_size=0.25,
        model_type="random_forest",
        random_state=42,
        model_save_path=tmp_path / "verdict_bulk_cols.pkl",
        hyperparameters={"n_estimators": 10, "max_depth": 4},
    )
    resolved = Path(model_path)
    features_file = resolved.parent / f"{resolved.stem}_features.txt"
    saved = [
        line.strip()
        for line in features_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert "backtest_mode" not in saved
    assert "final_verdict" not in saved
    assert "rsi" in saved


def test_select_training_feature_columns_requires_numeric_features():
    df = pd.DataFrame(
        {
            "entry_date": ["2026-01-01"],
            "label": ["buy"],
            "backtest_mode": ["integrated"],
        }
    )
    with pytest.raises(ValueError, match="No numeric feature columns"):
        select_training_feature_columns(df, verdict_classifier_exclude_columns())
