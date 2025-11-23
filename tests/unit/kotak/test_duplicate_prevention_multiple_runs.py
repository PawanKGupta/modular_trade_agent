"""
Tests for duplicate order prevention when buy order service runs multiple times.
This prevents creating duplicate entries in the orders table for the same stock.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine, Recommendation
from src.infrastructure.db.models import OrderStatus as DbOrderStatus


class TestDuplicatePreventionMultipleRuns:
    """Test duplicate prevention when service runs multiple times"""

    @pytest.fixture
    def auto_trade_engine(self):
        """Create AutoTradeEngine instance with mocked dependencies"""
        with patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"):
            engine = AutoTradeEngine(
                enable_verifier=False,
                enable_telegram=False,
                user_id=1,
                db_session=MagicMock(),
            )
            engine.orders_repo = MagicMock()
            engine.orders = MagicMock()
            engine.portfolio = MagicMock()
            engine.strategy_config = MagicMock()
            engine.strategy_config.user_capital = 100000.0
            engine.strategy_config.default_variety = "AMO"
            engine.strategy_config.default_exchange = "NSE"
            engine.strategy_config.default_product = "MIS"
            engine.strategy_config.MIN_QTY = 1
            engine.strategy_config.max_portfolio_size = 10  # Must be int, not MagicMock
            engine.user_id = 1
            engine.db = MagicMock()
            engine.current_symbols_in_portfolio = MagicMock(return_value=[])
            return engine

    def test_place_new_entries_skips_when_order_exists_in_db(self, auto_trade_engine):
        """Test that place_new_entries skips placing order if order already exists in DB"""
        symbol = "RELIANCE"
        broker_symbol = "RELIANCE-EQ"
        ticker = "RELIANCE.NS"

        # Mock existing order in database
        existing_order = MagicMock()
        existing_order.id = 123
        existing_order.symbol = broker_symbol
        existing_order.side = "buy"
        existing_order.status = DbOrderStatus.PENDING
        existing_order.quantity = 20  # Must be int, not MagicMock
        existing_order.price = 2500.0  # Must be float, not MagicMock

        auto_trade_engine.orders_repo.list.return_value = [existing_order]

        # Mock recommendation
        rec = Recommendation(
            ticker=ticker,
            verdict="buy",
            last_close=2500.0,
            execution_capital=50000.0,
        )

        # Mock portfolio checks
        auto_trade_engine.portfolio = MagicMock()
        auto_trade_engine.portfolio.get_holdings = MagicMock(return_value={"data": []})
        auto_trade_engine.has_holding = MagicMock(return_value=False)
        auto_trade_engine._check_for_manual_orders = MagicMock(
            return_value={"has_manual_order": False}
        )

        # Mock indicators - price must match existing order to avoid update
        # Also need to mock the static method for parallel fetching
        mock_indicators = {
            "close": 2500.0,  # Must match existing_order.price
            "rsi10": 25.0,
            "ema9": 2600.0,
            "ema200": 2400.0,
            "avg_volume": 1000000,
        }

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.AutoTradeEngine.get_daily_indicators"
        ) as mock_get_indicators:
            mock_get_indicators.return_value = mock_indicators
            auto_trade_engine.get_daily_indicators = MagicMock(return_value=mock_indicators)

            # Mock execution capital to match existing order quantity
            # If price is 2500 and qty is 20, capital = 2500 * 20 = 50000
            auto_trade_engine._calculate_execution_capital = MagicMock(return_value=50000.0)
            auto_trade_engine.get_affordable_qty = MagicMock(return_value=100)
            auto_trade_engine.get_available_cash = MagicMock(return_value=200000.0)

            # Call place_new_entries
            result = auto_trade_engine.place_new_entries([rec])

            # Verify order was skipped (quantity and price unchanged)
            assert result["skipped_duplicates"] == 1
            assert len(result["ticker_attempts"]) == 1
            assert result["ticker_attempts"][0]["status"] == "skipped"
            assert result["ticker_attempts"][0]["reason"] == "active_order_in_db"
            assert result["ticker_attempts"][0]["existing_order_id"] == 123

            # Verify order was NOT placed
            auto_trade_engine.orders.place_market_buy.assert_not_called()

    def test_place_new_entries_allows_when_no_order_in_db(self, auto_trade_engine):
        """Test that place_new_entries allows placing order if no order exists in DB"""
        symbol = "RELIANCE"
        broker_symbol = "RELIANCE-EQ"
        ticker = "RELIANCE.NS"

        # Mock no existing orders in database
        auto_trade_engine.orders_repo.list.return_value = []

        # Mock recommendation
        rec = Recommendation(
            ticker=ticker,
            verdict="buy",
            last_close=2500.0,
            execution_capital=50000.0,
        )

        # Mock portfolio checks
        auto_trade_engine.portfolio = MagicMock()
        auto_trade_engine.portfolio.get_holdings = MagicMock(return_value={"data": []})
        auto_trade_engine.has_holding = MagicMock(return_value=False)
        auto_trade_engine._check_for_manual_orders = MagicMock(
            return_value={"has_manual_order": False}
        )
        auto_trade_engine.orders.get_pending_orders = MagicMock(return_value=[])

        # Mock indicators - need to patch static method to prevent real API calls
        mock_indicators = {
            "close": 2500.0,
            "rsi10": 25.0,
            "ema9": 2600.0,
            "ema200": 2400.0,
            "avg_volume": 1000000,
        }

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.AutoTradeEngine.get_daily_indicators"
        ) as mock_get_indicators:
            mock_get_indicators.return_value = mock_indicators
            auto_trade_engine.get_daily_indicators = MagicMock(return_value=mock_indicators)

            # Mock order placement
            auto_trade_engine._attempt_place_order = MagicMock(return_value=(True, "ORDER123"))
            auto_trade_engine._calculate_execution_capital = MagicMock(return_value=50000.0)
            auto_trade_engine.get_affordable_qty = MagicMock(return_value=100)
            auto_trade_engine.get_available_cash = MagicMock(return_value=200000.0)

            # Call place_new_entries
            result = auto_trade_engine.place_new_entries([rec])

            # Verify order placement was attempted
            assert result["attempted"] >= 1
            auto_trade_engine._attempt_place_order.assert_called()

    def test_place_new_entries_skips_pending_execution_order(self, auto_trade_engine):
        """Test that place_new_entries skips when PENDING order exists"""
        broker_symbol = "RELIANCE-EQ"
        ticker = "RELIANCE.NS"

        # Mock existing order with PENDING status (AMO/PENDING_EXECUTION merged into PENDING)
        existing_order = MagicMock()
        existing_order.id = 456
        existing_order.symbol = broker_symbol
        existing_order.side = "buy"
        existing_order.status = DbOrderStatus.PENDING
        existing_order.quantity = 20  # Must be int, not MagicMock
        existing_order.price = 2500.0  # Must be float, not MagicMock

        auto_trade_engine.orders_repo.list.return_value = [existing_order]

        # Mock recommendation
        rec = Recommendation(
            ticker=ticker,
            verdict="buy",
            last_close=2500.0,
            execution_capital=50000.0,
        )

        # Mock portfolio checks
        auto_trade_engine.portfolio = MagicMock()
        auto_trade_engine.portfolio.get_holdings = MagicMock(return_value={"data": []})
        auto_trade_engine.has_holding = MagicMock(return_value=False)
        auto_trade_engine._check_for_manual_orders = MagicMock(
            return_value={"has_manual_order": False}
        )

        # Mock indicators - price must match existing order to avoid update
        mock_indicators = {
            "close": 2500.0,  # Must match existing_order.price
            "rsi10": 25.0,
            "ema9": 2600.0,
            "ema200": 2400.0,
            "avg_volume": 1000000,
        }

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.AutoTradeEngine.get_daily_indicators"
        ) as mock_get_indicators:
            mock_get_indicators.return_value = mock_indicators
            auto_trade_engine.get_daily_indicators = MagicMock(return_value=mock_indicators)

            # Mock execution capital to match existing order
            auto_trade_engine._calculate_execution_capital = MagicMock(return_value=50000.0)
            auto_trade_engine.get_affordable_qty = MagicMock(return_value=100)
            auto_trade_engine.get_available_cash = MagicMock(return_value=200000.0)

            # Call place_new_entries
            result = auto_trade_engine.place_new_entries([rec])

            # Verify order was skipped (PENDING_EXECUTION orders are skipped, not updated)
            assert result["skipped_duplicates"] == 1
            assert len(result["ticker_attempts"]) == 1
            assert result["ticker_attempts"][0]["status"] == "skipped"
            assert result["ticker_attempts"][0]["reason"] == "active_order_in_db"
            assert result["ticker_attempts"][0]["existing_order_id"] == 456

            # Verify order was NOT placed
            auto_trade_engine.orders.place_market_buy.assert_not_called()

    def test_has_active_buy_order_checks_database(self, auto_trade_engine):
        """Test that has_active_buy_order checks database for existing orders"""
        symbol = "RELIANCE-EQ"

        # Mock existing order in database
        existing_order = MagicMock()
        existing_order.symbol = symbol
        existing_order.side = "buy"
        existing_order.status = DbOrderStatus.PENDING

        auto_trade_engine.orders_repo.list.return_value = [existing_order]
        auto_trade_engine.orders = None  # Simulate broker API unavailable

        # Check if active buy order exists
        result = auto_trade_engine.has_active_buy_order(symbol)

        # Verify database check was performed
        assert result is True
        auto_trade_engine.orders_repo.list.assert_called_once_with(auto_trade_engine.user_id)

    def test_has_active_buy_order_checks_broker_first(self, auto_trade_engine):
        """Test that has_active_buy_order checks broker API first, then database"""
        symbol = "RELIANCE-EQ"

        # Mock broker API returning pending order
        mock_order = {
            "transactionType": "BUY",
            "tradingSymbol": symbol,
        }
        auto_trade_engine.orders.get_pending_orders = MagicMock(return_value=[mock_order])

        # Check if active buy order exists
        result = auto_trade_engine.has_active_buy_order(symbol)

        # Verify broker API was checked
        assert result is True
        auto_trade_engine.orders.get_pending_orders.assert_called_once()

        # Verify database was NOT checked (broker check returned True first)
        if hasattr(auto_trade_engine, "orders_repo"):
            auto_trade_engine.orders_repo.list.assert_not_called()
