"""Tests for Yahoo OHLCV ingest validation."""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.application.services.ohlcv_fetch_validation import (
    meets_indicator_history_requirement,
    validate_yahoo_ohlcv_frame,
)


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


def test_meets_indicator_history_by_bar_count():
    ok, _ = meets_indicator_history_requirement(
        interval="1d",
        bars_in_window=300,
        effective_start=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        min_daily_bars=250,
        min_listing_years=5.0,
    )
    assert ok


def test_meets_indicator_history_fails_short_window():
    ok, msg = meets_indicator_history_requirement(
        interval="1d",
        bars_in_window=50,
        effective_start=date(2024, 6, 1),
        end_date=date(2024, 8, 1),
        min_daily_bars=250,
        min_listing_years=2.0,
    )
    assert not ok
    assert "bars" in msg


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
