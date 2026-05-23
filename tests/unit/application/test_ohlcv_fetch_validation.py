"""Tests for Yahoo OHLCV ingest validation."""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.application.services.ohlcv_fetch_validation import validate_yahoo_ohlcv_frame


def _daily_frame(n: int = 5) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-06-03", periods=n, freq="B"),
            "open": [10.0] * n,
            "high": [11.0] * n,
            "low": [9.0] * n,
            "close": [10.5] * n,
            "volume": [1000] * n,
        }
    )


def test_validate_ok_for_clean_frame():
    df = _daily_frame(10)
    result = validate_yahoo_ohlcv_frame(
        df,
        symbol="T.NS",
        interval="1d",
        start_date=date(2024, 6, 3),
        end_date=date(2024, 6, 20),
        min_coverage_pct=50.0,
    )
    assert result.status in ("ok", "partial")
    assert result.invalid_ohlc_rows == 0
    assert result.row_count == 10


def test_validate_fails_on_empty():
    result = validate_yahoo_ohlcv_frame(
        None,
        symbol="T.NS",
        interval="1d",
        start_date=date(2024, 6, 3),
        end_date=date(2024, 6, 20),
    )
    assert result.status == "failed"


def test_validate_fails_on_invalid_close():
    df = _daily_frame(3)
    df.loc[1, "close"] = -1.0
    result = validate_yahoo_ohlcv_frame(
        df,
        symbol="T.NS",
        interval="1d",
        start_date=date(2024, 6, 3),
        end_date=date(2024, 6, 20),
    )
    assert result.status == "failed"
    assert result.invalid_ohlc_rows >= 1
