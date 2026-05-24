#!/usr/bin/env python3
"""
Create a bootstrap verdict-classifier training CSV for admin ML jobs.

Writes ``data/training/verdict_classifier.csv`` with columns compatible with
``MLTrainingService.train_verdict_classifier`` (requires ``label`` and ``entry_date``
for incremental training).

This is for pipeline smoke tests only — replace with real position-level data from
backtest collection (see docs/architecture/ML_COMPLETE_GUIDE.md) before production training.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FEATURES_FILE = ROOT / "models" / "verdict_model_features_enhanced.txt"
DEFAULT_OUT = ROOT / "data" / "training" / "verdict_classifier.csv"

LABELS = ("strong_buy", "buy", "watch", "avoid")


def _feature_names() -> list[str]:
    if FEATURES_FILE.is_file():
        return [ln.strip() for ln in FEATURES_FILE.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [
        "rsi_10",
        "price_above_ema200",
        "volume_ratio",
        "alignment_score",
        "dip_depth_from_20d_high_pct",
    ]


def build_frame(*, n_rows: int = 600, seed: int = 42, end_date: date | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    features = _feature_names()
    end = end_date or date.today()
    start = end - timedelta(days=900)  # ~2.5y history for incremental watermarks
    span_days = max((end - start).days, 1)
    rows: list[dict] = []
    # Reserve trailing rows on recent calendar days so incremental watermarks always have "new" samples.
    tail_days = min(14, span_days + 1)
    n_tail = min(max(n_rows // 10, 40), n_rows // 2)
    n_main = n_rows - n_tail

    for i in range(n_main):
        # Spread dates across [start, end] so incremental jobs always have "new" rows.
        offset = int(rng.integers(0, span_days + 1))
        entry = start + timedelta(days=offset)
        row: dict = {
            "ticker": f"STOCK{i % 50}.NS",
            "entry_date": entry.isoformat(),
            "label": LABELS[int(rng.integers(0, len(LABELS)))],
        }
        for name in features:
            if name in ("price_above_ema200", "vol_strong", "has_hammer", "has_bullish_engulfing", "has_divergence",
                        "fundamental_ok", "decline_rate_slowing", "is_monday", "is_friday", "is_q4",
                        "is_month_end", "is_quarter_end", "extreme_dip_high_volume", "bearish_deep_dip", "is_reentry"):
                row[name] = int(rng.integers(0, 2))
            elif name in ("day_of_week", "month", "quarter", "fill_number", "total_fills_in_position"):
                row[name] = int(rng.integers(0, 8))
            else:
                row[name] = float(rng.uniform(0, 100))
        rows.append(row)

    for j in range(n_tail):
        day_offset = j % tail_days
        entry = end - timedelta(days=day_offset)
        i = n_main + j
        row = {
            "ticker": f"STOCK{i % 50}.NS",
            "entry_date": entry.isoformat(),
            "label": LABELS[int(rng.integers(0, len(LABELS)))],
        }
        for name in features:
            if name in ("price_above_ema200", "vol_strong", "has_hammer", "has_bullish_engulfing", "has_divergence",
                        "fundamental_ok", "decline_rate_slowing", "is_monday", "is_friday", "is_q4",
                        "is_month_end", "is_quarter_end", "extreme_dip_high_volume", "bearish_deep_dip", "is_reentry"):
                row[name] = int(rng.integers(0, 2))
            elif name in ("day_of_week", "month", "quarter", "fill_number", "total_fills_in_position"):
                row[name] = int(rng.integers(0, 8))
            else:
                row[name] = float(rng.uniform(0, 100))
        rows.append(row)

    return pd.DataFrame(rows)


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    frame = build_frame()
    frame.to_csv(out, index=False)
    max_d = frame["entry_date"].max()
    min_d = frame["entry_date"].min()
    print(f"Wrote {len(frame)} rows -> {out} (entry_date {min_d} .. {max_d})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
