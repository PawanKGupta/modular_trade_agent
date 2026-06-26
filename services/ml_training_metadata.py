"""
Columns from bulk analysis exports and ops metadata that must never be ML features.

``trade_agent`` may add CSV columns (e.g. ``backtest_mode``) for operators; training
pipelines must exclude them even when a bulk export is used as a training CSV.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from utils.logger import logger

# trade_agent screener exports (not position-level ML datasets).
_BULK_ANALYSIS_FILENAME_RE = re.compile(
    r"bulk_analysis(?:_final)?[_\.]",
    re.IGNORECASE,
)

# Phase 0 bulk export + backtest scoring (string / dict repr / verdict fields).
BULK_ANALYSIS_CSV_METADATA: frozenset[str] = frozenset(
    {
        "backtest_mode",
        "status",
        "verdict",
        "final_verdict",
        "combined_score",
        "strength_score",
        "backtest_score",
        "timeframe_analysis",
        "backtest",
        "buy_range",
        "justification",
        "chart_quality",
        "volume_analysis",
        "volume_pattern",
        "volume_description",
        "candle_analysis",
        "news_sentiment",
        "fundamental_assessment",
        "fundamental_growth_stock",
        "fundamental_avoid",
        "fundamental_reason",
        "signals",
        "cache_health_status",
        "yahoo_calls",
        "_yahoo_calls_analysis",
        "analysis_duration_sec",
        "cache_hit_pct",
        "ml_verdict",
        "ml_confidence",
        "ml_probabilities",
        "capital_adjusted",
    }
)

# Price-regressor target: best achievable upside within a forward window after entry
# (emitted by scripts/build_historical_dataset.py). Predicting this lets the model set
# targets BEYOND the EMA9 exit, unlike actual_pnl_pct which encodes the EMA9 return.
PRICE_TARGET_LABEL_COLUMN = "max_favorable_pct_20d"

# Shared across verdict classifier and price regressor (position-level backtest rows).
VERDICT_AND_REGRESSOR_METADATA: tuple[str, ...] = (
    "ticker",
    "entry_date",
    "exit_date",
    "label",
    "actual_pnl_pct",
    PRICE_TARGET_LABEL_COLUMN,
    "holding_days",
    "backtest_date",
    "position_id",
    "sample_weight",
    "fill_quantity",
    "initial_entry_date",
    "initial_entry_price",
    "fill_price",
    "exit_reason",
    "max_drawdown_pct",
)

DIP_EPISODE_METADATA: tuple[str, ...] = (
    "ticker",
    "entry_date",
    "exit_date",
    "n_adds",
    "pnl_pct",
    "net_win",
    "strong_win",
)

# Curated price-regressor feature contract. Order IS the contract — emitted to the
# `.price_features.json` manifest at train time and consumed by MLPriceService at serve
# time. Every column here is computed live by ``MLPriceService._extract_target_features``.
PRICE_TARGET_FEATURE_COLUMNS: tuple[str, ...] = (
    "rsi_10",
    "ema9_distance_pct",
    "volume_ratio",
    "support_distance_pct",
    "dip_depth_from_20d_high_pct",
    "consecutive_red_days",
    "volume_green_vs_red_ratio",
    "day_of_week",
    "rsi_volume_interaction",
    "dip_support_interaction",
    # Magnitude features (volatility / momentum / room-to-run) — drive HOW FAR price runs.
    "atr_pct_14",
    "hist_vol_20d",
    "ret_60d",
    "ret_120d",
    "dist_from_high_252d_pct",
)

# Backtest exits that hit the 30-day holding ceiling rather than a real signal exit;
# their pnl is not a predictable price target, so they are dropped before fitting.
_MAXHOLD_EXIT_REASON = "MaxHold"


def price_regressor_feature_columns(df: pd.DataFrame) -> list[str]:
    """
    Resolve the curated price-regressor feature columns present in ``df``.

    Preserves the canonical order of :data:`PRICE_TARGET_FEATURE_COLUMNS`.

    Raises:
        ValueError: If none of the curated columns are present.
    """
    cols = [c for c in PRICE_TARGET_FEATURE_COLUMNS if c in df.columns]
    if not cols:
        raise ValueError(
            "None of the curated price feature columns are present in the training data: "
            f"{list(PRICE_TARGET_FEATURE_COLUMNS)}. Regenerate with build_historical_dataset.py."
        )
    return cols


def drop_maxhold_exits(df: pd.DataFrame) -> pd.DataFrame:
    """Return ``df`` without MaxHold-ceiling exits (no-op if ``exit_reason`` absent)."""
    if "exit_reason" not in df.columns:
        return df
    return df[df["exit_reason"] != _MAXHOLD_EXIT_REASON]


def _union_exclude(*parts: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for part in parts:
        for name in part:
            if name not in seen:
                seen.add(name)
                out.append(name)
    return out


def verdict_classifier_exclude_columns() -> list[str]:
    """Metadata excluded before fitting verdict classifiers."""
    return _union_exclude(VERDICT_AND_REGRESSOR_METADATA, BULK_ANALYSIS_CSV_METADATA)


def dip_classifier_exclude_columns() -> list[str]:
    """Metadata excluded before fitting dip-success classifiers."""
    return _union_exclude(DIP_EPISODE_METADATA, BULK_ANALYSIS_CSV_METADATA)


def is_bulk_analysis_export_path(csv_path: Path | str) -> bool:
    """
    True when the path looks like a ``trade_agent`` bulk screener CSV, not ML training data.

    Matches names such as ``bulk_analysis_final_20260522_013532.csv`` or
    ``bulk_analysis_20260522.csv`` under ``analysis_results/``.
    """
    name = Path(csv_path).name
    if _BULK_ANALYSIS_FILENAME_RE.search(name):
        return True
    return "bulk_analysis_final" in name.lower()


def bulk_analysis_training_path_error(csv_path: Path | str) -> str | None:
    """
    Return a user-facing error if ``csv_path`` must not be used for admin ML training.

    Skipped when ``ML_ALLOW_BULK_ANALYSIS_TRAINING_CSV`` is truthy (experiments only).

    Checks filename patterns and, when the file exists, header columns typical of
    bulk exports (``final_verdict`` without position-level ``label``).
    """
    if os.getenv("ML_ALLOW_BULK_ANALYSIS_TRAINING_CSV", "").lower() in ("1", "true", "yes"):
        return None

    path = Path(csv_path)
    if is_bulk_analysis_export_path(path):
        return (
            f"'{path.name}' looks like a trade_agent bulk screener export "
            "(bulk_analysis_final_*.csv), not an ML training dataset. "
            "Use position-level data (e.g. data/ml_training_data.csv from backtest "
            "collection). See docs/guides/BULK_ANALYSIS_RELIABILITY.md."
        )

    if not path.is_file():
        return None

    try:
        columns = {c.strip() for c in pd.read_csv(path, nrows=0).columns}
    except (OSError, ValueError) as e:
        logger.debug("Could not read CSV header for bulk guard: %s", e)
        return None

    has_screener_verdict = "final_verdict" in columns or (
        "verdict" in columns and "combined_score" in columns
    )
    has_training_label = "label" in columns or "net_win" in columns
    has_bulk_ops = "backtest_mode" in columns or "backtest" in columns

    if has_screener_verdict and not has_training_label and has_bulk_ops:
        return (
            f"'{path.name}' has bulk-analysis columns (e.g. final_verdict, backtest_mode) "
            "but no training label column (label / net_win). "
            "Use a dedicated ML training CSV, not analysis_results/bulk_analysis_final_*.csv."
        )
    return None


def validate_training_csv_for_model_type(
    frame: pd.DataFrame,
    model_type: str,
    *,
    target_column: str = PRICE_TARGET_LABEL_COLUMN,
) -> None:
    """
    Ensure a training CSV has columns required for the selected admin model type.

    Raises:
        ValueError: When required label/target columns are missing.
    """
    columns = set(frame.columns)
    if model_type == "verdict_classifier":
        if "label" not in columns:
            raise ValueError(
                "Verdict classifier training requires a 'label' column "
                f"(e.g. strong_buy, buy, watch, avoid). Columns present: {sorted(columns)[:12]}"
            )
        return
    if model_type == "price_regressor":
        if target_column not in columns:
            raise ValueError(
                f"Price regressor training requires target column '{target_column}'. "
                "Use the historical-dataset CSV from build_historical_dataset.py "
                "(e.g. data/training/verdict_classifier.csv). "
                f"Columns present: {sorted(columns)[:12]}"
            )
        if "entry_date" not in columns and "backtest_date" not in columns:
            raise ValueError(
                "Price regressor training requires 'entry_date' or 'backtest_date' for "
                "incremental windows and watermarks."
            )
        return
    raise ValueError(f"Unsupported model_type for training CSV validation: {model_type}")


def select_training_feature_columns(
    df: pd.DataFrame,
    exclude_cols: Iterable[str],
) -> list[str]:
    """
    Resolve feature column names: explicit excludes, bulk metadata, non-numeric only.

    Args:
        df: Training frame.
        exclude_cols: Label columns and run-specific fields to drop.

    Returns:
        Ordered list of numeric feature names safe for sklearn ``fit``.

    Raises:
        ValueError: If no numeric feature columns remain.
    """
    exclude = set(exclude_cols) | BULK_ANALYSIS_CSV_METADATA
    feature_cols: list[str] = []
    for col in df.columns:
        if col in exclude:
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            logger.debug("Skipping non-numeric training column: %s", col)
            continue
        feature_cols.append(col)
    if not feature_cols:
        raise ValueError("No numeric feature columns found for training")
    return feature_cols
