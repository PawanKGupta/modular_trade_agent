"""XGBoost verdict training must accept string label columns."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("xgboost")

from services.ml_training_service import MLTrainingService
from services.ml_verdict_feature_manifest import load_verdict_feature_manifest
from services.ml_verdict_service import MLVerdictService


def test_train_verdict_classifier_xgboost_accepts_string_labels(tmp_path: Path) -> None:
    rows = []
    labels = ("strong_buy", "buy", "watch", "avoid")
    for idx in range(40):
        rows.append(
            {
                "entry_date": f"2026-01-{(idx % 28) + 1:02d}",
                "label": labels[idx % len(labels)],
                "rsi": float(20 + (idx % 15)),
                "volume_ratio": 1.0 + (idx % 5) * 0.1,
                "alignment_score": float(idx % 10),
            }
        )
    df = pd.DataFrame(rows)
    svc = MLTrainingService(models_dir=str(tmp_path))
    model_path, accuracy = svc.train_verdict_classifier(
        df=df,
        test_size=0.25,
        model_type="xgboost",
        random_state=42,
        model_save_path=tmp_path / "verdict_xgb.pkl",
        hyperparameters={"n_estimators": 8, "max_depth": 3},
    )
    assert Path(model_path).is_file()
    assert accuracy >= 0.0

    manifest = load_verdict_feature_manifest(model_path)
    assert manifest is not None
    assert manifest.get("label_classes") == ["avoid", "buy", "strong_buy", "watch"]

    loaded = MLVerdictService(model_path=model_path)
    assert loaded.model_loaded
    assert loaded._verdict_classes == ["avoid", "buy", "strong_buy", "watch"]


def test_train_verdict_classifier_logistic_regression_sklearn_18(tmp_path: Path) -> None:
    """LogisticRegression must not pass removed sklearn 1.8 kwargs (e.g. multi_class)."""
    rows = [
        {
            "entry_date": f"2026-05-{(i % 20) + 1:02d}",
            "label": ("buy", "watch", "avoid", "strong_buy")[i % 4],
            "rsi": float(25 + i),
            "volume_ratio": 1.2,
        }
        for i in range(32)
    ]
    df = pd.DataFrame(rows)
    svc = MLTrainingService(models_dir=str(tmp_path))
    model_path, accuracy = svc.train_verdict_classifier(
        df=df,
        test_size=0.25,
        model_type="logistic_regression",
        random_state=42,
        model_save_path=tmp_path / "verdict_lr.pkl",
    )
    assert Path(model_path).is_file()
    assert accuracy >= 0.0
