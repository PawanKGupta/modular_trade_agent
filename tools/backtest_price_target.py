#!/usr/bin/env python3
# ruff: noqa: T201, PLR2004, PLC0415, E501, E402
"""
Walk-forward backtest of the ML price-target overlay vs the flat EMA9 exit.

For each held-out entry we simulate placing a take-profit at the calibrated ML target:
  - ml_target_pct = capture * max(0, predicted_max_favorable_pct), floored at the EMA9 target
  - if the realized forward max (max_favorable_pct_20d) >= ml_target_pct -> TP fills,
    realized return = ml_target_pct
  - else -> TP never fills, fall back to the normal exit -> realized return = actual_pnl_pct

Baseline strategy = always actual_pnl_pct (the EMA9/RSI50/MaxHold exit the system uses today).

Splits are strictly chronological (train on the past, test on the future) so there is no
look-ahead leakage. Gross returns only (no costs/slippage) — relative comparison is the point.

Usage (repo root, .venv):
  python tools/backtest_price_target.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ml_training_metadata import (
    PRICE_TARGET_FEATURE_COLUMNS,
    PRICE_TARGET_LABEL_COLUMN,
    drop_maxhold_exits,
)

CSV = ROOT / "data" / "training" / "verdict_classifier.csv"
CAPTURE = 0.6  # must match services.ml_price_service._TARGET_CAPTURE_FRACTION
N_FOLDS = 5


def _load() -> pd.DataFrame:
    df = pd.read_csv(CSV)
    df = drop_maxhold_exits(df)
    df = df.dropna(subset=[PRICE_TARGET_LABEL_COLUMN, "actual_pnl_pct", "entry_date"])
    df = df.sort_values("entry_date").reset_index(drop=True)
    # EMA9 target return floor: how far price must rise to reach EMA9 (only when below it).
    df["ema9_target_pct"] = (-df["ema9_distance_pct"]).clip(lower=0.0)
    return df


def _simulate(test: pd.DataFrame, pred_ceiling: np.ndarray, capture: float) -> dict:
    ml_target = np.maximum(capture * np.clip(pred_ceiling, 0, None), test["ema9_target_pct"].values)
    realized_max = test[PRICE_TARGET_LABEL_COLUMN].values
    baseline = test["actual_pnl_pct"].values
    filled = realized_max >= ml_target
    ml_return = np.where(filled, ml_target, baseline)
    return {
        "n": len(test),
        "baseline_mean": float(np.mean(baseline)),
        "ml_mean": float(np.mean(ml_return)),
        "fill_rate": float(np.mean(filled)),
        "ml_mean_on_filled": float(np.mean(ml_return[filled])) if filled.any() else float("nan"),
        "baseline_mean_on_filled": (
            float(np.mean(baseline[filled])) if filled.any() else float("nan")
        ),
    }


def main() -> int:
    if not CSV.is_file():
        print(f"ERROR: dataset not found at {CSV}", file=sys.stderr)
        return 1
    df = _load()
    feats = list(PRICE_TARGET_FEATURE_COLUMNS)
    print(f"Dataset: {len(df)} entries  {df['entry_date'].min()} -> {df['entry_date'].max()}")
    print(f"Capture fraction: {CAPTURE}\n")

    # Expanding-window walk-forward: split the chronological rows into N_FOLDS+1 blocks;
    # for fold k, train on blocks[0..k], test on block[k+1].
    blocks = np.array_split(df.index.values, N_FOLDS + 1)
    agg_base, agg_ml, agg_n = [], [], []
    print(f"{'fold':<5}{'test_n':>8}{'period':>26}{'base%':>9}{'ML%':>9}{'uplift':>9}{'fill%':>8}")
    for k in range(N_FOLDS):
        tr_idx = np.concatenate(blocks[: k + 1])
        te_idx = blocks[k + 1]
        train, test = df.loc[tr_idx], df.loc[te_idx]
        model = RandomForestRegressor(n_estimators=120, max_depth=12, random_state=42, n_jobs=-1)
        model.fit(train[feats].fillna(0).values, train[PRICE_TARGET_LABEL_COLUMN].values)
        pred = model.predict(test[feats].fillna(0).values)
        r = _simulate(test, pred, CAPTURE)
        period = f"{test['entry_date'].min()[:7]}..{test['entry_date'].max()[:7]}"
        print(
            f"{k + 1:<5}{r['n']:>8}{period:>26}{r['baseline_mean']:>9.2f}"
            f"{r['ml_mean']:>9.2f}{r['ml_mean'] - r['baseline_mean']:>+9.2f}{r['fill_rate'] * 100:>8.1f}"
        )
        agg_base.append(r["baseline_mean"] * r["n"])
        agg_ml.append(r["ml_mean"] * r["n"])
        agg_n.append(r["n"])

    tot_n = sum(agg_n)
    base = sum(agg_base) / tot_n
    ml = sum(agg_ml) / tot_n
    print(
        f"\nPooled across folds ({tot_n} held-out trades):"
        f"\n  Baseline (EMA9 exit) mean return: {base:6.2f}% / trade"
        f"\n  ML take-profit overlay   return:  {ml:6.2f}% / trade"
        f"\n  Uplift:                           {ml - base:+6.2f}% / trade  ({(ml / base - 1) * 100:+.1f}% relative)"
    )

    # Capture-fraction sensitivity on the final fold (descriptive; not used to pick CAPTURE).
    print("\nCapture sensitivity (final fold, descriptive only):")
    tr_idx = np.concatenate(blocks[:N_FOLDS])
    te_idx = blocks[N_FOLDS]
    train, test = df.loc[tr_idx], df.loc[te_idx]
    model = RandomForestRegressor(n_estimators=120, max_depth=12, random_state=42, n_jobs=-1)
    model.fit(train[feats].fillna(0).values, train[PRICE_TARGET_LABEL_COLUMN].values)
    pred = model.predict(test[feats].fillna(0).values)
    for cap in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0):
        r = _simulate(test, pred, cap)
        print(
            f"  capture={cap:<4} ML={r['ml_mean']:6.2f}%  base={r['baseline_mean']:6.2f}%  "
            f"uplift={r['ml_mean'] - r['baseline_mean']:+5.2f}%  fill={r['fill_rate'] * 100:4.1f}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
