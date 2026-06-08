"""Tests for Yahoo OHLCV ingest validation."""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.application.services.ohlcv_fetch_validation import (
    drop_incomplete_weekly_tail_bar,
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


def _weekly_frame(n: int = 3) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-18", "2026-05-25", "2026-06-08"]),
            "open": [1100.0, 1125.0, 987.9],
            "high": [1150.0, 1149.8, 1006.7],
            "low": [1050.0, 1091.0, 975.6],
            "close": [1120.0, 1100.1, float("nan")],
            "volume": [1000000, 1500000, 185871],
        }
    ).head(n)


def test_drop_incomplete_weekly_tail_bar_removes_nan_close():
    df = _weekly_frame(3)
    trimmed = drop_incomplete_weekly_tail_bar(df)
    assert len(trimmed) == 2
    assert trimmed.iloc[-1]["date"].date() == date(2026, 5, 25)


def test_validate_weekly_ok_when_only_tail_bar_incomplete():
    df = _weekly_frame(3)
    result = validate_yahoo_ohlcv_frame(
        df,
        symbol="GABRIEL.NS",
        interval="1wk",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 6, 8),
        min_coverage_pct=50.0,
    )
    assert result.status in ("ok", "partial")
    assert result.invalid_ohlc_rows == 0
