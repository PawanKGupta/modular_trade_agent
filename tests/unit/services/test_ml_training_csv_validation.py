"""Training CSV column guards for admin ML jobs."""

from __future__ import annotations

import pandas as pd
import pytest

from services.ml_training_metadata import validate_training_csv_for_model_type


def test_price_regressor_rejects_verdict_csv_columns():
    frame = pd.DataFrame(
        {
            "entry_date": ["2026-05-01"],
            "label": ["buy"],
            "rsi": [25.0],
        }
    )
    with pytest.raises(ValueError, match="actual_pnl_pct"):
        validate_training_csv_for_model_type(frame, "price_regressor")


def test_price_regressor_accepts_price_csv_shape():
    frame = pd.DataFrame(
        {
            "entry_date": ["2026-05-01"],
            "actual_pnl_pct": [5.0],
            "current_price": [100.0],
            "rsi_10": [30.0],
        }
    )
    validate_training_csv_for_model_type(frame, "price_regressor")
