"""Unit tests for scalar OHLCV value comparison."""

from __future__ import annotations

import pandas as pd

from tools.compare_yahoo_cache_ohlcv import (
    OHLCV_FIELDS,
    compare_ohlcv_values,
)


def _bars(n: int = 2, open_delta: float = 0.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-06-03", periods=n, freq="B"),
            "open": [100.0 + open_delta, 101.0][:n],
            "high": [101.0, 102.0][:n],
            "low": [99.0, 100.0][:n],
            "close": [100.5, 101.5][:n],
            "volume": [1000, 1100][:n],
        }
    )


def test_all_five_scalars_compared_per_date():
    left = _bars(2)
    right = _bars(2)
    report = compare_ohlcv_values(left, right, left_label="A", right_label="B")
    assert report.value_checks == 2 * len(OHLCV_FIELDS)
    assert report.ok
    assert not report.mismatches


def test_detects_volume_mismatch():
    left = _bars(1)
    right = _bars(1)
    right.loc[0, "volume"] = 9999
    report = compare_ohlcv_values(left, right, left_label="A", right_label="B")
    assert not report.ok
    assert len(report.mismatches) == 1
    assert report.mismatches[0].field == "volume"
    assert report.mismatches[0].left_value == 1000
    assert report.mismatches[0].right_value == 9999


def test_same_bar_count_different_values_not_ok():
    """Matching row count without matching values must fail."""
    left = _bars(2)
    right = _bars(2)
    right.loc[1, "close"] = 999.0
    report = compare_ohlcv_values(left, right, left_label="A", right_label="B")
    assert report.common_dates == 2
    assert report.left_bars == report.right_bars == 2
    assert not report.ok
    assert report.mismatches[0].field == "close"
