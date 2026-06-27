"""
Helpers for incremental admin ML training windows (CSV row selection by date).
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd


class IncrementalTrainingDataError(ValueError):
    """Raised when incremental training cannot satisfy date-window constraints."""

    pass


def infer_training_sort_column(frame: pd.DataFrame) -> str:
    """Return the canonical date column used to order training samples."""
    if "entry_date" in frame.columns:
        return "entry_date"
    if "backtest_date" in frame.columns:
        return "backtest_date"
    raise IncrementalTrainingDataError(
        "CSV must contain 'entry_date' or 'backtest_date' for incremental ML training windows."
    )


def coerce_row_dates(series: pd.Series) -> pd.Series:
    """Parse mixed date strings/timestamps to timezone-naive datetimes."""
    parsed = pd.to_datetime(series, errors="coerce", utc=False)
    if getattr(parsed.dt, "tz", None) is not None:
        parsed = parsed.dt.tz_localize(None)
    return parsed


def subset_for_incremental_training(
    frame: pd.DataFrame,
    *,
    train_through: date,
    incremental: bool,
    prior_through_inclusive: date | None,
) -> tuple[pd.DataFrame, dict]:
    """
    Select rows used for sklearn fitting.

    When ``incremental`` is True and ``prior_through_inclusive`` is set (from the active
    model's watermark), this requires both:
      - historical rows dated on or before the watermark, and
      - at least one row strictly after that date (the new regime).

    The resulting frame is capped at ``train_through`` inclusive on the inferred date column.

    Args:
        frame: Raw training dataframe (typically from CSV).
        train_through: Latest calendar date allowed in training (typically today IST).
        incremental: Apply incremental watermark rules vs full file up to train_through.
        prior_through_inclusive: Last inclusive date represented in the previous training job.

    Returns:
        Selected dataframe plus diagnostics for logging/API.

    Raises:
        IncrementalTrainingDataError: If date columns missing or incremental constraints fail.
    """
    if frame.empty:
        raise IncrementalTrainingDataError("Training data CSV is empty")

    column = infer_training_sort_column(frame)
    frame = frame.copy()
    dates = coerce_row_dates(frame[column])
    valid = dates.notna()
    frame = frame.loc[valid].copy()
    dates = dates.loc[valid]

    if frame.empty:
        raise IncrementalTrainingDataError(f"No rows have a valid '{column}' value.")

    cutoff = pd.Timestamp(datetime.combine(train_through, datetime.min.time()))

    inclusive_mask = dates <= cutoff
    working = frame.loc[inclusive_mask].copy()
    row_dates = dates.loc[inclusive_mask]

    if working.empty:
        raise IncrementalTrainingDataError(f"No samples on or before {train_through}.")

    if not incremental or prior_through_inclusive is None:
        max_obs = pd.Timestamp(row_dates.max()).date()
        return working, {
            "mode": "full_window",
            "date_column": column,
            "row_count": len(working),
            "prior_row_count": len(working),
            "incremental_row_count": len(working),
            "min_date": pd.Timestamp(row_dates.min()).date().isoformat(),
            "max_date": max_obs.isoformat(),
            "prior_through_inclusive": None,
            "incremental_requested": incremental,
        }

    # Watermark already at/after the run end date: no calendar window for strictly newer rows.
    if prior_through_inclusive >= train_through:
        max_obs = pd.Timestamp(row_dates.max()).date()
        return working, {
            "mode": "full_window_caught_up",
            "date_column": column,
            "row_count": len(working),
            "prior_row_count": len(working),
            "incremental_row_count": len(working),
            "min_date": pd.Timestamp(row_dates.min()).date().isoformat(),
            "max_date": max_obs.isoformat(),
            "prior_through_inclusive": prior_through_inclusive.isoformat(),
            "incremental_requested": incremental,
            "note": (
                "Active model watermark is on/after train_through; using full CSV window "
                "(uncheck incremental or add rows with dates after the watermark)."
            ),
        }

    prior_anchor = pd.Timestamp(datetime.combine(prior_through_inclusive, datetime.min.time()))
    prior_mask = row_dates <= prior_anchor
    new_mask = row_dates > prior_anchor

    priors = prior_mask.sum()
    news = new_mask.sum()
    if priors == 0:
        raise IncrementalTrainingDataError(
            "Incremental training requires baseline rows dated on/before "
            f"{prior_through_inclusive.isoformat()}, but none were found. "
            "Use a consolidated CSV covering history prior to your last training end date "
            'or omit incremental training ("full refresh").'
        )
    if news == 0:
        # The CSV has no rows newer than the active model's watermark.  Refusing here is
        # deliberate: silently full-retraining would move the watermark backward and could
        # replace a more-current model with one trained on older data.  Make the user choose
        # a full retrain explicitly (uncheck Incremental Training) instead.
        raise IncrementalTrainingDataError(
            f"No new rows since {prior_through_inclusive.isoformat()} "
            f"(CSV ends on/before {pd.Timestamp(row_dates.max()).date().isoformat()}). "
            "The active model was already trained through that date. "
            'Uncheck "Incremental Training" to do a full retrain on this dataset, '
            "or supply a CSV with rows dated after the watermark."
        )

    combo_mask = prior_mask | new_mask
    # Identical to `row_dates <= cutoff` when watermark < cutoff; retained for clarity/tests.
    selected = working.loc[combo_mask].copy()
    sel_dates = row_dates.loc[combo_mask]

    return selected, {
        "mode": "incremental",
        "date_column": column,
        "row_count": len(selected),
        "prior_row_count": int(priors),
        "incremental_row_count": int(news),
        "min_date": pd.Timestamp(sel_dates.min()).date().isoformat(),
        "max_date": pd.Timestamp(sel_dates.max()).date().isoformat(),
        "prior_through_inclusive": prior_through_inclusive.isoformat(),
        "incremental_requested": incremental,
    }
