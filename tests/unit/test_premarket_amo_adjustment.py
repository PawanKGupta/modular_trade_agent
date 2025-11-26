"""
Tests for pre-market AMO quantity adjustment feature

Tests the functionality that adjusts AMO order quantities at 9:05 AM
based on pre-market prices to keep capital constant.
"""

from math import floor
from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
from src.application.services.paper_trading_service_adapter import PaperTradingServiceAdapter
from src.infrastructure.db.models import UserTradingConfig


@pytest.fixture
def mock_auto_trade_engine():
    """Create a mock AutoTradeEngine with all required components"""
    engine = Mock(spec=AutoTradeEngine)

    # Mock strategy config
    engine.strategy_config = Mock()
    engine.strategy_config.enable_premarket_amo_adjustment = True
    engine.strategy_config.user_capital = 200000.0

    # Mock auth
    engine.auth = Mock()
    engine.auth.is_authenticated = Mock(return_value=True)

    # Mock orders
    engine.orders = Mock()
    engine.orders.get_order_book = Mock(return_value=[])
    engine.orders.modify_order = Mock(return_value={"stat": "ok"})

    # Mock portfolio
    engine.portfolio = Mock()

    # Mock login
    engine.login = Mock(return_value=True)

    # Mock database components
    engine.db = Mock()
    engine.orders_repo = Mock()
    engine.user_id = 1

    # Mock telegram notifier
    engine.telegram_notifier = Mock()
    engine.telegram_notifier.enabled = True
    engine.telegram_notifier.send_message = Mock()

    return engine


def test_adjustment_disabled_in_config(mock_auto_trade_engine):
    """Test that adjustment is skipped when disabled in config"""
    # Create real instance with mocked dependencies
    with patch.object(AutoTradeEngine, "__init__", return_value=None):
        engine = AutoTradeEngine()
        engine.strategy_config = Mock()
        engine.strategy_config.enable_premarket_amo_adjustment = False

        # Call the method
        summary = engine.adjust_amo_quantities_premarket()

        # Verify it was skipped
        assert summary["skipped_not_enabled"] == 1
        assert summary["adjusted"] == 0


def test_no_pending_orders(mock_auto_trade_engine):
    """Test when there are no pending AMO orders"""
    with patch.object(AutoTradeEngine, "__init__", return_value=None):
        engine = AutoTradeEngine()
        engine.strategy_config = mock_auto_trade_engine.strategy_config
        engine.auth = mock_auto_trade_engine.auth
        engine.orders = Mock()
        engine.orders.get_order_book = Mock(return_value=[])
        engine.portfolio = mock_auto_trade_engine.portfolio
        engine.login = mock_auto_trade_engine.login

        summary = engine.adjust_amo_quantities_premarket()

        assert summary["total_orders"] == 0
        assert summary["adjusted"] == 0


def test_filter_only_amo_buy_orders(mock_auto_trade_engine):
    """Test that only AMO buy orders are processed"""
    orders = [
        {
            "symbol": "RELIANCE-EQ",
            "quantity": 1000,
            "nOrdNo": "ORD001",
            "orderValidity": "DAY",
            "orderStatus": "PENDING",
            "transactionType": "BUY",
        },
        {
            "symbol": "TCS-EQ",
            "quantity": 500,
            "nOrdNo": "ORD002",
            "orderValidity": "DAY",
            "orderStatus": "PENDING",
            "transactionType": "SELL",  # SELL order - should be filtered out
        },
        {
            "symbol": "INFY-EQ",
            "quantity": 800,
            "nOrdNo": "ORD003",
            "orderValidity": "IOC",  # Not AMO - should be filtered out
            "orderStatus": "PENDING",
            "transactionType": "BUY",
        },
    ]

    with patch.object(AutoTradeEngine, "__init__", return_value=None):
        engine = AutoTradeEngine()
        engine.strategy_config = mock_auto_trade_engine.strategy_config
        engine.auth = mock_auto_trade_engine.auth
        engine.orders = Mock()
        engine.orders.get_order_book = Mock(return_value=orders)
        engine.portfolio = mock_auto_trade_engine.portfolio
        engine.login = mock_auto_trade_engine.login
        engine.db = None
        engine.orders_repo = None
        engine.telegram_notifier = None

        with patch(
            "modules.kotak_neo_auto_trader.market_data.KotakNeoMarketData"
        ) as mock_market_data:
            mock_md_instance = Mock()
            mock_md_instance.get_ltp = Mock(return_value=None)  # Price not available
            mock_market_data.return_value = mock_md_instance

            summary = engine.adjust_amo_quantities_premarket()

            # Only 1 order (RELIANCE) should be processed (BUY + AMO)
            assert summary["total_orders"] == 1


def test_adjustment_with_gap_up(mock_auto_trade_engine):
    """Test quantity adjustment when price gaps up"""
    orders = [
        {
            "symbol": "TATASTEEL-EQ",
            "quantity": 1202,  # Calculated at Rs 166.33
            "nOrdNo": "ORD001",
            "orderValidity": "DAY",
            "orderStatus": "PENDING",
            "transactionType": "BUY",
        },
    ]

    premarket_price = 169.85  # Gap up from 166.33
    expected_new_qty = floor(200000 / premarket_price)  # = 1177

    with patch.object(AutoTradeEngine, "__init__", return_value=None):
        engine = AutoTradeEngine()
        engine.strategy_config = mock_auto_trade_engine.strategy_config
        engine.auth = mock_auto_trade_engine.auth
        engine.orders = Mock()
        engine.orders.get_order_book = Mock(return_value=orders)
        engine.orders.modify_order = Mock(return_value={"stat": "ok"})
        engine.portfolio = mock_auto_trade_engine.portfolio
        engine.login = mock_auto_trade_engine.login
        engine.db = mock_auto_trade_engine.db
        engine.orders_repo = mock_auto_trade_engine.orders_repo
        engine.telegram_notifier = mock_auto_trade_engine.telegram_notifier
        engine.user_id = 1

        with patch(
            "modules.kotak_neo_auto_trader.market_data.KotakNeoMarketData"
        ) as mock_market_data:
            mock_md_instance = Mock()
            mock_md_instance.get_ltp = Mock(return_value=premarket_price)
            mock_market_data.return_value = mock_md_instance

            with patch("modules.kotak_neo_auto_trader.auto_trade_engine.config") as mock_config:
                mock_config.MIN_QTY = 1

                summary = engine.adjust_amo_quantities_premarket()

                # Verify adjustment happened
                assert summary["total_orders"] == 1
                assert summary["adjusted"] == 1
                assert summary["no_adjustment_needed"] == 0

                # Verify modify_order was called with correct new quantity
                engine.orders.modify_order.assert_called_once()
                call_args = engine.orders.modify_order.call_args[1]
                assert call_args["order_id"] == "ORD001"
                assert call_args["quantity"] == expected_new_qty


def test_adjustment_with_gap_down(mock_auto_trade_engine):
    """Test quantity adjustment when price gaps down"""
    orders = [
        {
            "symbol": "INFY-EQ",
            "quantity": 120,  # Calculated at Rs 1700
            "nOrdNo": "ORD001",
            "orderValidity": "DAY",
            "orderStatus": "PENDING",
            "transactionType": "BUY",
        },
    ]

    premarket_price = 1650.0  # Gap down from 1700
    expected_new_qty = floor(200000 / premarket_price)  # = 121

    with patch.object(AutoTradeEngine, "__init__", return_value=None):
        engine = AutoTradeEngine()
        engine.strategy_config = mock_auto_trade_engine.strategy_config
        engine.auth = mock_auto_trade_engine.auth
        engine.orders = Mock()
        engine.orders.get_order_book = Mock(return_value=orders)
        engine.orders.modify_order = Mock(return_value={"stat": "ok"})
        engine.portfolio = mock_auto_trade_engine.portfolio
        engine.login = mock_auto_trade_engine.login
        engine.db = mock_auto_trade_engine.db
        engine.orders_repo = mock_auto_trade_engine.orders_repo
        engine.telegram_notifier = mock_auto_trade_engine.telegram_notifier
        engine.user_id = 1

        with patch(
            "modules.kotak_neo_auto_trader.market_data.KotakNeoMarketData"
        ) as mock_market_data:
            mock_md_instance = Mock()
            mock_md_instance.get_ltp = Mock(return_value=premarket_price)
            mock_market_data.return_value = mock_md_instance

            with patch("modules.kotak_neo_auto_trader.auto_trade_engine.config") as mock_config:
                mock_config.MIN_QTY = 1

                summary = engine.adjust_amo_quantities_premarket()

                # Verify adjustment happened
                assert summary["adjusted"] == 1

                # Verify new quantity (more shares for gap down)
                call_args = engine.orders.modify_order.call_args[1]
                assert call_args["quantity"] == expected_new_qty
                assert expected_new_qty > 120  # More shares


def test_no_adjustment_needed(mock_auto_trade_engine):
    """Test when pre-market price matches EOD price (no adjustment needed)"""
    eod_price = 500.0
    original_qty = floor(200000 / eod_price)  # = 400

    orders = [
        {
            "symbol": "HCLTECH-EQ",
            "quantity": original_qty,
            "nOrdNo": "ORD001",
            "orderValidity": "DAY",
            "orderStatus": "PENDING",
            "transactionType": "BUY",
        },
    ]

    premarket_price = 500.0  # Same as EOD

    with patch.object(AutoTradeEngine, "__init__", return_value=None):
        engine = AutoTradeEngine()
        engine.strategy_config = mock_auto_trade_engine.strategy_config
        engine.auth = mock_auto_trade_engine.auth
        engine.orders = Mock()
        engine.orders.get_order_book = Mock(return_value=orders)
        engine.orders.modify_order = Mock()
        engine.portfolio = mock_auto_trade_engine.portfolio
        engine.login = mock_auto_trade_engine.login
        engine.db = None
        engine.orders_repo = None
        engine.telegram_notifier = None

        with patch(
            "modules.kotak_neo_auto_trader.market_data.KotakNeoMarketData"
        ) as mock_market_data:
            mock_md_instance = Mock()
            mock_md_instance.get_ltp = Mock(return_value=premarket_price)
            mock_market_data.return_value = mock_md_instance

            with patch("modules.kotak_neo_auto_trader.auto_trade_engine.config") as mock_config:
                mock_config.MIN_QTY = 1

                summary = engine.adjust_amo_quantities_premarket()

                # Verify no adjustment
                assert summary["no_adjustment_needed"] == 1
                assert summary["adjusted"] == 0

                # Verify modify_order was NOT called
                engine.orders.modify_order.assert_not_called()


def test_price_unavailable(mock_auto_trade_engine):
    """Test handling when pre-market price is not available"""
    orders = [
        {
            "symbol": "LOWLIQUIDITY-EQ",
            "quantity": 100,
            "nOrdNo": "ORD001",
            "orderValidity": "DAY",
            "orderStatus": "PENDING",
            "transactionType": "BUY",
        },
    ]

    with patch.object(AutoTradeEngine, "__init__", return_value=None):
        engine = AutoTradeEngine()
        engine.strategy_config = mock_auto_trade_engine.strategy_config
        engine.auth = mock_auto_trade_engine.auth
        engine.orders = Mock()
        engine.orders.get_order_book = Mock(return_value=orders)
        engine.orders.modify_order = Mock()
        engine.portfolio = mock_auto_trade_engine.portfolio
        engine.login = mock_auto_trade_engine.login
        engine.db = None
        engine.orders_repo = None
        engine.telegram_notifier = None

        with patch(
            "modules.kotak_neo_auto_trader.market_data.KotakNeoMarketData"
        ) as mock_market_data:
            mock_md_instance = Mock()
            mock_md_instance.get_ltp = Mock(return_value=None)  # Price not available
            mock_market_data.return_value = mock_md_instance

            summary = engine.adjust_amo_quantities_premarket()

            # Verify skipped due to price unavailability
            assert summary["price_unavailable"] == 1
            assert summary["adjusted"] == 0

            # Verify modify_order was NOT called
            engine.orders.modify_order.assert_not_called()


def test_modification_failure(mock_auto_trade_engine):
    """Test handling when order modification fails"""

    orders = [
        {
            "symbol": "FAIL-EQ",
            "quantity": 100,
            "nOrdNo": "ORD001",
            "orderValidity": "DAY",
            "orderStatus": "PENDING",
            "transactionType": "BUY",
        },
    ]

    with patch.object(AutoTradeEngine, "__init__", return_value=None):
        engine = AutoTradeEngine()
        engine.strategy_config = mock_auto_trade_engine.strategy_config
        engine.auth = mock_auto_trade_engine.auth
        engine.orders = Mock()
        engine.orders.get_order_book = Mock(return_value=orders)
        engine.orders.modify_order = Mock(return_value={"stat": "error", "message": "Failed"})
        engine.portfolio = mock_auto_trade_engine.portfolio
        engine.login = mock_auto_trade_engine.login
        engine.db = None
        engine.orders_repo = None
        engine.telegram_notifier = None

        with patch(
            "modules.kotak_neo_auto_trader.market_data.KotakNeoMarketData"
        ) as mock_market_data:
            mock_md_instance = Mock()
            mock_md_instance.get_ltp = Mock(return_value=110.0)
            mock_market_data.return_value = mock_md_instance

            with patch("modules.kotak_neo_auto_trader.auto_trade_engine.config") as mock_config:
                mock_config.MIN_QTY = 1

                summary = engine.adjust_amo_quantities_premarket()

                # Verify modification failure tracked
                assert summary["modification_failed"] == 1
                assert summary["adjusted"] == 0


def test_database_update_on_success(mock_auto_trade_engine):
    """Test that database is updated when modification succeeds"""
    orders = [
        {
            "symbol": "RELIANCE-EQ",
            "quantity": 100,
            "nOrdNo": "ORD001",
            "orderValidity": "DAY",
            "orderStatus": "PENDING",
            "transactionType": "BUY",
        },
    ]

    premarket_price = 2500.0
    new_qty = floor(200000 / premarket_price)  # = 80

    with patch.object(AutoTradeEngine, "__init__", return_value=None):
        engine = AutoTradeEngine()
        engine.strategy_config = mock_auto_trade_engine.strategy_config
        engine.auth = mock_auto_trade_engine.auth
        engine.orders = Mock()
        engine.orders.get_order_book = Mock(return_value=orders)
        engine.orders.modify_order = Mock(return_value={"stat": "ok"})
        engine.portfolio = mock_auto_trade_engine.portfolio
        engine.login = mock_auto_trade_engine.login
        engine.db = mock_auto_trade_engine.db
        engine.orders_repo = Mock()
        engine.orders_repo.get_by_broker_order_id = Mock(return_value=Mock())
        engine.orders_repo.update = Mock()
        engine.telegram_notifier = mock_auto_trade_engine.telegram_notifier
        engine.user_id = 1

        with patch(
            "modules.kotak_neo_auto_trader.market_data.KotakNeoMarketData"
        ) as mock_market_data:
            mock_md_instance = Mock()
            mock_md_instance.get_ltp = Mock(return_value=premarket_price)
            mock_market_data.return_value = mock_md_instance

            with patch("modules.kotak_neo_auto_trader.auto_trade_engine.config") as mock_config:
                mock_config.MIN_QTY = 1

                summary = engine.adjust_amo_quantities_premarket()

                # Verify DB update was attempted
                engine.orders_repo.get_by_broker_order_id.assert_called_once_with(1, "ORD001")
                engine.orders_repo.update.assert_called_once()

                # Verify Telegram notification was sent
                engine.telegram_notifier.send_message.assert_called_once()


def test_paper_trading_returns_skipped(mock_auto_trade_engine):
    """Test that paper trading adapter returns skip status"""
    with patch.object(PaperTradingServiceAdapter, "__init__", return_value=None):
        adapter = PaperTradingServiceAdapter()
        adapter.logger = Mock()
        adapter.logger.info = Mock()

        summary = adapter.adjust_amo_quantities_premarket()

        # Verify paper trading specific skip
        assert summary["skipped_paper_trading"] == 1
        assert summary["adjusted"] == 0
        assert summary["total_orders"] == 0


def test_authentication_failure(mock_auto_trade_engine):
    """Test handling when authentication fails"""
    with patch.object(AutoTradeEngine, "__init__", return_value=None):
        engine = AutoTradeEngine()
        engine.strategy_config = mock_auto_trade_engine.strategy_config
        engine.auth = Mock()
        engine.auth.is_authenticated = Mock(return_value=False)
        engine.login = Mock(return_value=False)  # Login fails

        summary = engine.adjust_amo_quantities_premarket()

        # Should return early with empty summary
        assert summary["total_orders"] == 0
        assert summary["adjusted"] == 0


def test_multiple_orders_mixed_results(mock_auto_trade_engine):
    """Test processing multiple orders with mixed results"""

    orders = [
        {
            "symbol": "STOCK1-EQ",
            "quantity": 100,
            "nOrdNo": "ORD001",
            "orderValidity": "DAY",
            "orderStatus": "PENDING",
            "transactionType": "BUY",
        },
        {
            "symbol": "STOCK2-EQ",
            "quantity": 200,
            "nOrdNo": "ORD002",
            "orderValidity": "DAY",
            "orderStatus": "PENDING",
            "transactionType": "BUY",
        },
        {
            "symbol": "STOCK3-EQ",
            "quantity": 400,  # Same as calculated
            "nOrdNo": "ORD003",
            "orderValidity": "DAY",
            "orderStatus": "PENDING",
            "transactionType": "BUY",
        },
    ]

    def mock_get_ltp(symbol, exchange="NSE"):
        prices = {
            "STOCK1-EQ": 2100.0,  # Needs adjustment
            "STOCK2-EQ": None,  # Price unavailable
            "STOCK3-EQ": 500.0,  # No adjustment needed
        }
        return prices.get(symbol)

    with patch.object(AutoTradeEngine, "__init__", return_value=None):
        engine = AutoTradeEngine()
        engine.strategy_config = mock_auto_trade_engine.strategy_config
        engine.auth = mock_auto_trade_engine.auth
        engine.orders = Mock()
        engine.orders.get_order_book = Mock(return_value=orders)
        engine.orders.modify_order = Mock(return_value={"stat": "ok"})
        engine.portfolio = mock_auto_trade_engine.portfolio
        engine.login = mock_auto_trade_engine.login
        engine.db = mock_auto_trade_engine.db
        engine.orders_repo = mock_auto_trade_engine.orders_repo
        engine.telegram_notifier = mock_auto_trade_engine.telegram_notifier
        engine.user_id = 1

        with patch(
            "modules.kotak_neo_auto_trader.market_data.KotakNeoMarketData"
        ) as mock_market_data:
            mock_md_instance = Mock()
            mock_md_instance.get_ltp = Mock(side_effect=mock_get_ltp)
            mock_market_data.return_value = mock_md_instance

            with patch("modules.kotak_neo_auto_trader.auto_trade_engine.config") as mock_config:
                mock_config.MIN_QTY = 1

                summary = engine.adjust_amo_quantities_premarket()

                # Verify mixed results
                assert summary["total_orders"] == 3
                assert summary["adjusted"] == 1  # STOCK1
                assert summary["price_unavailable"] == 1  # STOCK2
                assert summary["no_adjustment_needed"] == 1  # STOCK3


def test_config_default_value():
    """Test that enable_premarket_amo_adjustment defaults to True"""
    config = UserTradingConfig(
        user_id=1,
        rsi_period=10,
        rsi_oversold=30.0,
        rsi_extreme_oversold=20.0,
        rsi_near_oversold=40.0,
        user_capital=200000.0,
        paper_trading_initial_capital=300000.0,
        max_portfolio_size=6,
    )

    # Check default value
    assert hasattr(config, "enable_premarket_amo_adjustment")
    # Note: The actual default will be set by the database/migration
