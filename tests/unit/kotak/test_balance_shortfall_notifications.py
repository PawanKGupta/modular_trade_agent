"""Tests for multi-channel balance shortfall notifications."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from config.strategy_config import StrategyConfig
from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine, Recommendation
from services.notification_preference_service import NotificationEventType
from tests.unit.kotak.conftest import assign_tradable_scrip_master


@pytest.fixture
def mock_auth():
    auth = MagicMock()
    auth.is_authenticated.return_value = True
    auth.login.return_value = True
    return auth


@pytest.fixture
def strategy_config():
    return StrategyConfig(
        rsi_period=14,
        rsi_oversold=25.0,
        user_capital=300000.0,
        max_portfolio_size=6,
    )


@pytest.fixture
def auto_trade_engine(mock_auth, strategy_config):
    with patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth") as mock_auth_class:
        mock_auth_class.return_value = mock_auth
        engine = AutoTradeEngine(
            env_file="test.env",
            auth=mock_auth,
            user_id=1,
            db_session=MagicMock(),
            strategy_config=strategy_config,
        )
        assign_tradable_scrip_master(engine, "RELIANCE")
        engine.portfolio = MagicMock()
        engine.portfolio.get_holdings.return_value = {"data": []}
        engine.orders = MagicMock()
        engine.orders_repo = MagicMock()
        engine.telegram_notifier = MagicMock()
        engine.telegram_notifier.enabled = True
        engine.login = Mock(return_value=True)
        return engine


def _mock_insufficient_balance_path(auto_trade_engine: AutoTradeEngine) -> Recommendation:
    rec = Recommendation(
        ticker="RELIANCE.NS",
        verdict="buy",
        last_close=2450.0,
        execution_capital=30000.0,
    )
    auto_trade_engine.current_symbols_in_portfolio = Mock(return_value=[])
    auto_trade_engine.portfolio_size = Mock(return_value=2)
    auto_trade_engine.has_holding = Mock(return_value=False)
    auto_trade_engine.has_active_buy_order = Mock(return_value=False)
    auto_trade_engine.get_daily_indicators = Mock(
        return_value={
            "close": 2450.0,
            "rsi10": 25.0,
            "ema9": 2400.0,
            "ema200": 2300.0,
            "avg_volume": 1000000,
        }
    )
    auto_trade_engine.get_affordable_qty = Mock(return_value=5)
    auto_trade_engine.get_available_cash = Mock(return_value=10000.0)
    auto_trade_engine.check_position_volume_ratio = Mock(return_value=True)
    auto_trade_engine._calculate_execution_capital = Mock(return_value=30000.0)
    auto_trade_engine.portfolio_service.get_current_positions = Mock(return_value=[])
    auto_trade_engine.portfolio_service.get_portfolio_count = Mock(return_value=2)
    auto_trade_engine.portfolio_service.check_portfolio_capacity = Mock(return_value=(True, 2, 6))
    auto_trade_engine.portfolio_service.has_position = Mock(return_value=False)
    auto_trade_engine.order_validation_service.check_balance = Mock(return_value=(False, 10000.0, 5))
    auto_trade_engine.order_validation_service.check_portfolio_capacity = Mock(
        return_value=(True, 2, 6)
    )
    auto_trade_engine.order_validation_service.check_duplicate_order = Mock(return_value=(False, None))
    auto_trade_engine.order_validation_service.check_volume_ratio = Mock(
        return_value=(True, 0.01, None)
    )
    auto_trade_engine.order_validation_service.get_available_cash = Mock(return_value=10000.0)
    auto_trade_engine.order_validation_service.orders = auto_trade_engine.orders
    auto_trade_engine.order_validation_service.orders_repo = auto_trade_engine.orders_repo
    auto_trade_engine._check_order_margin = Mock(return_value=(False, 10000.0, 29500.0, 19500.0))
    return rec


class TestBalanceShortfallNotifications:
    @patch(
        "modules.kotak_neo_auto_trader.trading_notification_dispatcher.dispatch_trading_notification"
    )
    def test_notify_balance_shortfall_uses_multi_channel_dispatcher(
        self, mock_dispatch, auto_trade_engine
    ):
        auto_trade_engine._notify_balance_shortfall(
                broker_symbol="RELIANCE-EQ",
                qty=12,
                close=2450.0,
                required_cash=29400.0,
                avail_cash=10000.0,
                shortfall=19400.0,
                dry_run=True,
        )

        mock_dispatch.assert_called_once()
        call_kwargs = mock_dispatch.call_args.kwargs
        assert call_kwargs["event_type"] == NotificationEventType.BALANCE_SHORTFALL
        assert call_kwargs["level"] == "warning"
        assert "RELIANCE-EQ" in call_kwargs["message_plain"]
        assert call_kwargs["order_id"] == "balance_shortfall:entry:RELIANCE-EQ"

    @patch(
        "modules.kotak_neo_auto_trader.auto_trade_engine.AutoTradeEngine._notify_balance_shortfall"
    )
    def test_evening_preview_dispatches_balance_shortfall(
        self, mock_notify, auto_trade_engine
    ):
        rec = _mock_insufficient_balance_path(auto_trade_engine)
        summary = auto_trade_engine.place_new_entries([rec], dry_run=True)

        assert summary["failed_balance"] == 1
        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args.kwargs
        assert call_kwargs["dry_run"] is True
        assert call_kwargs["shortfall"] == 19500.0

    def test_preview_evening_buy_margins_includes_reentry(self, auto_trade_engine):
        auto_trade_engine.load_latest_recommendations = Mock(
            return_value=[
                Recommendation(
                    ticker="RELIANCE.NS",
                    verdict="buy",
                    last_close=2450.0,
                    execution_capital=30000.0,
                )
            ]
        )
        entry_summary = {
            "attempted": 1,
            "placed": 0,
            "preview_sufficient": 0,
            "failed_balance": 1,
            "skipped": 0,
            "dry_run": True,
            "ticker_attempts": [],
        }
        reentry_summary = {
            "attempted": 2,
            "placed": 0,
            "preview_sufficient": 1,
            "failed_balance": 1,
            "dry_run": True,
        }
        auto_trade_engine.place_new_entries = Mock(return_value=entry_summary)
        auto_trade_engine.place_reentry_orders = Mock(return_value=reentry_summary)

        merged = auto_trade_engine.preview_evening_buy_margins()

        auto_trade_engine.place_reentry_orders.assert_called_once_with(dry_run=True)
        assert merged["failed_balance"] == 2
        assert merged["preview_sufficient"] == 1
        assert merged["reentry"] == reentry_summary
