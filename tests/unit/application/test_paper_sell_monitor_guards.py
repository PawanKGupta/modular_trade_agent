"""Layer 3 paper sell-monitor guards (backtest parity, stale-bar detection)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.application.services.paper_trading_service_adapter import (
    PaperTradingServiceAdapter,
    _daily_bar_duplicates_prior_session,
    _latest_daily_bar_date_ist,
)
from src.infrastructure.db.timezone_utils import ist_now


@pytest.fixture
def paper_monitor_adapter(db_session):
    adapter = PaperTradingServiceAdapter(
        user_id=1,
        db_session=db_session,
        initial_capital=100000.0,
    )
    adapter.broker = MagicMock()
    adapter.broker.is_connected.return_value = True
    adapter.logger = MagicMock()
    adapter.active_sell_orders = {}
    adapter.converted_to_market = set()
    adapter.running = True
    adapter.shutdown_requested = False
    return adapter


def test_latest_daily_bar_date_ist_from_date_column():
    today = ist_now().date()
    df = pd.DataFrame(
        {
            "date": [pd.Timestamp(today)],
            "high": [106.0],
            "low": [100.0],
            "volume": [1000],
        }
    )
    assert _latest_daily_bar_date_ist(df, df.iloc[-1]) == today


def test_daily_bar_duplicates_prior_session_detects_copy():
    df = pd.DataFrame(
        {
            "date": [pd.Timestamp("2026-05-29"), pd.Timestamp("2026-06-01")],
            "high": [4149.9, 4149.9],
            "low": [4000.1, 4000.1],
            "volume": [2177691, 2177691],
            "close": [4054.5, 4051.0],
        }
    )
    assert _daily_bar_duplicates_prior_session(df) is True


def test_daily_bar_duplicates_prior_session_false_when_high_differs():
    df = pd.DataFrame(
        {
            "high": [100.0, 106.0],
            "low": [95.0, 100.0],
            "volume": [1000, 1100],
        }
    )
    assert _daily_bar_duplicates_prior_session(df) is False


def test_monitor_sell_backtest_parity_high_above_target_still_fills(paper_monitor_adapter):
    """High 106 >= target 105 still fills at limit (LTP 103 does not block daily-high path)."""
    adapter = paper_monitor_adapter
    adapter.active_sell_orders = {
        "RELIANCE": {
            "order_id": "SELL_1",
            "target_price": 105.0,
            "qty": 10,
            "ticker": "RELIANCE.NS",
            "entry_price": 100.0,
        }
    }
    adapter.broker.check_and_execute_pending_orders = MagicMock(
        return_value={"checked": 1, "executed": 0, "still_pending": 1}
    )
    holding = MagicMock()
    holding.quantity = 10
    adapter.broker.get_holding = MagicMock(side_effect=[holding, holding, None])
    adapter.broker.fill_pending_sell_limits_on_daily_high = MagicMock(return_value=True)

    today = ist_now().date()
    mock_data = pd.DataFrame(
        {
            "date": [pd.Timestamp(today - pd.Timedelta(days=1)), pd.Timestamp(today)],
            "high": [100.0, 106.0],
            "low": [98.0, 103.0],
            "volume": [50000, 60000],
            "close": [99.0, 103.0],
        }
    )

    with (
        patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data),
        patch.object(adapter, "_get_current_rsi10_paper", return_value=40.0),
    ):
        adapter._monitor_sell_orders()

    adapter.broker.fill_pending_sell_limits_on_daily_high.assert_called_once_with(
        "RELIANCE", 106.0
    )


def test_monitor_sell_skips_daily_high_when_bar_duplicates_prior(paper_monitor_adapter):
    """Stale today row (same H/L/V as yesterday) must not trigger target exit."""
    adapter = paper_monitor_adapter
    adapter.active_sell_orders = {
        "DMART": {
            "order_id": "SELL_2",
            "target_price": 4105.0,
            "qty": 5,
            "ticker": "DMART.NS",
            "entry_price": 4144.0,
        }
    }
    adapter.broker.check_and_execute_pending_orders = MagicMock(
        return_value={"executed": 0, "still_pending": 1}
    )
    holding = MagicMock()
    holding.quantity = 5
    adapter.broker.get_holding = MagicMock(return_value=holding)
    adapter.broker.fill_pending_sell_limits_on_daily_high = MagicMock(return_value=True)

    today = date(2026, 6, 1)
    mock_data = pd.DataFrame(
        {
            "date": [pd.Timestamp("2026-05-29"), pd.Timestamp(today)],
            "high": [4149.9, 4149.9],
            "low": [4000.1, 4000.1],
            "volume": [2177691, 2177691],
            "close": [4054.5, 4051.0],
        }
    )

    with (
        patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data),
        patch(
            "src.application.services.paper_trading_service_adapter.ist_now",
            return_value=pd.Timestamp("2026-06-01 09:15").to_pydatetime(),
        ),
        patch.object(adapter, "_get_current_rsi10_paper", return_value=40.0),
    ):
        adapter._monitor_sell_orders()

    adapter.broker.fill_pending_sell_limits_on_daily_high.assert_not_called()
    assert "DMART" in adapter.active_sell_orders
