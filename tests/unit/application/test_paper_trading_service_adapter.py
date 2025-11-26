"""
Tests for Paper Trading Service Adapter

Tests that paper trading mode works correctly for individual services.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.application.services.paper_trading_service_adapter import (
    PaperTradingEngineAdapter,
    PaperTradingServiceAdapter,
)
from src.infrastructure.db.models import Users


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
        with patch(
            "src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter"
        ) as mock_broker_class, patch(
            "src.application.services.paper_trading_service_adapter.PaperTradingConfig"
        ) as mock_config_class:
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
        with patch(
            "src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter"
        ) as mock_broker_class, patch(
            "src.application.services.paper_trading_service_adapter.PaperTradingConfig"
        ) as mock_config_class:
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
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from config.strategy_config import StrategyConfig

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

        with patch.object(adapter.engine, "load_latest_recommendations", return_value=recommendations):
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
        """Test placing new entries"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from config.strategy_config import StrategyConfig

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

        summary = adapter.place_new_entries(recommendations)

        assert summary["attempted"] == 1
        assert summary["placed"] == 1
        assert mock_paper_broker.place_order.called

    def test_place_new_entries_respects_max_position_size(self, db_session, test_user, mock_paper_broker):
        """Test that orders respect max_position_size limit"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from config.strategy_config import StrategyConfig

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
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from modules.kotak_neo_auto_trader.domain import Holding
        from config.strategy_config import StrategyConfig

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
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from config.strategy_config import StrategyConfig

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

        with patch(
            "src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter"
        ) as mock_broker_class, patch(
            "src.application.services.paper_trading_service_adapter.PaperTradingConfig"
        ) as mock_config_class:
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
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from modules.kotak_neo_auto_trader.domain import Order, OrderType, TransactionType, OrderStatus
        from config.strategy_config import StrategyConfig

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

    def test_place_new_entries_multiple_pending_orders(self, db_session, test_user, mock_paper_broker):
        """Test duplicate prevention with multiple pending orders"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from modules.kotak_neo_auto_trader.domain import OrderStatus, TransactionType
        from config.strategy_config import StrategyConfig

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
            pending_reliance, pending_infy, completed_order
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
        import pandas as pd
        from unittest.mock import patch
        
        # Mock EMA9 calculation
        def mock_calculate_ema9(ticker):
            if "RELIANCE" in ticker:
                return 2600.0  # EMA9 for RELIANCE
            elif "TCS" in ticker:
                return 3600.0  # EMA9 for TCS
            return None
        
        with patch.object(
            adapter_with_holdings, '_calculate_ema9', side_effect=mock_calculate_ema9
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
            adapter_with_holdings, '_calculate_ema9', side_effect=mock_calculate_ema9
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
        import pandas as pd
        from unittest.mock import patch
        
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
        
        # Mock OHLCV data where High >= Target
        mock_data = pd.DataFrame({
            "High": [2650.0],  # High >= 2600.0 (target reached!)
            "Close": [2620.0],
            "RSI10": [45.0],  # RSI < 50 (not triggered)
        })
        
        with patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data):
            with patch("pandas_ta.rsi") as mock_rsi:
                mock_data["RSI10"] = 45.0
                mock_rsi.return_value = pd.Series([45.0])
                
                adapter_with_holdings._monitor_sell_orders()
        
        # Order should be removed (target reached)
        assert "RELIANCE" not in adapter_with_holdings.active_sell_orders

    def test_monitor_sell_orders_rsi_exit(self, db_session, test_user, adapter_with_holdings):
        """Test exit condition: RSI > 50 (falling knife)"""
        import pandas as pd
        from unittest.mock import patch
        
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
        
        # Mock OHLCV data where RSI > 50 but High < Target
        mock_data = pd.DataFrame({
            "High": [2550.0],  # High < Target (not reached)
            "Close": [2520.0],
            "RSI10": [52.0],  # RSI > 50 (falling knife exit!)
        })
        
        with patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data):
            with patch("pandas_ta.rsi") as mock_rsi:
                mock_data["RSI10"] = 52.0
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
        import pandas as pd
        from unittest.mock import patch
        
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
        mock_data = pd.DataFrame({
            "High": [2580.0],  # High < Target
            "Close": [2560.0],
            "RSI10": [45.0],  # RSI < 50
        })
        
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
        import pandas as pd
        from unittest.mock import patch
        
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
        mock_data = pd.DataFrame({
            "High": [2580.0],
            "Close": [2560.0],
            "RSI10": [45.0],
        })
        
        # Mock EMA9 calculation returning different value
        def mock_calculate_ema9(ticker):
            return 2700.0  # EMA9 has moved up significantly!
        
        with patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data):
            with patch("pandas_ta.rsi") as mock_rsi:
                mock_data["RSI10"] = 45.0
                mock_rsi.return_value = pd.Series([45.0])
                
                with patch.object(
                    adapter_with_holdings, '_calculate_ema9', side_effect=mock_calculate_ema9
                ):
                    adapter_with_holdings._monitor_sell_orders()
        
        # Target should STILL be frozen at original value
        assert "RELIANCE" in adapter_with_holdings.active_sell_orders
        assert adapter_with_holdings.active_sell_orders["RELIANCE"]["target_price"] == initial_target
        assert adapter_with_holdings.active_sell_orders["RELIANCE"]["target_price"] != 2700.0

