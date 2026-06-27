from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.application.services.ml_incremental_training import (
    IncrementalTrainingDataError,
    subset_for_incremental_training,
)


def _fixture_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "train.csv"
    rows = []
    for idx in range(15):
        day = date(2026, 1, idx + 1)
        rows.append(
            {
                "entry_date": day.isoformat(),
                "rsi": float(idx),
                "label": "buy" if idx % 2 else "watch",
            }
        )
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    return csv_path


def test_incremental_requires_history_and_delta(tmp_path: Path):
    csv_path = _fixture_csv(tmp_path)
    df = pd.read_csv(csv_path)

    subset_full, diag = subset_for_incremental_training(
        df,
        train_through=date(2026, 1, 15),
        incremental=False,
        prior_through_inclusive=None,
    )
    assert diag["mode"] == "full_window"
    assert len(subset_full) == len(df)

    incremental_frame, incr_diag = subset_for_incremental_training(
        df,
        train_through=date(2026, 1, 15),
        incremental=True,
        prior_through_inclusive=date(2026, 1, 10),
    )
    assert incr_diag["prior_row_count"] == 10
    assert incr_diag["incremental_row_count"] == 5
    assert len(incremental_frame) == len(df)


def test_incremental_same_day_watermark_uses_full_window(tmp_path: Path):
    """When watermark >= train_through, retrain on full CSV instead of failing."""
    df = pd.read_csv(_fixture_csv(tmp_path))
    subset, diag = subset_for_incremental_training(
        df,
        train_through=date(2026, 1, 15),
        incremental=True,
        prior_through_inclusive=date(2026, 1, 15),
    )
    assert diag["mode"] == "full_window_caught_up"
    assert len(subset) == len(df)


def test_watermark_ahead_of_csv_refuses_with_guidance(tmp_path: Path):
    """When the CSV has no rows newer than the watermark, refuse with actionable guidance.

    Root cause scenario: a prior training job used a different CSV (e.g. the legacy
    paper-trading export with dates up to today), setting the watermark to a recent date.
    The next job submits a historical CSV (dates only up to ~2025) with incremental=True.
    The system must refuse rather than silently moving the watermark backward — the error
    must tell the user to uncheck Incremental Training to do a full retrain.
    """
    df = pd.read_csv(_fixture_csv(tmp_path))
    # CSV goes up to 2026-01-15; watermark is 2026-06-25 (far ahead of CSV data)
    future_watermark = date(2026, 6, 25)
    with pytest.raises(IncrementalTrainingDataError, match="Uncheck"):
        subset_for_incremental_training(
            df,
            train_through=date(2026, 6, 26),
            incremental=True,
            prior_through_inclusive=future_watermark,
        )


def test_incremental_errors_when_prior_missing(tmp_path: Path):
    df = pd.read_csv(_fixture_csv(tmp_path))
    df_recent = df[df["entry_date"] >= "2026-01-11"].reset_index(drop=True)

    with pytest.raises(IncrementalTrainingDataError):
        subset_for_incremental_training(
            df_recent,
            train_through=date(2026, 1, 15),
            incremental=True,
            prior_through_inclusive=date(2026, 1, 10),
        )
