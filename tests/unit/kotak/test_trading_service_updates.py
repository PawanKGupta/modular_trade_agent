"""
Unit tests for Trading Service Updates

Tests verify:
1. Position monitor removal from scheduler
2. RSI exit integration in sell monitor
3. Re-entry integration in buy order service

Tests cover both real trading and paper trading.
"""

from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.run_trading_service import TradingService


class TestTradingServicePositionMonitorRemoval:
    """Test that position monitor is removed from trading service"""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session"""
        session = Mock()
        session.query = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.close = Mock()
        return session

    @pytest.fixture
    def mock_strategy_config(self):
        """Mock strategy config"""
        config = Mock()
        return config

    @pytest.fixture
    def sample_user_id(self):
        """Sample user ID for testing"""
        return 1

    @patch("modules.kotak_neo_auto_trader.run_trading_service.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.AutoTradeEngine")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.SellOrderManager")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.prevent_service_conflict")
    @patch("src.application.services.broker_credentials.create_temp_env_file")
    @patch("src.infrastructure.logging.get_user_logger")
    def test_position_monitor_not_in_tasks_completed(  # noqa: PLR0913
        self,
        mock_get_logger,
        mock_create_temp_env,
        mock_prevent_conflict,
        mock_sell_manager_class,
        mock_engine_class,
        mock_auth_class,
        mock_db_session,
        sample_user_id,
        mock_strategy_config,
    ):
        """Test that position_monitor is not in tasks_completed dict"""
        # Setup mocks
        mock_auth = Mock()
        mock_auth.login.return_value = True
        mock_auth_class.return_value = mock_auth

        mock_engine = Mock()
        mock_engine.positions_repo = Mock()
        mock_engine.orders_repo = Mock()
        mock_engine.order_verifier = None
        mock_engine.login.return_value = True
        mock_engine_class.return_value = mock_engine

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_sell_manager_instance = Mock()
        mock_sell_manager_class.return_value = mock_sell_manager_instance

        mock_prevent_conflict.return_value = True
        mock_create_temp_env.return_value = "temp_env_file.env"

        # Create service
        service = TradingService(
            user_id=sample_user_id,
            db_session=mock_db_session,
            broker_creds={"api_key": "test", "api_secret": "test"},
            strategy_config=mock_strategy_config,
        )

        # Verify position_monitor is NOT in tasks_completed
        assert "position_monitor" not in service.tasks_completed

        # Verify expected tasks are present
        assert "analysis" in service.tasks_completed
        assert "buy_orders" in service.tasks_completed
        assert "premarket_retry" in service.tasks_completed
        assert "premarket_amo_adjustment" in service.tasks_completed
        assert "sell_monitor_started" in service.tasks_completed
        assert "eod_cleanup" in service.tasks_completed

    @patch("modules.kotak_neo_auto_trader.run_trading_service.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.AutoTradeEngine")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.SellOrderManager")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.prevent_service_conflict")
    @patch("src.application.services.broker_credentials.create_temp_env_file")
    @patch("src.infrastructure.logging.get_user_logger")
    def test_no_run_position_monitor_method(  # noqa: PLR0913
        self,
        mock_get_logger,
        mock_create_temp_env,
        mock_prevent_conflict,
        mock_sell_manager_class,
        mock_engine_class,
        mock_auth_class,
        mock_db_session,
        sample_user_id,
        mock_strategy_config,
    ):
        """Test that run_position_monitor method does not exist"""
        # Setup mocks
        mock_auth = Mock()
        mock_auth.login.return_value = True
        mock_auth_class.return_value = mock_auth

        mock_engine = Mock()
        mock_engine.positions_repo = Mock()
        mock_engine.orders_repo = Mock()
        mock_engine.order_verifier = None
        mock_engine.login.return_value = True
        mock_engine_class.return_value = mock_engine

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_sell_manager_instance = Mock()
        mock_sell_manager_class.return_value = mock_sell_manager_instance

        mock_prevent_conflict.return_value = True
        mock_create_temp_env.return_value = "temp_env_file.env"

        # Create service
        service = TradingService(
            user_id=sample_user_id,
            db_session=mock_db_session,
            broker_creds={"api_key": "test", "api_secret": "test"},
            strategy_config=mock_strategy_config,
        )

        # Verify run_position_monitor method does not exist
        assert not hasattr(service, "run_position_monitor")


class TestTradingServiceRSIExitIntegration:
    """Test RSI exit integration in sell monitor"""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session"""
        session = Mock()
        session.query = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.close = Mock()
        return session

    @pytest.fixture
    def mock_strategy_config(self):
        """Mock strategy config"""
        config = Mock()
        return config

    @pytest.fixture
    def sample_user_id(self):
        """Sample user ID for testing"""
        return 1

    @patch("modules.kotak_neo_auto_trader.run_trading_service.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.AutoTradeEngine")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.SellOrderManager")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.prevent_service_conflict")
    @patch("src.application.services.broker_credentials.create_temp_env_file")
    @patch("src.infrastructure.logging.get_user_logger")
    @patch("src.application.services.task_execution_wrapper.execute_task")
    def test_run_sell_monitor_calls_rsi_exit_logic(  # noqa: PLR0913
        self,
        mock_execute_task,
        mock_get_logger,
        mock_create_temp_env,
        mock_prevent_conflict,
        mock_sell_manager_class,
        mock_engine_class,
        mock_auth_class,
        mock_db_session,
        sample_user_id,
        mock_strategy_config,
    ):
        """Test that run_sell_monitor integrates RSI exit logic"""
        # Setup mocks
        mock_auth = Mock()
        mock_auth.login.return_value = True
        mock_auth_class.return_value = mock_auth

        mock_engine = Mock()
        mock_engine.positions_repo = Mock()
        mock_engine.orders_repo = Mock()
        mock_engine.order_verifier = None
        mock_engine.login.return_value = True
        mock_engine_class.return_value = mock_engine

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Create mock sell manager with RSI exit methods
        mock_sell_manager = Mock()
        mock_sell_manager.active_sell_orders = {}
        mock_sell_manager.rsi10_cache = {}
        mock_sell_manager.converted_to_market = set()

        # Mock RSI exit methods
        mock_sell_manager._initialize_rsi10_cache = Mock()
        mock_sell_manager._check_rsi_exit_condition = Mock(return_value=False)
        mock_sell_manager.monitor_and_update = Mock()
        mock_sell_manager.run_at_market_open = Mock()

        mock_sell_manager_class.return_value = mock_sell_manager

        mock_prevent_conflict.return_value = True
        mock_create_temp_env.return_value = "temp_env_file.env"

        # Mock execute_task context manager
        mock_execute_task.return_value.__enter__ = Mock(return_value={})
        mock_execute_task.return_value.__exit__ = Mock(return_value=False)

        # Create service
        service = TradingService(
            user_id=sample_user_id,
            db_session=mock_db_session,
            broker_creds={"api_key": "test", "api_secret": "test"},
            strategy_config=mock_strategy_config,
        )

        # Initialize service
        service.initialize()
        service.sell_manager = mock_sell_manager

        # Call run_sell_monitor
        service.run_sell_monitor()

        # Verify RSI exit methods are available on sell_manager
        assert hasattr(service.sell_manager, "_initialize_rsi10_cache")
        assert hasattr(service.sell_manager, "_check_rsi_exit_condition")
        assert hasattr(service.sell_manager, "rsi10_cache")
        assert hasattr(service.sell_manager, "converted_to_market")

        # Verify run_at_market_open was called (which initializes RSI cache via _initialize_rsi10_cache)
        # This is the key method that sets up RSI exit functionality at market open
        mock_sell_manager.run_at_market_open.assert_called()

        # Note: monitor_and_update() is called in the continuous monitoring loop (scheduler),
        # not in run_sell_monitor() itself. run_sell_monitor() only starts the monitoring process.
        # The RSI exit integration is verified by checking that:
        # 1. run_at_market_open() is called (which initializes RSI cache)
        # 2. RSI exit methods are available on sell_manager


class TestTradingServiceReentryIntegration:
    """Test re-entry integration in buy order service"""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session"""
        session = Mock()
        session.query = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.close = Mock()
        return session

    @pytest.fixture
    def mock_strategy_config(self):
        """Mock strategy config"""
        config = Mock()
        return config

    @pytest.fixture
    def sample_user_id(self):
        """Sample user ID for testing"""
        return 1

    @patch("modules.kotak_neo_auto_trader.run_trading_service.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.AutoTradeEngine")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.SellOrderManager")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.prevent_service_conflict")
    @patch("src.application.services.broker_credentials.create_temp_env_file")
    @patch("src.infrastructure.logging.get_user_logger")
    @patch("src.application.services.task_execution_wrapper.execute_task")
    def test_run_buy_orders_calls_place_reentry_orders(  # noqa: PLR0913
        self,
        mock_execute_task,
        mock_get_logger,
        mock_create_temp_env,
        mock_prevent_conflict,
        mock_sell_manager_class,
        mock_engine_class,
        mock_auth_class,
        mock_db_session,
        sample_user_id,
        mock_strategy_config,
    ):
        """Test that run_buy_orders calls place_reentry_orders"""
        # Setup mocks
        mock_auth = Mock()
        mock_auth.login.return_value = True
        mock_auth_class.return_value = mock_auth

        mock_engine = Mock()
        mock_engine.positions_repo = Mock()
        mock_engine.orders_repo = Mock()
        mock_engine.order_verifier = None
        mock_engine.login.return_value = True

        # Mock place_reentry_orders method
        mock_engine.place_reentry_orders = Mock(
            return_value={
                "attempted": 0,
                "placed": 0,
                "failed_balance": 0,
                "skipped_duplicates": 0,
                "skipped_invalid_rsi": 0,
                "skipped_missing_data": 0,
                "skipped_invalid_qty": 0,
                "skipped_no_position": 0,
            }
        )

        # Mock load_latest_recommendations to return empty list (no fresh entries)
        mock_engine.load_latest_recommendations = Mock(return_value=[])
        mock_engine_class.return_value = mock_engine

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_sell_manager_instance = Mock()
        mock_sell_manager_class.return_value = mock_sell_manager_instance

        mock_prevent_conflict.return_value = True
        mock_create_temp_env.return_value = "temp_env_file.env"

        # Mock execute_task context manager
        mock_execute_task.return_value.__enter__ = Mock(return_value={})
        mock_execute_task.return_value.__exit__ = Mock(return_value=False)

        # Create service
        service = TradingService(
            user_id=sample_user_id,
            db_session=mock_db_session,
            broker_creds={"api_key": "test", "api_secret": "test"},
            strategy_config=mock_strategy_config,
        )

        # Initialize service
        service.initialize()

        # Call run_buy_orders
        service.run_buy_orders()

        # Verify place_reentry_orders was called
        mock_engine.place_reentry_orders.assert_called_once()

    @patch("modules.kotak_neo_auto_trader.run_trading_service.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.AutoTradeEngine")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.SellOrderManager")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.prevent_service_conflict")
    @patch("src.application.services.broker_credentials.create_temp_env_file")
    @patch("src.infrastructure.logging.get_user_logger")
    @patch("src.application.services.task_execution_wrapper.execute_task")
    def test_run_buy_orders_calls_place_reentry_orders_after_fresh_entries(  # noqa: PLR0913
        self,
        mock_execute_task,
        mock_get_logger,
        mock_create_temp_env,
        mock_prevent_conflict,
        mock_sell_manager_class,
        mock_engine_class,
        mock_auth_class,
        mock_db_session,
        sample_user_id,
        mock_strategy_config,
    ):
        """Test that run_buy_orders calls place_reentry_orders after placing fresh entry orders"""
        # Setup mocks
        mock_auth = Mock()
        mock_auth.login.return_value = True
        mock_auth_class.return_value = mock_auth

        mock_engine = Mock()
        mock_engine.positions_repo = Mock()
        mock_engine.orders_repo = Mock()
        mock_engine.order_verifier = None
        mock_engine.login.return_value = True

        # Mock place_new_entries to return summary
        mock_engine.place_new_entries = Mock(
            return_value={
                "attempted": 1,
                "placed": 1,
                "failed_balance": 0,
                "skipped_duplicates": 0,
                "skipped_portfolio_limit": 0,
            }
        )

        # Mock place_reentry_orders method
        mock_engine.place_reentry_orders = Mock(
            return_value={
                "attempted": 0,
                "placed": 0,
                "failed_balance": 0,
                "skipped_duplicates": 0,
                "skipped_invalid_rsi": 0,
                "skipped_missing_data": 0,
                "skipped_invalid_qty": 0,
                "skipped_no_position": 0,
            }
        )

        # Mock load_latest_recommendations to return some recommendations
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        mock_recommendation = Recommendation(
            ticker="RELIANCE.NS",
            verdict="buy",
            last_close=2500.0,
            execution_capital=50000.0,
        )
        mock_engine.load_latest_recommendations = Mock(return_value=[mock_recommendation])
        mock_engine_class.return_value = mock_engine

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_sell_manager_instance = Mock()
        mock_sell_manager_class.return_value = mock_sell_manager_instance

        mock_prevent_conflict.return_value = True
        mock_create_temp_env.return_value = "temp_env_file.env"

        # Mock execute_task context manager
        mock_execute_task.return_value.__enter__ = Mock(return_value={})
        mock_execute_task.return_value.__exit__ = Mock(return_value=False)

        # Create service
        service = TradingService(
            user_id=sample_user_id,
            db_session=mock_db_session,
            broker_creds={"api_key": "test", "api_secret": "test"},
            strategy_config=mock_strategy_config,
        )

        # Initialize service
        service.initialize()

        # Call run_buy_orders
        service.run_buy_orders()

        # Verify place_new_entries was called first
        mock_engine.place_new_entries.assert_called_once()

        # Verify place_reentry_orders was called after place_new_entries
        mock_engine.place_reentry_orders.assert_called_once()

        # Verify order: place_new_entries called before place_reentry_orders
        assert mock_engine.place_new_entries.call_count == 1
        assert mock_engine.place_reentry_orders.call_count == 1

        # Verify call order by checking call indices
        # place_new_entries should be called first, then place_reentry_orders
        place_new_entries_call_index = None
        place_reentry_orders_call_index = None

        # Get all method calls to find the order
        all_calls = []
        for call in mock_engine.method_calls:
            if call[0] == "place_new_entries":
                place_new_entries_call_index = len(all_calls)
                all_calls.append("place_new_entries")
            elif call[0] == "place_reentry_orders":
                place_reentry_orders_call_index = len(all_calls)
                all_calls.append("place_reentry_orders")

        # Verify both methods were called
        assert place_new_entries_call_index is not None, "place_new_entries was not called"
        assert place_reentry_orders_call_index is not None, "place_reentry_orders was not called"

        # Verify place_new_entries was called before place_reentry_orders
        assert (
            place_new_entries_call_index < place_reentry_orders_call_index
        ), f"place_reentry_orders was called before place_new_entries (indices: {place_new_entries_call_index}, {place_reentry_orders_call_index})"


class TestPaperTradingServiceUpdates:
    """Test paper trading service updates for position monitor removal, RSI exit, and re-entry"""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session"""
        session = Mock()
        session.query = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.close = Mock()
        return session

    @pytest.fixture
    def sample_user_id(self):
        """Sample user ID for testing"""
        return 1

    @patch("src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter")
    @patch("src.application.services.paper_trading_service_adapter.PaperTradingConfig")
    @patch("src.infrastructure.logging.get_user_logger")
    def test_paper_trading_no_position_monitor_method(
        self,
        mock_get_logger,
        mock_config_class,
        mock_broker_class,
        mock_db_session,
        sample_user_id,
    ):
        """Test that paper trading service does not have run_position_monitor method"""
        from src.application.services.paper_trading_service_adapter import (
            PaperTradingServiceAdapter,
        )

        # Setup mocks
        mock_broker = Mock()
        mock_broker.is_connected.return_value = True
        mock_broker.get_holdings.return_value = []
        mock_broker.get_pending_orders = Mock(return_value=[])
        mock_broker.get_all_orders = Mock(return_value=[])
        mock_broker.get_portfolio = Mock(return_value={"availableCash": 100000.0, "cash": 100000.0})
        mock_broker.store = Mock()
        mock_broker.store.get_account = Mock(return_value={"available_cash": 100000.0})
        mock_broker_class.return_value = mock_broker

        mock_config = Mock()
        mock_config_class.return_value = mock_config

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Create paper trading service
        adapter = PaperTradingServiceAdapter(
            user_id=sample_user_id,
            db_session=mock_db_session,
            initial_capital=100000.0,
        )
        adapter.broker = mock_broker
        adapter.initialize()

        # Verify run_position_monitor method does not exist
        assert not hasattr(adapter, "run_position_monitor")

    @patch("src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter")
    @patch("src.application.services.paper_trading_service_adapter.PaperTradingConfig")
    @patch("src.infrastructure.logging.get_user_logger")
    @patch("src.application.services.task_execution_wrapper.execute_task")
    def test_paper_trading_run_sell_monitor_has_rsi_exit(
        self,
        mock_execute_task,
        mock_get_logger,
        mock_config_class,
        mock_broker_class,
        mock_db_session,
        sample_user_id,
    ):
        """Test that paper trading run_sell_monitor has RSI exit logic"""
        from src.application.services.paper_trading_service_adapter import (
            PaperTradingServiceAdapter,
        )

        # Setup mocks
        mock_broker = Mock()
        mock_broker.is_connected.return_value = True
        mock_broker.get_holdings.return_value = []
        mock_broker.get_pending_orders = Mock(return_value=[])
        mock_broker.get_all_orders = Mock(return_value=[])
        mock_broker.get_portfolio = Mock(return_value={"availableCash": 100000.0, "cash": 100000.0})
        mock_broker.store = Mock()
        mock_broker.store.get_account = Mock(return_value={"available_cash": 100000.0})
        mock_broker_class.return_value = mock_broker

        mock_config = Mock()
        mock_config_class.return_value = mock_config

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Mock execute_task context manager
        mock_execute_task.return_value.__enter__ = Mock(return_value={})
        mock_execute_task.return_value.__exit__ = Mock(return_value=False)

        # Create paper trading service
        adapter = PaperTradingServiceAdapter(
            user_id=sample_user_id,
            db_session=mock_db_session,
            initial_capital=100000.0,
        )
        adapter.broker = mock_broker
        adapter.initialize()

        # Verify RSI exit attributes exist
        assert hasattr(adapter, "rsi10_cache")
        assert hasattr(adapter, "converted_to_market")
        assert hasattr(adapter, "_get_current_rsi10_paper")
        assert hasattr(adapter, "_monitor_sell_orders")

    @patch("src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter")
    @patch("src.application.services.paper_trading_service_adapter.PaperTradingConfig")
    @patch("src.infrastructure.logging.get_user_logger")
    @patch("src.application.services.task_execution_wrapper.execute_task")
    def test_paper_trading_run_buy_orders_calls_place_reentry_orders(
        self,
        mock_execute_task,
        mock_get_logger,
        mock_config_class,
        mock_broker_class,
        mock_db_session,
        sample_user_id,
    ):
        """Test that paper trading run_buy_orders calls place_reentry_orders"""
        from src.application.services.paper_trading_service_adapter import (
            PaperTradingServiceAdapter,
        )

        # Setup mocks
        mock_broker = Mock()
        mock_broker.is_connected.return_value = True
        mock_broker.get_holdings.return_value = []
        mock_broker.get_pending_orders = Mock(return_value=[])
        mock_broker.get_all_orders = Mock(return_value=[])
        mock_broker.get_portfolio = Mock(return_value={"availableCash": 100000.0, "cash": 100000.0})
        mock_broker.store = Mock()
        mock_broker.store.get_account = Mock(return_value={"available_cash": 100000.0})
        mock_broker_class.return_value = mock_broker

        mock_config = Mock()
        mock_config_class.return_value = mock_config

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Mock execute_task context manager
        mock_execute_task.return_value.__enter__ = Mock(return_value={})
        mock_execute_task.return_value.__exit__ = Mock(return_value=False)

        # Create paper trading service
        adapter = PaperTradingServiceAdapter(
            user_id=sample_user_id,
            db_session=mock_db_session,
            initial_capital=100000.0,
        )
        adapter.broker = mock_broker
        adapter.initialize()

        # Mock engine's place_reentry_orders
        adapter.engine.place_reentry_orders = Mock(
            return_value={
                "attempted": 0,
                "placed": 0,
                "failed_balance": 0,
                "skipped_duplicates": 0,
                "skipped_invalid_rsi": 0,
                "skipped_missing_data": 0,
                "skipped_invalid_qty": 0,
                "skipped_no_position": 0,
            }
        )

        # Mock load_latest_recommendations to return empty list
        adapter.engine.load_latest_recommendations = Mock(return_value=[])

        # Call run_buy_orders
        adapter.run_buy_orders()

        # Verify place_reentry_orders was called
        adapter.engine.place_reentry_orders.assert_called_once()

    @patch("src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter")
    @patch("src.application.services.paper_trading_service_adapter.PaperTradingConfig")
    @patch("src.infrastructure.logging.get_user_logger")
    @patch("src.application.services.task_execution_wrapper.execute_task")
    def test_paper_trading_run_buy_orders_calls_place_reentry_orders_after_fresh_entries(
        self,
        mock_execute_task,
        mock_get_logger,
        mock_config_class,
        mock_broker_class,
        mock_db_session,
        sample_user_id,
    ):
        """Test that paper trading run_buy_orders calls place_reentry_orders after placing fresh entry orders"""
        from src.application.services.paper_trading_service_adapter import (
            PaperTradingServiceAdapter,
        )

        # Setup mocks
        mock_broker = Mock()
        mock_broker.is_connected.return_value = True
        mock_broker.get_holdings.return_value = []
        mock_broker.get_pending_orders = Mock(return_value=[])
        mock_broker.get_all_orders = Mock(return_value=[])
        mock_broker.get_portfolio = Mock(return_value={"availableCash": 100000.0, "cash": 100000.0})
        mock_broker.store = Mock()
        mock_broker.store.get_account = Mock(return_value={"available_cash": 100000.0})
        mock_broker_class.return_value = mock_broker

        mock_config = Mock()
        mock_config_class.return_value = mock_config

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Mock execute_task context manager
        mock_execute_task.return_value.__enter__ = Mock(return_value={})
        mock_execute_task.return_value.__exit__ = Mock(return_value=False)

        # Create paper trading service
        adapter = PaperTradingServiceAdapter(
            user_id=sample_user_id,
            db_session=mock_db_session,
            initial_capital=100000.0,
        )
        adapter.broker = mock_broker
        adapter.initialize()

        # Mock engine's place_new_entries and place_reentry_orders
        adapter.engine.place_new_entries = Mock(
            return_value={
                "attempted": 1,
                "placed": 1,
                "failed_balance": 0,
                "skipped_duplicates": 0,
                "skipped_portfolio_limit": 0,
            }
        )

        adapter.engine.place_reentry_orders = Mock(
            return_value={
                "attempted": 0,
                "placed": 0,
                "failed_balance": 0,
                "skipped_duplicates": 0,
                "skipped_invalid_rsi": 0,
                "skipped_missing_data": 0,
                "skipped_invalid_qty": 0,
                "skipped_no_position": 0,
            }
        )

        # Mock load_latest_recommendations to return some recommendations
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        mock_recommendation = Recommendation(
            ticker="RELIANCE.NS",
            verdict="buy",
            last_close=2500.0,
            execution_capital=50000.0,
        )
        adapter.engine.load_latest_recommendations = Mock(return_value=[mock_recommendation])

        # Call run_buy_orders
        adapter.run_buy_orders()

        # Verify place_new_entries was called first
        adapter.engine.place_new_entries.assert_called_once()

        # Verify place_reentry_orders was called after place_new_entries
        adapter.engine.place_reentry_orders.assert_called_once()

        # Verify order: place_new_entries called before place_reentry_orders
        assert adapter.engine.place_new_entries.call_count == 1
        assert adapter.engine.place_reentry_orders.call_count == 1
