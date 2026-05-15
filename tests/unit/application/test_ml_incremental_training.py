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
