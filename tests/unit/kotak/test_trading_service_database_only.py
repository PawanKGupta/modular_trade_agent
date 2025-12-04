"""
Unit tests for TradingService database-only position tracking

Tests verify that TradingService.initialize() passes database repositories
to SellOrderManager for database-only position tracking.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from modules.kotak_neo_auto_trader.run_trading_service import TradingService


class TestTradingServiceDatabaseOnlyInitialization:
    """Test TradingService initialization with database repositories"""

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
        config = MagicMock()
        return config

    @pytest.fixture
    def sample_user_id(self):
        """Sample user ID for testing"""
        return 2

    @patch("modules.kotak_neo_auto_trader.run_trading_service.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.AutoTradeEngine")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.SellOrderManager")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.prevent_service_conflict")
    @patch("src.application.services.broker_credentials.create_temp_env_file")
    @patch("src.infrastructure.logging.get_user_logger")
    def test_initialize_passes_positions_repo_to_sell_manager(  # noqa: PLR0913
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
        """Test that initialize() passes positions_repo to SellOrderManager"""
        # Setup mocks
        mock_auth = Mock()
        mock_auth.login.return_value = True  # Auth login succeeds
        mock_auth_class.return_value = mock_auth

        mock_engine = Mock()
        mock_engine.positions_repo = Mock()
        mock_engine.orders_repo = Mock()
        mock_engine.order_verifier = None
        mock_engine.login.return_value = True  # Engine login succeeds
        mock_engine_class.return_value = mock_engine

        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        mock_sell_manager_instance = Mock()
        mock_sell_manager_class.return_value = mock_sell_manager_instance

        # Mock dependencies
        mock_prevent_conflict.return_value = True  # No service conflicts
        mock_create_temp_env.return_value = "temp_env_file.env"  # Temp env file created

        # Create service
        service = TradingService(
            user_id=sample_user_id,
            db_session=mock_db_session,
            broker_creds={"api_key": "test", "api_secret": "test"},  # Provide broker_creds
            strategy_config=mock_strategy_config,
        )

        # Call initialize
        result = service.initialize()

        # Verify initialize succeeded
        assert result is True

        # Verify SellOrderManager was instantiated
        mock_sell_manager_class.assert_called_once()

        # Verify positions_repo was passed
        call_args = mock_sell_manager_class.call_args
        assert call_args[0][0] == mock_auth  # First positional arg is auth
        assert call_args[1]["positions_repo"] == mock_engine.positions_repo
        assert call_args[1]["user_id"] == sample_user_id
        assert call_args[1]["orders_repo"] == mock_engine.orders_repo

    @patch("modules.kotak_neo_auto_trader.run_trading_service.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.AutoTradeEngine")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.SellOrderManager")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.prevent_service_conflict")
    @patch("src.application.services.broker_credentials.create_temp_env_file")
    @patch("src.infrastructure.logging.get_user_logger")
    def test_initialize_passes_orders_repo_to_sell_manager(  # noqa: PLR0913
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
        """Test that initialize() passes orders_repo to SellOrderManager"""
        # Setup mocks
        mock_auth = Mock()
        mock_auth.login.return_value = True  # Auth login succeeds
        mock_auth_class.return_value = mock_auth

        mock_engine = Mock()
        mock_engine.positions_repo = Mock()
        mock_engine.orders_repo = Mock()
        mock_engine.order_verifier = None
        mock_engine.login.return_value = True  # Engine login succeeds
        mock_engine_class.return_value = mock_engine

        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        mock_sell_manager_instance = Mock()
        mock_sell_manager_class.return_value = mock_sell_manager_instance

        # Mock dependencies
        mock_prevent_conflict.return_value = True  # No service conflicts
        mock_create_temp_env.return_value = "temp_env_file.env"  # Temp env file created

        # Create service
        service = TradingService(
            user_id=sample_user_id,
            db_session=mock_db_session,
            broker_creds={"api_key": "test", "api_secret": "test"},  # Provide broker_creds
            strategy_config=mock_strategy_config,
        )

        # Call initialize
        result = service.initialize()

        # Verify initialize succeeded
        assert result is True

        # Verify orders_repo was passed
        call_args = mock_sell_manager_class.call_args
        assert call_args[1]["orders_repo"] == mock_engine.orders_repo

    @patch("modules.kotak_neo_auto_trader.run_trading_service.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.AutoTradeEngine")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.SellOrderManager")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.prevent_service_conflict")
    @patch("src.application.services.broker_credentials.create_temp_env_file")
    @patch("src.infrastructure.logging.get_user_logger")
    def test_initialize_handles_missing_positions_repo(  # noqa: PLR0913
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
        """Test that initialize() handles missing positions_repo gracefully"""
        # Setup mocks
        mock_auth = Mock()
        mock_auth.login.return_value = True  # Auth login succeeds
        mock_auth_class.return_value = mock_auth

        # Create mock engine without positions_repo attribute
        # Use spec to limit attributes, then add only what we need
        mock_engine = Mock(spec=['orders_repo', 'order_verifier', 'login', 'portfolio'])
        mock_engine.orders_repo = Mock()
        mock_engine.order_verifier = None
        mock_engine.login.return_value = True  # Engine login succeeds
        # positions_repo is NOT in spec, so hasattr will return False
        mock_engine_class.return_value = mock_engine

        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        mock_sell_manager_instance = Mock()
        mock_sell_manager_class.return_value = mock_sell_manager_instance

        # Mock dependencies
        mock_prevent_conflict.return_value = True  # No service conflicts
        mock_create_temp_env.return_value = "temp_env_file.env"  # Temp env file created

        # Create service
        service = TradingService(
            user_id=sample_user_id,
            db_session=mock_db_session,
            broker_creds={"api_key": "test", "api_secret": "test"},  # Provide broker_creds
            strategy_config=mock_strategy_config,
        )

        # Call initialize - should not raise, but should log warning
        result = service.initialize()

        # Verify initialize succeeded
        assert result is True

        # Verify SellOrderManager was still instantiated (with None positions_repo)
        mock_sell_manager_class.assert_called_once()

        # Verify positions_repo was None (because hasattr returns False)
        call_args = mock_sell_manager_class.call_args
        assert call_args[1]["positions_repo"] is None

        # Verify warning was logged
        mock_logger.error.assert_called()
        error_calls = [str(call) for call in mock_logger.error.call_args_list]
        assert any("PositionsRepository not available" in call for call in error_calls)

    @patch("modules.kotak_neo_auto_trader.run_trading_service.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.AutoTradeEngine")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.SellOrderManager")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.prevent_service_conflict")
    @patch("src.application.services.broker_credentials.create_temp_env_file")
    @patch("src.infrastructure.logging.get_user_logger")
    def test_initialize_passes_order_verifier_to_sell_manager(  # noqa: PLR0913
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
        """Test that initialize() passes order_verifier to SellOrderManager"""
        # Setup mocks
        mock_auth = Mock()
        mock_auth.login.return_value = True  # Auth login succeeds
        mock_auth_class.return_value = mock_auth

        mock_engine = Mock()
        mock_engine.positions_repo = Mock()
        mock_engine.orders_repo = Mock()
        mock_engine.order_verifier = Mock()  # Order verifier available
        mock_engine.login.return_value = True  # Engine login succeeds
        mock_engine_class.return_value = mock_engine

        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        mock_sell_manager_instance = Mock()
        mock_sell_manager_class.return_value = mock_sell_manager_instance

        # Mock dependencies
        mock_prevent_conflict.return_value = True  # No service conflicts
        mock_create_temp_env.return_value = "temp_env_file.env"  # Temp env file created

        # Create service
        service = TradingService(
            user_id=sample_user_id,
            db_session=mock_db_session,
            broker_creds={"api_key": "test", "api_secret": "test"},  # Provide broker_creds
            strategy_config=mock_strategy_config,
        )

        # Call initialize
        result = service.initialize()

        # Verify initialize succeeded
        assert result is True

        # Verify order_verifier was passed
        call_args = mock_sell_manager_class.call_args
        assert call_args[1]["order_verifier"] == mock_engine.order_verifier
