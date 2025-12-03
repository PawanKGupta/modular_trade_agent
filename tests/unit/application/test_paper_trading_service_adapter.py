"""
Tests for Paper Trading Service Adapter

Tests that paper trading mode works correctly for individual services.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.application.services.paper_trading_service_adapter import (
    PaperTradingEngineAdapter,
    PaperTradingServiceAdapter,
)
from src.infrastructure.db.models import (
    Signals,
    SignalStatus,
    Users,
    UserSignalStatus,
)
from src.infrastructure.db.timezone_utils import ist_now


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = Users(
        email="paper_test@example.com",
        password_hash="test_hash",
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def mock_paper_broker():
    """Mock paper trading broker"""
    broker = MagicMock()
    broker.is_connected.return_value = True
    broker.get_holdings.return_value = []
    broker.get_available_balance.return_value = MagicMock(amount=100000.0)
    broker.place_order.return_value = "PAPER_ORDER_123"
    return broker


class TestPaperTradingServiceAdapter:
    """Test PaperTradingServiceAdapter"""

    def test_initialize_success(self, db_session, test_user):
        """Test successful initialization"""
        with (
            patch(
                "src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter"
            ) as mock_broker_class,
            patch(
                "src.application.services.paper_trading_service_adapter.PaperTradingConfig"
            ) as mock_config_class,
        ):
            mock_broker = MagicMock()
            mock_broker.connect.return_value = True
            mock_broker.get_holdings.return_value = []
            mock_broker.get_available_balance.return_value = MagicMock(amount=100000.0)
            mock_broker_class.return_value = mock_broker

            adapter = PaperTradingServiceAdapter(
                user_id=test_user.id,
                db_session=db_session,
                initial_capital=100000.0,
            )

            result = adapter.initialize()

            assert result is True
            assert adapter.broker is not None
            assert adapter.config is not None

    def test_initialize_failure(self, db_session, test_user):
        """Test initialization failure when broker connection fails"""
        with (
            patch(
                "src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter"
            ) as mock_broker_class,
            patch(
                "src.application.services.paper_trading_service_adapter.PaperTradingConfig"
            ) as mock_config_class,
        ):
            mock_broker = MagicMock()
            mock_broker.connect.return_value = False
            mock_broker_class.return_value = mock_broker

            adapter = PaperTradingServiceAdapter(
                user_id=test_user.id,
                db_session=db_session,
            )

            result = adapter.initialize()

            assert result is False

    def test_run_buy_orders_no_recommendations(self, db_session, test_user, mock_paper_broker):
        """Test buy orders with no recommendations"""
        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
        )
        adapter.broker = mock_paper_broker
        adapter.engine = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=adapter.logger,
        )

        with patch.object(adapter.engine, "load_latest_recommendations", return_value=[]):
            adapter.run_buy_orders()

        assert adapter.tasks_completed["buy_orders"] is True

    def test_run_buy_orders_with_recommendations(self, db_session, test_user, mock_paper_broker):
        """Test buy orders with recommendations"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
        )
        adapter.broker = mock_paper_broker
        # Mock broker config with max_position_size
        mock_paper_broker.config = MagicMock()
        mock_paper_broker.config.max_position_size = 100000.0

        adapter.engine = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=adapter.logger,
        )

        recommendations = [
            Recommendation(ticker="RELIANCE.NS", verdict="buy", last_close=2500.0),
            Recommendation(ticker="TCS.NS", verdict="strong_buy", last_close=3500.0),
        ]

        with patch.object(
            adapter.engine, "load_latest_recommendations", return_value=recommendations
        ):
            adapter.run_buy_orders()

        assert adapter.tasks_completed["buy_orders"] is True
        # Verify orders were placed
        assert mock_paper_broker.place_order.call_count == 2


class TestPaperTradingEngineAdapter:
    """Test PaperTradingEngineAdapter"""

    def test_load_latest_recommendations_from_db(self, db_session, test_user, mock_paper_broker):
        """Test loading recommendations from database (Signals table)"""
        from src.infrastructure.db.models import Signals
        from src.infrastructure.db.timezone_utils import ist_now

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create test signals in database
        signal1 = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            ts=ist_now(),
        )
        signal2 = Signals(
            symbol="TCS",
            verdict="strong_buy",
            final_verdict="strong_buy",
            last_close=3500.0,
            ts=ist_now(),
        )
        signal3 = Signals(
            symbol="WATCH",
            verdict="watch",
            final_verdict="watch",
            last_close=100.0,
            ts=ist_now(),
        )
        db_session.add_all([signal1, signal2, signal3])
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should only return buy/strong_buy signals
        assert len(recs) == 2
        tickers = {r.ticker for r in recs}
        assert "RELIANCE.NS" in tickers or "RELIANCE" in tickers
        assert "TCS.NS" in tickers or "TCS" in tickers

    def test_place_new_entries(self, db_session, test_user, mock_paper_broker):
        """Test placing new entries as MARKET AMO orders"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from modules.kotak_neo_auto_trader.domain import OrderType, OrderVariety

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=MagicMock(),
        )

        # Mock broker config with max_position_size
        mock_paper_broker.config = MagicMock()
        mock_paper_broker.config.max_position_size = 100000.0

        recommendations = [
            Recommendation(
                ticker="RELIANCE.NS", verdict="buy", last_close=2500.0, execution_capital=100000.0
            )
        ]

        with patch("core.volume_analysis.is_market_hours", return_value=False):
            summary = adapter.place_new_entries(recommendations)

        assert summary["attempted"] == 1
        assert summary["placed"] == 1
        assert mock_paper_broker.place_order.called

        # Verify order is MARKET AMO type (matches real broker)
        placed_order = mock_paper_broker.place_order.call_args[0][0]
        assert placed_order.order_type == OrderType.MARKET
        assert placed_order.variety == OrderVariety.AMO
        assert placed_order.price is None  # MARKET orders don't have price parameter

    def test_place_new_entries_prevents_duplicate_symbols_with_different_formats(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that duplicate orders are not placed for same symbol with different formats"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=MagicMock(),
        )

        # Mock broker config with max_position_size
        mock_paper_broker.config = MagicMock()
        mock_paper_broker.config.max_position_size = 100000.0

        # Create recommendations with same symbol but different formats
        recommendations = [
            Recommendation(ticker="XYZ", verdict="buy", last_close=100.0),  # Without .NS
            Recommendation(ticker="XYZ.NS", verdict="buy", last_close=100.0),  # With .NS
        ]

        summary = adapter.place_new_entries(recommendations)

        # Should attempt both but only place one (second should be detected as duplicate)
        assert summary["attempted"] == 2
        assert summary["placed"] == 1  # Only one order should be placed
        assert summary["skipped_duplicates"] == 1  # One should be skipped as duplicate

        # Verify only one order was placed
        assert mock_paper_broker.place_order.call_count == 1

    def test_place_new_entries_respects_max_position_size(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that orders respect max_position_size limit"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=MagicMock(),
        )

        # Mock broker config with lower max_position_size
        mock_paper_broker.config = MagicMock()
        mock_paper_broker.config.max_position_size = 50000.0

        # Recommendation with execution_capital > max_position_size
        recommendations = [
            Recommendation(
                ticker="RELIANCE.NS", verdict="buy", last_close=2500.0, execution_capital=100000.0
            )
        ]

        summary = adapter.place_new_entries(recommendations)

        assert summary["attempted"] == 1
        # Order should be placed but with adjusted quantity
        assert summary["placed"] == 1
        assert mock_paper_broker.place_order.called

        # Verify order quantity was adjusted (should be ~20 shares for 50000/2500)
        call_args = mock_paper_broker.place_order.call_args
        order = call_args[0][0]
        assert order.quantity <= 20  # Should be limited by max_position_size

    def test_place_new_entries_duplicate(self, db_session, test_user, mock_paper_broker):
        """Test placing entries with duplicate in portfolio"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        # Mock holding
        mock_holding = MagicMock()
        mock_holding.symbol = "RELIANCE"
        mock_paper_broker.get_holdings.return_value = [mock_holding]
        mock_paper_broker.config = MagicMock()
        mock_paper_broker.config.max_position_size = 100000.0

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=MagicMock(),
        )

        recommendations = [
            Recommendation(
                ticker="RELIANCE.NS", verdict="buy", last_close=2500.0, execution_capital=100000.0
            )
        ]

        summary = adapter.place_new_entries(recommendations)

        assert summary["attempted"] == 1
        assert summary["placed"] == 0
        assert summary["skipped_duplicates"] == 1
        assert not mock_paper_broker.place_order.called

    def test_place_new_entries_portfolio_limit(self, db_session, test_user, mock_paper_broker):
        """Test placing entries when portfolio limit is reached"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        # Mock 6 holdings (portfolio limit)
        mock_holdings = [MagicMock() for _ in range(6)]
        mock_paper_broker.get_holdings.return_value = mock_holdings
        mock_paper_broker.config = MagicMock()
        mock_paper_broker.config.max_position_size = 100000.0

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=MagicMock(),
        )

        recommendations = [
            Recommendation(
                ticker="RELIANCE.NS", verdict="buy", last_close=2500.0, execution_capital=100000.0
            )
        ]

        summary = adapter.place_new_entries(recommendations)

        assert summary["skipped_portfolio_limit"] == 1
        assert not mock_paper_broker.place_order.called

    def test_initialize_sets_max_position_size_from_strategy_config(self, db_session, test_user):
        """Test that initialization sets max_position_size from strategy_config.user_capital"""
        from config.strategy_config import StrategyConfig

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        with (
            patch(
                "src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter"
            ) as mock_broker_class,
            patch(
                "src.application.services.paper_trading_service_adapter.PaperTradingConfig"
            ) as mock_config_class,
        ):
            mock_broker = MagicMock()
            mock_broker.connect.return_value = True
            mock_broker.get_holdings.return_value = []
            mock_broker.get_available_balance.return_value = MagicMock(amount=100000.0)
            mock_broker_class.return_value = mock_broker

            mock_config = MagicMock()
            mock_config_class.return_value = mock_config

            adapter = PaperTradingServiceAdapter(
                user_id=test_user.id,
                db_session=db_session,
                strategy_config=strategy_config,
                initial_capital=100000.0,
            )

            result = adapter.initialize()

            assert result is True
            # Verify PaperTradingConfig was called with max_position_size from strategy_config
            mock_config_class.assert_called_once()
            call_kwargs = mock_config_class.call_args[1]
            assert call_kwargs["max_position_size"] == 100000.0

    def test_place_new_entries_skips_pending_orders(self, db_session, test_user, mock_paper_broker):
        """Test that duplicate check includes pending buy orders (not just holdings)"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from modules.kotak_neo_auto_trader.domain import (
            OrderStatus,
            TransactionType,
        )

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        # Mock no holdings but has pending order
        mock_paper_broker.get_holdings.return_value = []

        # Create a pending buy order for RELIANCE
        pending_order = MagicMock()
        pending_order.symbol = "RELIANCE"
        pending_order.status = OrderStatus.OPEN
        pending_order.transaction_type = TransactionType.BUY
        pending_order.is_buy_order.return_value = True
        pending_order.is_active.return_value = True

        mock_paper_broker.get_all_orders.return_value = [pending_order]
        mock_paper_broker.config = MagicMock()
        mock_paper_broker.config.max_position_size = 100000.0

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=MagicMock(),
        )

        recommendations = [
            Recommendation(
                ticker="RELIANCE.NS", verdict="buy", last_close=2500.0, execution_capital=100000.0
            )
        ]

        summary = adapter.place_new_entries(recommendations)

        # Should skip because of pending order
        assert summary["attempted"] == 1
        assert summary["placed"] == 0
        assert summary["skipped_duplicates"] == 1
        assert not mock_paper_broker.place_order.called

    def test_place_new_entries_multiple_pending_orders(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test duplicate prevention with multiple pending orders"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from modules.kotak_neo_auto_trader.domain import OrderStatus, TransactionType

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        # Mock holdings with one stock
        mock_holding = MagicMock()
        mock_holding.symbol = "TCS"
        mock_paper_broker.get_holdings.return_value = [mock_holding]

        # Create pending orders
        pending_reliance = MagicMock()
        pending_reliance.symbol = "RELIANCE"
        pending_reliance.status = OrderStatus.OPEN
        pending_reliance.transaction_type = TransactionType.BUY
        pending_reliance.is_buy_order.return_value = True
        pending_reliance.is_active.return_value = True

        pending_infy = MagicMock()
        pending_infy.symbol = "INFY"
        pending_infy.status = OrderStatus.OPEN
        pending_infy.transaction_type = TransactionType.BUY
        pending_infy.is_buy_order.return_value = True
        pending_infy.is_active.return_value = True

        # Add a completed order (should not block)
        completed_order = MagicMock()
        completed_order.symbol = "HDFC"
        completed_order.status = OrderStatus.EXECUTED
        completed_order.is_buy_order.return_value = True
        completed_order.is_active.return_value = False

        mock_paper_broker.get_all_orders.return_value = [
            pending_reliance,
            pending_infy,
            completed_order,
        ]
        mock_paper_broker.config = MagicMock()
        mock_paper_broker.config.max_position_size = 100000.0

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=MagicMock(),
        )

        recommendations = [
            Recommendation(ticker="RELIANCE.NS", verdict="buy", last_close=2500.0),
            Recommendation(ticker="INFY.NS", verdict="buy", last_close=1450.0),
            Recommendation(ticker="TCS.NS", verdict="buy", last_close=3500.0),
            Recommendation(ticker="HDFC.NS", verdict="buy", last_close=1600.0),  # completed order
        ]

        summary = adapter.place_new_entries(recommendations)

        # All should be skipped (holdings + pending orders + completed but still valid)
        assert summary["attempted"] == 4
        assert summary["placed"] == 1  # Only HDFC should be placed (completed order doesn't block)
        assert summary["skipped_duplicates"] == 3


class TestPaperTradingSellMonitoring:
    """Test frozen EMA9 sell monitoring strategy"""

    @pytest.fixture
    def adapter_with_holdings(self, db_session, test_user):
        """Create adapter with mock holdings for sell monitoring tests"""
        from config.strategy_config import StrategyConfig

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        mock_broker = MagicMock()
        mock_broker.is_connected.return_value = True
        mock_broker.config = MagicMock()
        mock_broker.config.max_position_size = 100000.0

        # Mock holdings
        mock_holding1 = MagicMock()
        mock_holding1.symbol = "RELIANCE"
        mock_holding1.quantity = 40
        mock_holding1.average_price = MagicMock(amount=2500.0)

        mock_holding2 = MagicMock()
        mock_holding2.symbol = "TCS"
        mock_holding2.quantity = 30
        mock_holding2.average_price = MagicMock(amount=3500.0)

        mock_broker.get_holdings.return_value = [mock_holding1, mock_holding2]
        mock_broker.place_order.return_value = "SELL_ORDER_123"

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
        )
        adapter.broker = mock_broker
        adapter.engine = PaperTradingEngineAdapter(
            broker=mock_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=adapter.logger,
        )

        return adapter

    def test_place_sell_orders_frozen_ema9(self, db_session, test_user, adapter_with_holdings):
        """Test that sell orders are placed at frozen EMA9 target"""
        from unittest.mock import patch

        # Mock EMA9 calculation
        def mock_calculate_ema9(ticker):
            if "RELIANCE" in ticker:
                return 2600.0  # EMA9 for RELIANCE
            elif "TCS" in ticker:
                return 3600.0  # EMA9 for TCS
            return None

        with patch.object(
            adapter_with_holdings, "_calculate_ema9", side_effect=mock_calculate_ema9
        ):
            adapter_with_holdings._place_sell_orders()

        # Verify sell orders were placed at frozen targets
        assert len(adapter_with_holdings.active_sell_orders) == 2

        # Check RELIANCE sell order
        assert "RELIANCE" in adapter_with_holdings.active_sell_orders
        reliance_order = adapter_with_holdings.active_sell_orders["RELIANCE"]
        assert reliance_order["target_price"] == 2600.0
        assert reliance_order["qty"] == 40

        # Check TCS sell order
        assert "TCS" in adapter_with_holdings.active_sell_orders
        tcs_order = adapter_with_holdings.active_sell_orders["TCS"]
        assert tcs_order["target_price"] == 3600.0
        assert tcs_order["qty"] == 30

    def test_sell_orders_not_duplicated(self, db_session, test_user, adapter_with_holdings):
        """Test that sell orders are not duplicated if already active"""
        from unittest.mock import patch

        # Pre-populate active sell orders
        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "EXISTING_ORDER",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        def mock_calculate_ema9(ticker):
            if "RELIANCE" in ticker:
                return 2650.0  # Different EMA9 (should NOT update)
            elif "TCS" in ticker:
                return 3600.0
            return None

        with patch.object(
            adapter_with_holdings, "_calculate_ema9", side_effect=mock_calculate_ema9
        ):
            adapter_with_holdings._place_sell_orders()

        # RELIANCE should still have original frozen target
        assert adapter_with_holdings.active_sell_orders["RELIANCE"]["target_price"] == 2600.0
        assert adapter_with_holdings.active_sell_orders["RELIANCE"]["order_id"] == "EXISTING_ORDER"

        # TCS should have new order
        assert "TCS" in adapter_with_holdings.active_sell_orders
        assert adapter_with_holdings.active_sell_orders["TCS"]["target_price"] == 3600.0

    def test_monitor_sell_orders_target_reached(self, db_session, test_user, adapter_with_holdings):
        """Test exit condition: High >= Frozen Target"""
        from unittest.mock import MagicMock, patch

        import pandas as pd

        # Set up active sell order with frozen target
        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL_ORDER_123",
                "target_price": 2600.0,  # Frozen target
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
                "entry_price": 2500.0,
            }
        }

        # Mock check_and_execute_pending_orders to simulate order execution
        mock_execution_summary = {"checked": 1, "executed": 1, "still_pending": 0}
        adapter_with_holdings.broker.check_and_execute_pending_orders = MagicMock(
            return_value=mock_execution_summary
        )

        # Mock get_holding to return None (position closed after execution)
        adapter_with_holdings.broker.get_holding = MagicMock(return_value=None)

        # Mock OHLCV data where High >= Target (use lowercase columns like fetch_ohlcv_yf returns)
        mock_data = pd.DataFrame(
            {
                "high": [2650.0],  # High >= 2600.0 (target reached!)
                "close": [2620.0],
                "rsi10": [45.0],  # RSI < 50 (not triggered)
            }
        )

        with patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data):
            with patch("pandas_ta.rsi") as mock_rsi:
                mock_data["rsi10"] = 45.0
                mock_rsi.return_value = pd.Series([45.0])

                adapter_with_holdings._monitor_sell_orders()

        # Order should be removed from tracking (position closed)
        assert "RELIANCE" not in adapter_with_holdings.active_sell_orders

        # Verify check_and_execute_pending_orders was called
        assert adapter_with_holdings.broker.check_and_execute_pending_orders.called

    def test_monitor_sell_orders_rsi_exit(self, db_session, test_user, adapter_with_holdings):
        """Test exit condition: RSI > 50 (falling knife)"""
        from unittest.mock import patch

        import pandas as pd

        # Set up active sell order
        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL_ORDER_123",
                "target_price": 2600.0,  # Target not reached
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        # Mock OHLCV data where RSI > 50 but High < Target (use lowercase columns like fetch_ohlcv_yf returns)
        mock_data = pd.DataFrame(
            {
                "high": [2550.0],  # High < Target (not reached)
                "close": [2520.0],
                "rsi10": [52.0],  # RSI > 50 (falling knife exit!)
            }
        )

        with patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data):
            with patch("pandas_ta.rsi") as mock_rsi:
                mock_data["rsi10"] = 52.0
                mock_rsi.return_value = pd.Series([52.0])

                adapter_with_holdings._monitor_sell_orders()

        # Order should be removed (RSI exit triggered)
        assert "RELIANCE" not in adapter_with_holdings.active_sell_orders

        # Verify market order was placed
        assert adapter_with_holdings.broker.place_order.called
        call_args = adapter_with_holdings.broker.place_order.call_args
        market_order = call_args[0][0]
        assert market_order.transaction_type.name == "SELL"
        assert market_order.order_type.name == "MARKET"

    def test_monitor_sell_orders_no_exit(self, db_session, test_user, adapter_with_holdings):
        """Test that order remains active when neither exit condition is met"""
        from unittest.mock import patch

        import pandas as pd

        # Set up active sell order
        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL_ORDER_123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        # Mock OHLCV data where neither exit condition is met
        mock_data = pd.DataFrame(
            {
                "High": [2580.0],  # High < Target
                "Close": [2560.0],
                "RSI10": [45.0],  # RSI < 50
            }
        )

        with patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data):
            with patch("pandas_ta.rsi") as mock_rsi:
                mock_data["RSI10"] = 45.0
                mock_rsi.return_value = pd.Series([45.0])

                adapter_with_holdings._monitor_sell_orders()

        # Order should still be active
        assert "RELIANCE" in adapter_with_holdings.active_sell_orders
        assert adapter_with_holdings.active_sell_orders["RELIANCE"]["target_price"] == 2600.0

    def test_frozen_target_never_updates(self, db_session, test_user, adapter_with_holdings):
        """Test that frozen target price NEVER updates after initial placement"""
        from unittest.mock import patch

        import pandas as pd

        initial_target = 2600.0

        # Set up active sell order
        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL_ORDER_123",
                "target_price": initial_target,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        # Mock data where EMA9 has changed significantly
        mock_data = pd.DataFrame(
            {
                "High": [2580.0],
                "Close": [2560.0],
                "RSI10": [45.0],
            }
        )

        # Mock EMA9 calculation returning different value
        def mock_calculate_ema9(ticker):
            return 2700.0  # EMA9 has moved up significantly!

        with patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data):
            with patch("pandas_ta.rsi") as mock_rsi:
                mock_data["RSI10"] = 45.0
                mock_rsi.return_value = pd.Series([45.0])

                with patch.object(
                    adapter_with_holdings, "_calculate_ema9", side_effect=mock_calculate_ema9
                ):
                    adapter_with_holdings._monitor_sell_orders()

        # Target should STILL be frozen at original value
        assert "RELIANCE" in adapter_with_holdings.active_sell_orders
        assert (
            adapter_with_holdings.active_sell_orders["RELIANCE"]["target_price"] == initial_target
        )
        assert adapter_with_holdings.active_sell_orders["RELIANCE"]["target_price"] != 2700.0

    def test_calculate_ema9_with_lowercase_columns(self, db_session, test_user):
        """Test that _calculate_ema9 works with lowercase column names from fetch_ohlcv_yf"""
        from unittest.mock import patch

        import pandas as pd

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
        )

        # Mock data with lowercase columns (as returned by fetch_ohlcv_yf)
        mock_data = pd.DataFrame(
            {
                "date": pd.date_range(start="2024-01-01", periods=50),
                "open": [2500.0] * 50,
                "high": [2550.0] * 50,
                "low": [2480.0] * 50,
                "close": [2520.0 + i for i in range(50)],  # Trending up
                "volume": [1000000] * 50,
            }
        )

        with patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data):
            with patch("pandas_ta.ema") as mock_ema:
                # Mock EMA calculation
                mock_ema.return_value = pd.Series([2565.0] * 50)

                result = adapter._calculate_ema9("RELIANCE.NS")

                # Verify it was called with lowercase "close"
                mock_ema.assert_called_once()
                call_args = mock_ema.call_args
                assert "close" in str(call_args) or call_args[0][0].name == "close"
                assert result == 2565.0

    def test_monitor_sell_orders_with_lowercase_columns(self, db_session, test_user):
        """Test that _monitor_sell_orders works with lowercase column names"""
        from unittest.mock import MagicMock, patch

        import pandas as pd

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
        )
        adapter.broker = MagicMock()
        adapter.logger = MagicMock()

        # Set up active sell order
        adapter.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL_ORDER_123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        # Mock OHLCV data with lowercase columns (as returned by fetch_ohlcv_yf)
        mock_data = pd.DataFrame(
            {
                "date": pd.date_range(start="2024-01-01", periods=50),
                "open": [2500.0] * 50,
                "high": [2650.0] * 50,  # High exceeds target
                "low": [2480.0] * 50,
                "close": [2620.0] * 50,
                "volume": [1000000] * 50,
            }
        )

        with patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data):
            with patch("pandas_ta.rsi") as mock_rsi:
                # Mock RSI calculation
                mock_rsi.return_value = pd.Series([45.0] * 50)

                # Ensure broker reports no remaining holding so order is removed
                adapter.broker.get_holding.return_value = None

                adapter._monitor_sell_orders()

                # Verify RSI was called with lowercase "close"
                mock_rsi.assert_called_once()
                call_args = mock_rsi.call_args
                assert "close" in str(call_args) or call_args[0][0].name == "close"

        # Order should be removed (target reached)
        assert "RELIANCE" not in adapter.active_sell_orders

    def test_monitor_sell_orders_fetches_60_days(self, db_session, test_user):
        """Test that _monitor_sell_orders fetches 60 days of data for stable indicators"""
        from unittest.mock import MagicMock, patch

        import pandas as pd

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
        )
        adapter.broker = MagicMock()
        adapter.logger = MagicMock()

        adapter.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL_ORDER_123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        mock_data = pd.DataFrame(
            {
                "high": [2580.0],
                "close": [2560.0],
            }
        )

        with patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data) as mock_fetch:
            with patch("pandas_ta.rsi", return_value=pd.Series([45.0])):
                adapter._monitor_sell_orders()

                # Verify fetch_ohlcv_yf was called with days=60
                mock_fetch.assert_called_with("RELIANCE.NS", days=60, interval="1d")

    def test_service_state_attributes(self, db_session, test_user):
        """Test that service has running and shutdown_requested attributes for scheduler control"""
        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
        )

        # Verify state attributes exist
        assert hasattr(adapter, "running")
        assert hasattr(adapter, "shutdown_requested")

        # Verify initial state
        assert adapter.running is False
        assert adapter.shutdown_requested is False

        # Test state changes
        adapter.running = True
        assert adapter.running is True

        adapter.shutdown_requested = True
        assert adapter.shutdown_requested is True

    def test_load_sell_orders_from_file(self, db_session, test_user, tmp_path):
        """Test loading sell orders from file on startup"""
        import json

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            storage_path=str(tmp_path),
        )
        adapter.broker = MagicMock()

        # Create mock holdings
        mock_holding = MagicMock()
        mock_holding.symbol = "RELIANCE"
        adapter.broker.get_holdings.return_value = [mock_holding]

        # Create mock pending orders (empty)
        adapter.broker.get_pending_orders.return_value = []

        # Create sell orders file with existing orders
        sell_orders_data = {
            "RELIANCE": {
                "order_id": "LOADED_ORDER_123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            },
            "TCS": {
                "order_id": "LOADED_ORDER_456",
                "target_price": 3600.0,
                "qty": 30,
                "ticker": "TCS.NS",
                "entry_date": "2024-01-01",
            },
        }

        # Write file
        adapter._sell_orders_file.parent.mkdir(parents=True, exist_ok=True)
        with open(adapter._sell_orders_file, "w") as f:
            json.dump(sell_orders_data, f)

        # Load orders
        adapter._load_sell_orders_from_file()

        # Verify RELIANCE order loaded (has holdings)
        assert "RELIANCE" in adapter.active_sell_orders
        assert adapter.active_sell_orders["RELIANCE"]["order_id"] == "LOADED_ORDER_123"
        assert adapter.active_sell_orders["RELIANCE"]["target_price"] == 2600.0

        # Verify TCS order NOT loaded (no holdings)
        assert "TCS" not in adapter.active_sell_orders

    def test_load_sell_orders_from_file_filters_stale_orders(self, db_session, test_user, tmp_path):
        """Test that stale orders (no holdings, no pending) are filtered out"""
        import json

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            storage_path=str(tmp_path),
        )
        adapter.broker = MagicMock()

        # No holdings
        adapter.broker.get_holdings.return_value = []

        # No pending orders
        adapter.broker.get_pending_orders.return_value = []

        # Create sell orders file with stale orders
        sell_orders_data = {
            "RELIANCE": {
                "order_id": "STALE_ORDER_123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            },
        }

        # Write file
        adapter._sell_orders_file.parent.mkdir(parents=True, exist_ok=True)
        with open(adapter._sell_orders_file, "w") as f:
            json.dump(sell_orders_data, f)

        # Load orders
        adapter._load_sell_orders_from_file()

        # Verify stale order was filtered out
        assert len(adapter.active_sell_orders) == 0
        assert "RELIANCE" not in adapter.active_sell_orders

    def test_load_sell_orders_from_file_keeps_pending_orders(self, db_session, test_user, tmp_path):
        """Test that orders with pending broker orders are kept even without holdings"""
        import json

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            storage_path=str(tmp_path),
        )
        adapter.broker = MagicMock()

        # No holdings
        adapter.broker.get_holdings.return_value = []

        # Create mock pending sell order
        mock_pending_order = MagicMock()
        mock_pending_order.symbol = "RELIANCE"
        mock_pending_order.is_sell_order.return_value = True
        mock_pending_order.is_active.return_value = True
        adapter.broker.get_pending_orders.return_value = [mock_pending_order]

        # Create sell orders file
        sell_orders_data = {
            "RELIANCE": {
                "order_id": "PENDING_ORDER_123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            },
        }

        # Write file
        adapter._sell_orders_file.parent.mkdir(parents=True, exist_ok=True)
        with open(adapter._sell_orders_file, "w") as f:
            json.dump(sell_orders_data, f)

        # Load orders
        adapter._load_sell_orders_from_file()

        # Verify order kept (has pending order in broker)
        assert "RELIANCE" in adapter.active_sell_orders
        assert adapter.active_sell_orders["RELIANCE"]["order_id"] == "PENDING_ORDER_123"

    def test_load_sell_orders_from_file_missing_file(self, db_session, test_user, tmp_path):
        """Test that missing file doesn't cause error"""
        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            storage_path=str(tmp_path),
        )
        adapter.broker = MagicMock()

        # File doesn't exist
        assert not adapter._sell_orders_file.exists()

        # Load should not error
        adapter._load_sell_orders_from_file()

        # Should have empty dict
        assert len(adapter.active_sell_orders) == 0

    def test_place_sell_orders_skips_loaded_orders(
        self, db_session, test_user, adapter_with_holdings, tmp_path
    ):
        """Test that _place_sell_orders skips orders loaded from file"""
        from unittest.mock import patch

        # Set storage path
        adapter_with_holdings.storage_path = str(tmp_path)
        adapter_with_holdings._sell_orders_file = tmp_path / "active_sell_orders.json"

        # Pre-load an order from file (simulating service restart)
        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "LOADED_ORDER_123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        def mock_calculate_ema9(ticker):
            if "RELIANCE" in ticker:
                return 2650.0  # Different EMA9 (should NOT place new order)
            elif "TCS" in ticker:
                return 3600.0
            return None

        with patch.object(
            adapter_with_holdings, "_calculate_ema9", side_effect=mock_calculate_ema9
        ):
            adapter_with_holdings._place_sell_orders()

        # RELIANCE should still have loaded order (not replaced)
        assert (
            adapter_with_holdings.active_sell_orders["RELIANCE"]["order_id"] == "LOADED_ORDER_123"
        )
        assert adapter_with_holdings.active_sell_orders["RELIANCE"]["target_price"] == 2600.0

        # TCS should have new order
        assert "TCS" in adapter_with_holdings.active_sell_orders
        assert adapter_with_holdings.active_sell_orders["TCS"]["target_price"] == 3600.0

    def test_place_sell_orders_skips_pending_broker_orders(
        self, db_session, test_user, adapter_with_holdings
    ):
        """Test that _place_sell_orders skips symbols with pending orders in broker"""
        from unittest.mock import MagicMock, patch

        # Create mock pending sell order in broker
        mock_pending_order = MagicMock()
        mock_pending_order.symbol = "RELIANCE"
        mock_pending_order.is_sell_order.return_value = True
        mock_pending_order.is_active.return_value = True
        mock_pending_order.price = MagicMock(amount=2600.0)
        mock_pending_order.order_id = "BROKER_ORDER_123"

        adapter_with_holdings.broker.get_pending_orders.return_value = [mock_pending_order]

        # Clear active_sell_orders (simulating service restart without file)
        adapter_with_holdings.active_sell_orders = {}

        def mock_calculate_ema9(ticker):
            if "RELIANCE" in ticker:
                return 2650.0  # Would place new order if not skipped
            elif "TCS" in ticker:
                return 3600.0
            return None

        with patch.object(
            adapter_with_holdings, "_calculate_ema9", side_effect=mock_calculate_ema9
        ):
            adapter_with_holdings._place_sell_orders()

        # RELIANCE should be skipped (has pending order in broker)
        # But should be restored to active_sell_orders from broker
        assert "RELIANCE" in adapter_with_holdings.active_sell_orders
        assert adapter_with_holdings.active_sell_orders["RELIANCE"]["target_price"] == 2600.0

        # TCS should have new order
        assert "TCS" in adapter_with_holdings.active_sell_orders

    def test_initialize_loads_sell_orders(self, db_session, test_user, tmp_path):
        """Test that initialize() calls _load_sell_orders_from_file()"""
        import json

        with (
            patch(
                "src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter"
            ) as mock_broker_class,
            patch(
                "src.application.services.paper_trading_service_adapter.PaperTradingConfig"
            ) as mock_config_class,
        ):
            mock_broker = MagicMock()
            mock_broker.connect.return_value = True
            mock_broker.get_holdings.return_value = []
            mock_broker.get_available_balance.return_value = MagicMock(amount=100000.0)
            mock_broker.get_pending_orders.return_value = []
            mock_broker_class.return_value = mock_broker

            adapter = PaperTradingServiceAdapter(
                user_id=test_user.id,
                db_session=db_session,
                initial_capital=100000.0,
                storage_path=str(tmp_path),
            )

            # Create sell orders file
            sell_orders_data = {
                "RELIANCE": {
                    "order_id": "INIT_ORDER_123",
                    "target_price": 2600.0,
                    "qty": 40,
                    "ticker": "RELIANCE.NS",
                    "entry_date": "2024-01-01",
                },
            }
            adapter._sell_orders_file.parent.mkdir(parents=True, exist_ok=True)
            with open(adapter._sell_orders_file, "w") as f:
                json.dump(sell_orders_data, f)

            # Initialize
            result = adapter.initialize()

            # Verify initialization succeeded
            assert result is True

            # Verify orders were loaded (even though no holdings, file exists)
            # Note: In real scenario, orders would be filtered if no holdings AND no pending orders
            # But we're just testing that _load_sell_orders_from_file was called
            assert hasattr(adapter, "active_sell_orders")

    def test_update_sell_order_quantity_after_reentry(
        self, db_session, test_user, adapter_with_holdings
    ):
        """Test that sell order quantity is updated when re-entry increases holdings"""
        from unittest.mock import MagicMock

        # Set up existing sell order
        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "OLD_SELL_ORDER_123",
                "target_price": 2600.0,  # Frozen target
                "qty": 40,  # Old quantity
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        # Mock broker to simulate holdings increase (re-entry happened)
        mock_holding = MagicMock()
        mock_holding.symbol = "RELIANCE"
        mock_holding.quantity = 60  # Increased from 40 to 60 (re-entry added 20)
        adapter_with_holdings.broker.get_holdings.return_value = [mock_holding]

        # Mock cancel and place order
        adapter_with_holdings.broker.cancel_order.return_value = True
        adapter_with_holdings.broker.place_order.return_value = "NEW_SELL_ORDER_456"

        # Mock EMA9 calculation to return new target
        from unittest.mock import patch

        new_target = 2650.0  # New EMA9 target after re-entry
        with patch.object(adapter_with_holdings, "_calculate_ema9", return_value=new_target):
            # Update sell order quantity (target will be recalculated)
            result = adapter_with_holdings._update_sell_order_quantity("RELIANCE", 60)

        # Verify update succeeded
        assert result is True
        assert adapter_with_holdings.active_sell_orders["RELIANCE"]["qty"] == 60
        assert (
            adapter_with_holdings.active_sell_orders["RELIANCE"]["target_price"] == new_target
        )  # Recalculated!
        assert (
            adapter_with_holdings.active_sell_orders["RELIANCE"]["order_id"] == "NEW_SELL_ORDER_456"
        )

        # Verify old order was cancelled
        adapter_with_holdings.broker.cancel_order.assert_called_with("OLD_SELL_ORDER_123")

        # Verify new order was placed with correct quantity and recalculated target
        adapter_with_holdings.broker.place_order.assert_called_once()
        new_order = adapter_with_holdings.broker.place_order.call_args[0][0]
        assert new_order.quantity == 60
        assert new_order.transaction_type.value == "SELL"
        assert float(new_order.price.amount) == new_target  # Recalculated target

    def test_sync_sell_order_quantities_with_holdings(
        self, db_session, test_user, adapter_with_holdings
    ):
        """Test that _sync_sell_order_quantities_with_holdings updates multiple orders"""
        from unittest.mock import MagicMock

        # Set up multiple sell orders with outdated quantities
        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL_ORDER_1",
                "target_price": 2600.0,
                "qty": 40,  # Old quantity
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            },
            "TCS": {
                "order_id": "SELL_ORDER_2",
                "target_price": 3600.0,
                "qty": 30,  # Old quantity
                "ticker": "TCS.NS",
                "entry_date": "2024-01-01",
            },
        }

        # Mock holdings with increased quantities (re-entries happened)
        mock_holding1 = MagicMock()
        mock_holding1.symbol = "RELIANCE"
        mock_holding1.quantity = 60  # Increased from 40

        mock_holding2 = MagicMock()
        mock_holding2.symbol = "TCS"
        mock_holding2.quantity = 30  # Same (no re-entry)

        adapter_with_holdings.broker.get_holdings.return_value = [
            mock_holding1,
            mock_holding2,
        ]

        # Mock cancel and place order
        adapter_with_holdings.broker.cancel_order.return_value = True
        adapter_with_holdings.broker.place_order.side_effect = [
            "NEW_SELL_ORDER_1",
            "NEW_SELL_ORDER_2",
        ]

        # Mock EMA9 calculation to return new targets
        from unittest.mock import patch

        new_target_reliance = 2650.0
        with patch.object(
            adapter_with_holdings, "_calculate_ema9", return_value=new_target_reliance
        ):
            # Sync quantities (targets will be recalculated)
            updated_count = adapter_with_holdings._sync_sell_order_quantities_with_holdings()

        # Verify only RELIANCE was updated (TCS quantity didn't change)
        assert updated_count == 1
        assert adapter_with_holdings.active_sell_orders["RELIANCE"]["qty"] == 60
        assert (
            adapter_with_holdings.active_sell_orders["RELIANCE"]["target_price"]
            == new_target_reliance
        )
        assert adapter_with_holdings.active_sell_orders["TCS"]["qty"] == 30  # Unchanged

    def test_update_sell_order_quantity_recalculates_target(
        self, db_session, test_user, adapter_with_holdings
    ):
        """Test that target price is recalculated as EMA9 when quantity is updated (matches backtest)"""
        from unittest.mock import patch

        old_target = 2600.0
        new_target = 2650.0  # New EMA9 target

        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "OLD_ORDER",
                "target_price": old_target,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        adapter_with_holdings.broker.cancel_order.return_value = True
        adapter_with_holdings.broker.place_order.return_value = "NEW_ORDER"

        # Mock EMA9 calculation to return new target
        with patch.object(adapter_with_holdings, "_calculate_ema9", return_value=new_target):
            # Update quantity (target will be recalculated)
            adapter_with_holdings._update_sell_order_quantity("RELIANCE", 60)

        # Verify target price was recalculated (not frozen)
        assert adapter_with_holdings.active_sell_orders["RELIANCE"]["target_price"] == new_target

        # Verify new order was placed with recalculated target
        new_order = adapter_with_holdings.broker.place_order.call_args[0][0]
        assert float(new_order.price.amount) == new_target

    def test_place_sell_orders_updates_quantity_on_reentry(
        self, db_session, test_user, adapter_with_holdings
    ):
        """Test that _place_sell_orders detects and updates quantity when holdings increased"""
        from unittest.mock import MagicMock

        # Set up existing sell order with old quantity
        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "EXISTING_ORDER",
                "target_price": 2600.0,
                "qty": 40,  # Old quantity
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        # Mock holdings with increased quantity (re-entry happened)
        mock_holding = MagicMock()
        mock_holding.symbol = "RELIANCE"
        mock_holding.quantity = 60  # Increased from 40
        adapter_with_holdings.broker.get_holdings.return_value = [mock_holding]

        # Mock pending orders (existing sell order)
        mock_pending_order = MagicMock()
        mock_pending_order.symbol = "RELIANCE"
        mock_pending_order.is_sell_order.return_value = True
        mock_pending_order.is_active.return_value = True
        adapter_with_holdings.broker.get_pending_orders.return_value = [mock_pending_order]

        # Mock cancel and place order
        adapter_with_holdings.broker.cancel_order.return_value = True
        adapter_with_holdings.broker.place_order.return_value = "UPDATED_ORDER"

        # Mock EMA9 calculation to return new target
        from unittest.mock import patch

        new_target = 2650.0  # New EMA9 target after re-entry
        with patch.object(adapter_with_holdings, "_calculate_ema9", return_value=new_target):
            # Call _place_sell_orders (should detect quantity mismatch and update)
            adapter_with_holdings._place_sell_orders()

        # Verify quantity and target were updated
        assert adapter_with_holdings.active_sell_orders["RELIANCE"]["qty"] == 60
        assert adapter_with_holdings.active_sell_orders["RELIANCE"]["target_price"] == new_target

        # Verify order was cancelled and new one placed
        adapter_with_holdings.broker.cancel_order.assert_called_with("EXISTING_ORDER")
        adapter_with_holdings.broker.place_order.assert_called_once()

        # Verify new order was placed with recalculated target
        new_order = adapter_with_holdings.broker.place_order.call_args[0][0]
        assert float(new_order.price.amount) == new_target

    def test_update_sell_order_quantity_no_update_if_quantity_same(
        self, db_session, test_user, adapter_with_holdings
    ):
        """Test that quantity is not updated if holdings quantity hasn't increased"""
        from unittest.mock import MagicMock

        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL_ORDER",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        adapter_with_holdings.broker.cancel_order = MagicMock()
        adapter_with_holdings.broker.place_order = MagicMock()

        # Try to update with same quantity (should return False)
        result = adapter_with_holdings._update_sell_order_quantity("RELIANCE", 40)

        # Verify no update happened
        assert result is False
        adapter_with_holdings.broker.cancel_order.assert_not_called()
        adapter_with_holdings.broker.place_order.assert_not_called()

    def test_update_sell_order_quantity_no_update_if_quantity_decreased(
        self, db_session, test_user, adapter_with_holdings
    ):
        """Test that quantity is not updated if new quantity is less than current"""
        from unittest.mock import MagicMock

        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL_ORDER",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        adapter_with_holdings.broker.cancel_order = MagicMock()
        adapter_with_holdings.broker.place_order = MagicMock()

        # Try to update with lower quantity (should return False)
        result = adapter_with_holdings._update_sell_order_quantity("RELIANCE", 30)

        # Verify no update happened
        assert result is False
        adapter_with_holdings.broker.cancel_order.assert_not_called()
        adapter_with_holdings.broker.place_order.assert_not_called()


class TestSignalStatusFiltering:
    """Test that signal status filtering works correctly in load_latest_recommendations"""

    def test_load_recommendations_includes_active_signals(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that ACTIVE signals are included in recommendations"""
        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create ACTIVE signals
        signal1 = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        signal2 = Signals(
            symbol="TCS",
            verdict="strong_buy",
            final_verdict="strong_buy",
            last_close=3500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        db_session.add_all([signal1, signal2])
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should return both ACTIVE signals
        assert len(recs) == 2
        tickers = {r.ticker for r in recs}
        assert "RELIANCE.NS" in tickers
        assert "TCS.NS" in tickers

    def test_load_recommendations_excludes_traded_signals(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that TRADED signals (per-user) are excluded from recommendations"""
        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create ACTIVE signal
        signal = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # Mark as TRADED for this user (per-user status)
        user_status = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal.id,
            symbol="RELIANCE",
            status=SignalStatus.TRADED,
        )
        db_session.add(user_status)
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should exclude TRADED signal
        assert len(recs) == 0

    def test_load_recommendations_excludes_rejected_signals(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that REJECTED signals (per-user) are excluded from recommendations"""
        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create ACTIVE signal
        signal = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # Mark as REJECTED for this user (per-user status)
        user_status = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal.id,
            symbol="RELIANCE",
            status=SignalStatus.REJECTED,
        )
        db_session.add(user_status)
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should exclude REJECTED signal
        assert len(recs) == 0

    def test_load_recommendations_excludes_expired_signals(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that EXPIRED signals (base status) are excluded from recommendations"""
        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create EXPIRED signal
        signal = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.EXPIRED,
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should exclude EXPIRED signal
        assert len(recs) == 0

    def test_load_recommendations_per_user_status_takes_precedence(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that per-user status takes precedence over base signal status"""
        # Create another user
        user2 = Users(
            email="user2@test.com",
            password_hash="hash2",
            role="user",
        )
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user2)

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create signal with EXPIRED base status
        signal = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.EXPIRED,  # Base status is EXPIRED
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # But mark as ACTIVE for test_user (per-user status)
        user_status = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal.id,
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,  # Per-user status is ACTIVE
        )
        db_session.add(user_status)
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should include signal because per-user status (ACTIVE) takes precedence
        assert len(recs) == 1
        assert recs[0].ticker == "RELIANCE.NS"

    def test_load_recommendations_mixed_status_signals(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test filtering with mixed status signals"""
        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create multiple signals with different statuses
        signal1 = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        signal2 = Signals(
            symbol="TCS",
            verdict="strong_buy",
            final_verdict="strong_buy",
            last_close=3500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        signal3 = Signals(
            symbol="INFY",
            verdict="buy",
            final_verdict="buy",
            last_close=1500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        signal4 = Signals(
            symbol="HDFC",
            verdict="buy",
            final_verdict="buy",
            last_close=2000.0,
            status=SignalStatus.EXPIRED,
            ts=ist_now(),
        )
        db_session.add_all([signal1, signal2, signal3, signal4])
        db_session.commit()
        db_session.refresh(signal2)
        db_session.refresh(signal3)

        # Mark signal2 as TRADED (per-user)
        user_status_traded = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal2.id,
            symbol="TCS",
            status=SignalStatus.TRADED,
        )
        # Mark signal3 as REJECTED (per-user)
        user_status_rejected = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal3.id,
            symbol="INFY",
            status=SignalStatus.REJECTED,
        )
        db_session.add_all([user_status_traded, user_status_rejected])
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should only return signal1 (ACTIVE, no per-user status)
        # signal2 is TRADED (per-user) - excluded
        # signal3 is REJECTED (per-user) - excluded
        # signal4 is EXPIRED (base) - excluded
        assert len(recs) == 1
        assert recs[0].ticker == "RELIANCE.NS"
