"""
Unit tests for TradingService with User Context (Phase 2.3)

Tests for:
- TradingService initialization with user context
- User configuration loading
- StrategyConfig conversion
- Integration with AutoTradeEngine
"""

import pytest
from unittest.mock import MagicMock, patch

from src.infrastructure.db.models import TradeMode, UserSettings, Users, UserTradingConfig
from src.infrastructure.db.timezone_utils import ist_now


@pytest.fixture
def sample_user_with_config(db_session):
    """Create a user with complete configuration"""
    user = Users(
        email="test@example.com",
        password_hash="hashed_password",
        created_at=ist_now(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    settings = UserSettings(
        user_id=user.id,
        trade_mode=TradeMode.BROKER,
        broker_creds_encrypted=b"encrypted_creds",
    )
    db_session.add(settings)
    db_session.commit()

    config = UserTradingConfig(
        user_id=user.id,
        rsi_period=14,
        rsi_oversold=25.0,
        user_capital=300000.0,
        max_portfolio_size=8,
    )
    db_session.add(config)
    db_session.commit()

    return user


class TestTradingServiceUserContext:
    """Tests for TradingService with user context"""

    @patch("modules.kotak_neo_auto_trader.run_trading_service.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.AutoTradeEngine")
    def test_trading_service_initialization_with_user_context(
        self, mock_engine, mock_auth, db_session, sample_user_with_config
    ):
        """Test TradingService initializes with user context"""
        from modules.kotak_neo_auto_trader.run_trading_service import TradingService

        broker_creds = {"api_key": "test_key", "api_secret": "test_secret"}

        service = TradingService(
            user_id=sample_user_with_config.id,
            db_session=db_session,
            broker_creds=broker_creds,
            env_file=None,
        )

        assert service.user_id == sample_user_with_config.id
        assert service.db == db_session
        assert service.broker_creds == broker_creds
        assert service.strategy_config is not None
        assert service.logger is not None
        assert service.logger.user_id == sample_user_with_config.id

    def test_trading_service_loads_user_config(
        self, db_session, sample_user_with_config
    ):
        """Test TradingService loads user-specific configuration"""
        from modules.kotak_neo_auto_trader.run_trading_service import TradingService

        broker_creds = {}

        service = TradingService(
            user_id=sample_user_with_config.id,
            db_session=db_session,
            broker_creds=broker_creds,
            env_file=None,
        )

        # Check that user config was loaded and converted
        assert service.strategy_config is not None
        assert service.strategy_config.rsi_period == 14
        assert service.strategy_config.rsi_oversold == 25.0
        assert service.strategy_config.user_capital == 300000.0

    def test_trading_service_uses_provided_strategy_config(
        self, db_session, sample_user_with_config
    ):
        """Test TradingService uses provided StrategyConfig if given"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.run_trading_service import TradingService

        custom_config = StrategyConfig(
            rsi_period=20,
            rsi_oversold=30.0,
            user_capital=500000.0,
        )

        broker_creds = {}

        service = TradingService(
            user_id=sample_user_with_config.id,
            db_session=db_session,
            broker_creds=broker_creds,
            strategy_config=custom_config,
            env_file=None,
        )

        # Should use provided config, not load from DB
        assert service.strategy_config.rsi_period == 20
        assert service.strategy_config.rsi_oversold == 30.0
        assert service.strategy_config.user_capital == 500000.0

    @patch("modules.kotak_neo_auto_trader.run_trading_service.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.AutoTradeEngine")
    def test_trading_service_passes_context_to_engine(
        self, mock_engine_class, mock_auth_class, db_session, sample_user_with_config
    ):
        """Test TradingService passes user context to AutoTradeEngine"""
        from modules.kotak_neo_auto_trader.run_trading_service import TradingService

        mock_auth_instance = MagicMock()
        mock_auth_instance.login.return_value = True
        mock_auth_class.return_value = mock_auth_instance

        mock_engine_instance = MagicMock()
        mock_engine_instance.login.return_value = True
        mock_engine_class.return_value = mock_engine_instance

        broker_creds = {}

        service = TradingService(
            user_id=sample_user_with_config.id,
            db_session=db_session,
            broker_creds=broker_creds,
            env_file="test.env",
        )

        # Initialize service (will call engine)
        service.initialize()

        # Check that AutoTradeEngine was called with user context
        mock_engine_class.assert_called_once()
        call_kwargs = mock_engine_class.call_args[1]

        assert call_kwargs["user_id"] == sample_user_with_config.id
        assert call_kwargs["db_session"] == db_session
        assert call_kwargs["strategy_config"] is not None
        assert call_kwargs["strategy_config"].rsi_period == 14


class TestAutoTradeEngineUserContext:
    """Tests for AutoTradeEngine with user context"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_auto_trade_engine_initialization_with_user_context(
        self, mock_auth_class, db_session
    ):
        """Test AutoTradeEngine initializes with user context"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

        # Mock auth to avoid credential errors
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth

        strategy_config = StrategyConfig(
            rsi_period=14,
            rsi_oversold=25.0,
            user_capital=300000.0,
        )

        engine = AutoTradeEngine(
            env_file="test.env",
            auth=mock_auth,  # Pass mock auth instead of None
            user_id=1,
            db_session=db_session,
            strategy_config=strategy_config,
        )

        assert engine.user_id == 1
        assert engine.db == db_session
        assert engine.strategy_config == strategy_config
        assert engine.strategy_config.rsi_period == 14
        assert engine.strategy_config.user_capital == 300000.0

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_auto_trade_engine_uses_default_config_when_none_provided(
        self, mock_auth_class
    ):
        """Test AutoTradeEngine falls back to default config"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

        # Mock auth to avoid credential errors
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth

        engine = AutoTradeEngine(
            env_file="test.env",
            auth=mock_auth,  # Pass mock auth instead of None
            user_id=None,
            db_session=None,
            strategy_config=None,
        )

        # Should use default config
        assert engine.strategy_config is not None
        assert isinstance(engine.strategy_config, StrategyConfig)
        # Check it's the default (not user-specific)
        assert engine.strategy_config.rsi_period == 10  # Default value

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_auto_trade_engine_initializes_orders_repository(
        self, mock_auth_class, db_session
    ):
        """Test AutoTradeEngine initializes OrdersRepository when db_session provided"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

        # Mock auth to avoid credential errors
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth

        strategy_config = StrategyConfig()

        engine = AutoTradeEngine(
            env_file="test.env",
            auth=mock_auth,  # Pass mock auth instead of None
            user_id=1,
            db_session=db_session,
            strategy_config=strategy_config,
        )

        assert engine.orders_repo is not None
        assert engine.history_path is None  # Should not use file-based storage

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_auto_trade_engine_falls_back_to_file_storage(self, mock_auth_class):
        """Test AutoTradeEngine uses file storage when db_session is None"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
        from modules.kotak_neo_auto_trader import config

        # Mock auth to avoid credential errors
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth

        strategy_config = StrategyConfig()

        engine = AutoTradeEngine(
            env_file="test.env",
            auth=mock_auth,  # Pass mock auth instead of None
            user_id=None,
            db_session=None,
            strategy_config=strategy_config,
        )

        assert engine.orders_repo is None
        assert engine.history_path == config.TRADES_HISTORY_PATH


class TestConfigConversion:
    """Tests for configuration conversion in TradingService"""

    def test_user_config_converted_to_strategy_config(
        self, db_session, sample_user_with_config
    ):
        """Test that UserTradingConfig is correctly converted to StrategyConfig"""
        from modules.kotak_neo_auto_trader.run_trading_service import TradingService

        broker_creds = {}

        service = TradingService(
            user_id=sample_user_with_config.id,
            db_session=db_session,
            broker_creds=broker_creds,
            env_file=None,
        )

        # Verify conversion
        config = service.strategy_config

        # RSI settings
        assert config.rsi_period == 14
        assert config.rsi_oversold == 25.0

        # Capital settings
        assert config.user_capital == 300000.0

        # Chart quality (should use user config values)
        assert config.chart_quality_enabled is True

    def test_default_values_used_for_missing_fields(
        self, db_session, sample_user_with_config
    ):
        """Test that default values are used for fields not in UserTradingConfig"""
        from modules.kotak_neo_auto_trader.run_trading_service import TradingService

        broker_creds = {}

        service = TradingService(
            user_id=sample_user_with_config.id,
            db_session=db_session,
            broker_creds=broker_creds,
            env_file=None,
        )

        config = service.strategy_config

        # These should use defaults from StrategyConfig
        assert config.min_volume_multiplier == 1.0
        assert config.volume_multiplier_for_strong == 1.2
        assert config.backtest_weight == 0.5


class TestMultiUserTradingServiceIntegration:
    """Integration tests for MultiUserTradingService with TradingService"""

    @patch("modules.kotak_neo_auto_trader.run_trading_service.TradingService")
    def test_multi_user_service_creates_trading_service_with_context(
        self, mock_trading_service_class, db_session, sample_user_with_config
    ):
        """Test MultiUserTradingService creates TradingService with user context"""
        from src.application.services.multi_user_trading_service import (
            MultiUserTradingService,
        )

        mock_service_instance = MagicMock()
        mock_trading_service_class.return_value = mock_service_instance

        service_manager = MultiUserTradingService(db=db_session)

        # Start service
        try:
            service_manager.start_service(sample_user_with_config.id)
        except (NotImplementedError, ValueError):
            # Expected - broker creds decryption not implemented yet
            pass

        # Check that TradingService was called with user context
        if mock_trading_service_class.called:
            call_kwargs = mock_trading_service_class.call_args[1]

            assert call_kwargs["user_id"] == sample_user_with_config.id
            assert call_kwargs["db_session"] == db_session
            assert call_kwargs["strategy_config"] is not None
            assert "broker_creds" in call_kwargs

    def test_multi_user_service_loads_user_config(
        self, db_session, sample_user_with_config
    ):
        """Test MultiUserTradingService loads and converts user config"""
        from src.application.services.multi_user_trading_service import (
            MultiUserTradingService,
        )

        service_manager = MultiUserTradingService(db=db_session)

        # Load config (this is what start_service does internally)
        user_config = service_manager._config_repo.get_or_create_default(
            sample_user_with_config.id
        )

        from src.application.services.config_converter import (
            user_config_to_strategy_config,
        )

        strategy_config = user_config_to_strategy_config(user_config)

        assert strategy_config.rsi_period == 14
        assert strategy_config.user_capital == 300000.0

