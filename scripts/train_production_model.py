"""
Train production verdict model on full Phase 2 dataset.

Architecture: RandomForest (n_estimators=400) + manual Platt scaling.
  - Last 15% of rows (temporal) → Platt calibration set
  - Remaining 85% → RF training

Saves model to models/verdict_model_random_forest.pkl with classes_=["avoid","buy"]
so MLVerdictService maps index 0 → "avoid", index 1 → "buy".
Updates models/model_versions.json.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.ml_calibrated_rf import ProductionCalibratedRF
from services.ml_training_metadata import (
    select_training_feature_columns,
    verdict_classifier_exclude_columns,
)
from services.ml_verdict_feature_manifest import write_verdict_feature_manifest

DATA_PATH = r"C:\Personal\Projects\TradingView\data_backup\ml_training_data_phase2.csv"
MODEL_OUT = project_root / "models" / "verdict_model_random_forest.pkl"
VERSIONS_PATH = project_root / "models" / "model_versions.json"

EXTRA_EXCLUDE = {
    "pe",
    "pb",
    "holding_days",
    "exit_date",
    "exit_reason",
    "actual_pnl_pct",
    "label",
    "sample_weight",
    "position_id",
    "ticker",
    "initial_entry_date",
    "initial_entry_price",
    "entry_date",
    "fill_price",
    "fill_quantity",
}

CAL_FRACTION = 0.15


def main() -> None:
    print("=== Production Model Training ===")
    print(f"Data: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH, parse_dates=False)
    df["entry_date"] = pd.to_datetime(df["entry_date"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values("entry_date").reset_index(drop=True)
    print(f"Loaded {len(df)} rows ({df['entry_date'].min()} → {df['entry_date'].max()})")

    # Label
    y = (df["actual_pnl_pct"] >= 1.0).astype(int).values
    print(f"Label: {y.sum()} wins ({y.mean():.1%}) of {len(y)} rows")

    # Features
    exclude = verdict_classifier_exclude_columns()
    feature_cols = select_training_feature_columns(df, exclude)
    feature_cols = [c for c in feature_cols if c not in EXTRA_EXCLUDE]
    print(f"Features: {len(feature_cols)}")

    X = df[feature_cols].fillna(0).values

    # Temporal split: last 15% → calibration
    cal_n = max(50, int(CAL_FRACTION * len(X)))
    tr_end = len(X) - cal_n
    X_tr, y_tr = X[:tr_end], y[:tr_end]
    X_cal, y_cal = X[tr_end:], y[tr_end:]

    print(f"\nSplit → train={len(X_tr)}  calibration={len(X_cal)}")
    print(f"  Train period: {df['entry_date'].iloc[0]} → {df['entry_date'].iloc[tr_end - 1]}")
    print(f"  Cal period:   {df['entry_date'].iloc[tr_end]} → {df['entry_date'].iloc[-1]}")

    if len(np.unique(y_cal)) < 2:
        raise ValueError(
            f"Calibration set has only one class: {np.unique(y_cal)}. "
            "Increase CAL_FRACTION or check data."
        )

    # Train RF
    print("\nTraining RandomForest (n_estimators=400, class_weight='balanced')...")
    rf = RandomForestClassifier(
        n_estimators=400,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(X_tr, y_tr)

    # Calibrate
    print("Fitting Platt scaler on calibration set...")
    raw_cal = rf.predict_proba(X_cal)[:, 1].reshape(-1, 1)
    platt = LogisticRegression()
    platt.fit(raw_cal, y_cal)

    # Evaluate on calibration set (proxy — not a true holdout)
    cal_scores = platt.predict_proba(raw_cal)[:, 1]
    brier = brier_score_loss(y_cal, cal_scores)
    auc = roc_auc_score(y_cal, cal_scores)
    print("\nCalibration set metrics (in-sample for calibration split):")
    print(f"  AUC={auc:.3f}  Brier={brier:.3f}")

    # Score distribution
    all_scores_raw = rf.predict_proba(X)[:, 1].reshape(-1, 1)
    all_scores = platt.predict_proba(all_scores_raw)[:, 1]
    print("\nFull-dataset score distribution:")
    print(
        f"  min={all_scores.min():.3f}  p25={np.percentile(all_scores, 25):.3f}  "
        f"p50={np.percentile(all_scores, 50):.3f}  p75={np.percentile(all_scores, 75):.3f}  "
        f"max={all_scores.max():.3f}"
    )

    for t in (0.55, 0.60, 0.65):
        n = (all_scores >= t).sum()
        print(f"  >= {t}: {n} rows ({n / len(all_scores):.1%})")

    # Top features
    imp = pd.Series(rf.feature_importances_, index=feature_cols).nlargest(10)
    print("\nTop 10 features:")
    for feat, val in imp.items():
        print(f"  {feat:<40} {val:.4f}")

    # Save model
    model = ProductionCalibratedRF(rf, platt)
    MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_OUT)
    print(f"\nModel saved → {MODEL_OUT}")

    # Save feature list sidecar
    feat_txt = MODEL_OUT.parent / f"{MODEL_OUT.stem}_features.txt"
    feat_txt.write_text("\n".join(feature_cols), encoding="utf-8")
    print(f"Features sidecar → {feat_txt}")

    # Write versioned manifest
    write_verdict_feature_manifest(MODEL_OUT, feature_cols, label_classes=["avoid", "buy"])
    print(f"Manifest → {MODEL_OUT.parent / (MODEL_OUT.stem + '.verdict_features.json')}")

    # Update model_versions.json
    trained_at = datetime.now(tz=UTC).isoformat()
    config_key = "rsi10_vol10_support20"
    entry = {
        "version": 2,
        "path": str(MODEL_OUT.resolve()),
        "config": {
            "rsi_period": 10,
            "volume_exhaustion_lookback_daily": 10,
            "support_resistance_lookback_daily": 20,
        },
        "trained_date": trained_at,
        "training_rows": int(len(df)),
        "calibration_rows": int(len(X_cal)),
        "feature_count": int(len(feature_cols)),
        "label": "actual_pnl_pct >= 1.0 (Label 1)",
        "architecture": "RandomForest(400) + Platt scaling (manual)",
        "production_threshold": 0.60,
        "performance": {
            "cal_set_auc": round(float(auc), 3),
            "cal_set_brier": round(float(brier), 3),
            "wfv_fold1_auc": 0.723,
            "wfv_fold2_auc": 0.770,
            "wfv_fold3_auc": 0.737,
            "wfv_fold1_pf": 13.807,
            "wfv_fold2_pf": 6.602,
            "wfv_fold3_pf": 7.510,
        },
    }

    if VERSIONS_PATH.exists():
        with open(VERSIONS_PATH, encoding="utf-8") as f:
            versions = json.load(f)
    else:
        versions = {"verdict_models": {}, "price_models": {}}

    versions["verdict_models"][config_key] = entry
    with open(VERSIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(versions, f, indent=2)
    print(f"model_versions.json updated (version=2, key={config_key})")

    print("\n=== Done ===")
    print("Next: run the service and confirm ml_verdict_service loads the new model.")


if __name__ == "__main__":
    main()
