"""
Phase 2 — Baseline Walk-Forward Validation

3-fold expanding-window validation comparing:
  - ML filter (RandomForest + CalibratedClassifierCV)
  - Regime baseline: india_vix < 20 AND nifty_trend >= 0
  - Unfiltered baseline (all trades)

Folds:
  1: Train 2015-2020, Test 2021
  2: Train 2015-2022, Test 2023
  3: Train 2015-2023, Test 2024

Decision Gate A (ALL folds must pass):
  - Win rate delta >= +3pp vs unfiltered
  - Profit factor >= 1.10
  - Coverage >= 40%
  - Brier score < 0.20
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.ml_training_metadata import (
    select_training_feature_columns,
    verdict_classifier_exclude_columns,
)

DATA_PATH = r"C:\Personal\Projects\TradingView\data_backup\ml_training_data_phase1.csv"

FOLDS = [
    {
        "name": "Fold 1",
        "train_end": "2020-12-31",
        "test_start": "2021-01-01",
        "test_end": "2021-12-31",
    },
    {
        "name": "Fold 2",
        "train_end": "2022-12-31",
        "test_start": "2023-01-01",
        "test_end": "2023-12-31",
    },
    {
        "name": "Fold 3",
        "train_end": "2023-12-31",
        "test_start": "2024-01-01",
        "test_end": "2024-12-31",
    },
]

GATE_A = {
    "win_rate_delta_pp": 3.0,
    "profit_factor": 1.10,
    "coverage_pct": 40.0,
    "brier_score": 0.20,
}

ML_THRESHOLD = 0.55  # confidence cutoff for ML pass/fail


def profit_factor(pnl_series: pd.Series) -> float:
    wins = pnl_series[pnl_series > 0].sum()
    losses = abs(pnl_series[pnl_series < 0].sum())
    return round(wins / losses, 3) if losses > 0 else float("inf")


def evaluate_filter(test_df: pd.DataFrame, mask: pd.Series, label: str) -> dict:
    filtered = test_df[mask]
    if len(filtered) == 0:
        return {
            "label": label,
            "n": 0,
            "coverage": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_pnl": 0.0,
        }
    win_rate = (filtered["actual_pnl_pct"] >= 1.0).mean() * 100
    pf = profit_factor(filtered["actual_pnl_pct"])
    avg_pnl = filtered["actual_pnl_pct"].mean()
    coverage = len(filtered) / len(test_df) * 100
    return {
        "label": label,
        "n": len(filtered),
        "coverage": round(coverage, 1),
        "win_rate": round(win_rate, 1),
        "profit_factor": pf,
        "avg_pnl": round(avg_pnl, 2),
    }


class CalibratedRF:
    """RF + Platt scaling on a held-out calibration set.
    cv='prefit' was removed in sklearn 1.4; this replaces it directly."""

    def __init__(self, rf: RandomForestClassifier, calibrator: LogisticRegression):
        self.rf = rf
        self.calibrator = calibrator
        self.classes_ = rf.classes_

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        raw = self.rf.predict_proba(X)[:, 1].reshape(-1, 1)
        cal = self.calibrator.predict_proba(raw)
        return cal


def train_model(train_df: pd.DataFrame, feature_cols: list[str]) -> CalibratedRF:
    X = train_df[feature_cols].fillna(0).values
    y = (train_df["actual_pnl_pct"] >= 1.0).astype(int).values

    cal_n = max(50, int(0.15 * len(X)))
    X_tr, X_cal = X[:-cal_n], X[-cal_n:]
    y_tr, y_cal = y[:-cal_n], y[-cal_n:]

    rf = RandomForestClassifier(
        n_estimators=400,
        max_depth=None,
        min_samples_leaf=1,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(X_tr, y_tr)

    # Platt scaling on held-out calibration set
    cal_raw = rf.predict_proba(X_cal)[:, 1].reshape(-1, 1)
    calibrator = LogisticRegression()
    calibrator.fit(cal_raw, y_cal)

    return CalibratedRF(rf, calibrator)


def run_fold(fold: dict, df: pd.DataFrame, feature_cols: list[str]) -> dict:
    train_mask = df["entry_date"] <= fold["train_end"]
    test_mask = (df["entry_date"] >= fold["test_start"]) & (df["entry_date"] <= fold["test_end"])

    train_df = df[train_mask].sort_values("entry_date").reset_index(drop=True)
    test_df = df[test_mask].sort_values("entry_date").reset_index(drop=True)

    print(f"\n{'=' * 60}")
    print(f"{fold['name']}: Train={len(train_df)} rows  Test={len(test_df)} rows")
    print(f"  Train: up to {fold['train_end']}")
    print(f"  Test:  {fold['test_start']} to {fold['test_end']}")

    if len(train_df) < 100 or len(test_df) < 20:
        print("  SKIP: insufficient data")
        return {}

    # Train ML model
    print("  Training ML model...")
    model = train_model(train_df, feature_cols)

    # ML predictions on test set
    X_test = test_df[feature_cols].fillna(0).values
    y_test = (test_df["actual_pnl_pct"] >= 1.0).astype(int).values
    proba = model.predict_proba(X_test)
    pos_idx = list(model.classes_).index(1)
    ml_scores = proba[:, pos_idx]

    # Metrics
    auc = roc_auc_score(y_test, ml_scores)
    brier = brier_score_loss(y_test, ml_scores)

    # Filters
    ml_mask = pd.Series(ml_scores >= ML_THRESHOLD, index=test_df.index)
    regime_mask = (test_df["india_vix"] < 20) & (test_df["nifty_trend"] >= 0)
    all_mask = pd.Series([True] * len(test_df), index=test_df.index)

    unfiltered = evaluate_filter(test_df, all_mask, "Unfiltered")
    ml_result = evaluate_filter(test_df, ml_mask, f"ML (>={ML_THRESHOLD})")
    regime_result = evaluate_filter(test_df, regime_mask, "Regime (VIX<20 & trend>=0)")

    # Win rate deltas vs unfiltered
    ml_result["win_rate_delta"] = round(ml_result["win_rate"] - unfiltered["win_rate"], 1)
    regime_result["win_rate_delta"] = round(regime_result["win_rate"] - unfiltered["win_rate"], 1)

    # Gate A evaluation for ML
    gate_pass = (
        ml_result["win_rate_delta"] >= GATE_A["win_rate_delta_pp"]
        and ml_result["profit_factor"] >= GATE_A["profit_factor"]
        and ml_result["coverage"] >= GATE_A["coverage_pct"]
        and brier < GATE_A["brier_score"]
    )

    # Print results
    print(f"\n  {'Metric':<22} {'Unfiltered':>12} {'ML Filter':>12} {'Regime':>12}")
    print(f"  {'-' * 60}")
    print(
        f"  {'Trades (n)':<22} {unfiltered['n']:>12} {ml_result['n']:>12} {regime_result['n']:>12}"
    )
    print(
        f"  {'Coverage %':<22} {unfiltered['coverage']:>12} {ml_result['coverage']:>12} {regime_result['coverage']:>12}"
    )
    print(
        f"  {'Win Rate %':<22} {unfiltered['win_rate']:>12} {ml_result['win_rate']:>12} {regime_result['win_rate']:>12}"
    )
    print(
        f"  {'Win Rate Delta pp':<22} {'—':>12} {ml_result['win_rate_delta']:>12} {regime_result['win_rate_delta']:>12}"
    )
    print(
        f"  {'Profit Factor':<22} {unfiltered['profit_factor']:>12} {ml_result['profit_factor']:>12} {regime_result['profit_factor']:>12}"
    )
    print(
        f"  {'Avg PnL %':<22} {unfiltered['avg_pnl']:>12} {ml_result['avg_pnl']:>12} {regime_result['avg_pnl']:>12}"
    )
    print(f"  {'ROC AUC':<22} {'—':>12} {auc:.3f}{'':>6} {'—':>12}")
    print(f"  {'Brier Score':<22} {'—':>12} {brier:.3f}{'':>6} {'—':>12}")
    print(f"\n  Gate A: {'PASS ✓' if gate_pass else 'FAIL ✗'}")
    for k, threshold in GATE_A.items():
        if k == "brier_score":
            actual = round(brier, 3)
            ok = actual < threshold
        elif k == "win_rate_delta_pp":
            actual = ml_result["win_rate_delta"]
            ok = actual >= threshold
        elif k == "profit_factor":
            actual = ml_result["profit_factor"]
            ok = actual >= threshold
        elif k == "coverage_pct":
            actual = ml_result["coverage"]
            ok = actual >= threshold
        print(f"    {'OK' if ok else 'FAIL':<5} {k}: {actual} (threshold: {threshold})")

    # Feature importance (top 10)
    importances = pd.Series(model.rf.feature_importances_, index=feature_cols)
    top10 = importances.nlargest(10)
    print("\n  Top 10 features:")
    for feat, imp in top10.items():
        print(f"    {feat:<35} {imp:.4f}")

    return {
        "fold": fold["name"],
        "train_rows": len(train_df),
        "test_rows": len(test_df),
        "auc": round(auc, 3),
        "brier": round(brier, 3),
        "unfiltered": unfiltered,
        "ml": ml_result,
        "regime": regime_result,
        "gate_a_pass": gate_pass,
    }


def main():
    print("Loading dataset...")
    df = pd.read_csv(DATA_PATH, parse_dates=False)
    df["entry_date"] = pd.to_datetime(df["entry_date"]).dt.strftime("%Y-%m-%d")
    print(f"Loaded {len(df)} rows, {df['entry_date'].min()} to {df['entry_date'].max()}")

    exclude_cols = verdict_classifier_exclude_columns()
    feature_cols = select_training_feature_columns(df, exclude_cols)
    # Also exclude pe/pb (all null — would be zeroed but still useless)
    feature_cols = [c for c in feature_cols if c not in ("pe", "pb")]
    print(f"Features: {len(feature_cols)} columns")

    results = []
    for fold in FOLDS:
        result = run_fold(fold, df, feature_cols)
        if result:
            results.append(result)

    # Final summary
    print(f"\n{'=' * 60}")
    print("FINAL SUMMARY — DECISION GATE A")
    print(f"{'=' * 60}")
    passes = sum(1 for r in results if r.get("gate_a_pass"))
    print(f"Folds passed Gate A: {passes} / {len(results)}")
    print()
    print(
        f"{'Fold':<10} {'AUC':>6} {'Brier':>7} {'WR Delta':>10} {'PF':>7} {'Coverage':>10} {'Gate A':>8}"
    )
    print("-" * 65)
    for r in results:
        print(
            f"{r['fold']:<10} {r['auc']:>6} {r['brier']:>7} "
            f"{r['ml']['win_rate_delta']:>10} {r['ml']['profit_factor']:>7} "
            f"{r['ml']['coverage']:>10} {'PASS' if r['gate_a_pass'] else 'FAIL':>8}"
        )

    print()
    if passes == len(results):
        print("DECISION: PASS — proceed to Phase 3 (Label Challenge)")
    elif passes >= 2:
        print("DECISION: MARGINAL — 2/3 folds pass; review failing fold before proceeding")
    else:
        print("DECISION: FAIL — ML does not consistently beat unfiltered baseline")


if __name__ == "__main__":
    main()
