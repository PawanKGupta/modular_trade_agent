"""Tests for _get_current_day_data (layer 1: no info-based synthetic bars)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from core.data_fetcher import _get_current_day_data, live_current_day_scope_allowed


@pytest.fixture
def mock_today():
    with patch("core.data_fetcher.ist_now") as mock_ist:
        mock_ist.return_value.date.return_value = date(2026, 6, 1)
        yield date(2026, 6, 1)


def test_get_current_day_data_uses_history_when_today_present(mock_today):
    hist = pd.DataFrame(
        {
            "Open": [100.0],
            "High": [110.0],
            "Low": [95.0],
            "Close": [105.0],
            "Volume": [50000],
        },
        index=pd.DatetimeIndex([pd.Timestamp("2026-06-01")]),
    )
    mock_stock = MagicMock()
    mock_stock.history.return_value = hist

    with patch("core.data_fetcher.yf.Ticker", return_value=mock_stock):
        result = _get_current_day_data("DMART.NS")

    assert result is not None
    assert result["date"] == mock_today
    assert result["high"] == 110.0
    mock_stock.info.assert_not_called()


def test_get_current_day_data_skips_info_fallback_when_no_today_row(mock_today):
    hist = pd.DataFrame(
        {
            "Open": [4000.0],
            "High": [4149.9],
            "Low": [4000.1],
            "Close": [4054.5],
            "Volume": [2177691],
        },
        index=pd.DatetimeIndex([pd.Timestamp("2026-05-29")]),
    )
    mock_stock = MagicMock()
    mock_stock.history.return_value = hist
    mock_stock.info = {
        "currentPrice": 4051.0,
        "previousClose": 4054.5,
        "volume": 2177691,
        "dayHigh": 4149.9,
        "dayLow": 4000.1,
    }

    with patch("core.data_fetcher.yf.Ticker", return_value=mock_stock):
        result = _get_current_day_data("DMART.NS")

    assert result is None


def test_live_current_day_scope_allowed_for_live_analysis():
    with patch("core.data_fetcher.ist_now") as mock_ist:
        mock_ist.return_value.date.return_value = date(2026, 6, 1)
        assert live_current_day_scope_allowed(
            end_date=None, add_current_day=True, interval="1d"
        )
        assert live_current_day_scope_allowed(
            end_date="2026-06-01", add_current_day=True, interval="1d"
        )


def test_live_current_day_scope_blocked_for_backtest_window():
    with patch("core.data_fetcher.ist_now") as mock_ist:
        mock_ist.return_value.date.return_value = date(2026, 6, 1)
        assert not live_current_day_scope_allowed(
            end_date="2024-01-31", add_current_day=True, interval="1d"
        )
        assert not live_current_day_scope_allowed(
            end_date="2024-01-31", add_current_day=False, interval="1d"
        )
        assert not live_current_day_scope_allowed(
            end_date="2024-01-31", add_current_day=True, interval="1wk"
        )
