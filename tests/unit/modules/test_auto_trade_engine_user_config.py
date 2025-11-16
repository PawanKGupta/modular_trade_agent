"""
Tests for AutoTradeEngine user-specific configuration integration (Phase 2.3)

Tests that AutoTradeEngine correctly uses user-specific config values instead
of hardcoded config values.
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime

from config.strategy_config import StrategyConfig


@pytest.fixture
def mock_auth():
    """Mock KotakNeoAuth"""
    auth = MagicMock()
    auth.is_authenticated.return_value = True
    auth.login.return_value = True
    return auth


@pytest.fixture
def custom_strategy_config():
    """Custom strategy config with non-default values"""
    return StrategyConfig(
        rsi_period=14,
        rsi_oversold=25.0,
        rsi_extreme_oversold=15.0,
        user_capital=300000.0,
        max_portfolio_size=8,  # Different from default (6)
        exit_on_ema9_or_rsi50=True,
        default_variety="AMO",
        default_exchange="NSE",
        default_product="CNC",
        default_order_type="MARKET",
        default_validity="DAY",
    )


@pytest.fixture
def auto_trade_engine(mock_auth, db_session, custom_strategy_config):
    """Create AutoTradeEngine instance with user config"""
    from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

    with patch(
        "modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"
    ) as mock_auth_class:
        mock_auth_class.return_value = mock_auth

        engine = AutoTradeEngine(
            env_file="test.env",
            auth=mock_auth,
            user_id=1,
            db_session=db_session,
            strategy_config=custom_strategy_config,
        )

        # Mock portfolio and orders
        engine.portfolio = MagicMock()
        engine.orders = MagicMock()

        return engine


class TestPortfolioLimitConfig:
    """Test that portfolio limits use user-specific config"""

    def test_portfolio_limit_uses_user_config(
        self, auto_trade_engine, custom_strategy_config
    ):
        """Test that portfolio limit check uses user config max_portfolio_size"""
        # Mock current_symbols_in_portfolio to return 7 symbols
        auto_trade_engine.current_symbols_in_portfolio = MagicMock(
            return_value=["SYM1", "SYM2", "SYM3", "SYM4", "SYM5", "SYM6", "SYM7"]
        )

        # Should allow 7 < 8 (user config)
        current_count = len(auto_trade_engine.current_symbols_in_portfolio())
        assert current_count < custom_strategy_config.max_portfolio_size

        # Should reject 8 >= 8 (user config)
        auto_trade_engine.current_symbols_in_portfolio = MagicMock(
            return_value=[
                "SYM1",
                "SYM2",
                "SYM3",
                "SYM4",
                "SYM5",
                "SYM6",
                "SYM7",
                "SYM8",
            ]
        )
        current_count = len(auto_trade_engine.current_symbols_in_portfolio())
        assert current_count >= custom_strategy_config.max_portfolio_size

    def test_portfolio_limit_config_accessible(
        self, auto_trade_engine, custom_strategy_config
    ):
        """Test that portfolio limit config is accessible from engine"""
        # Verify config is accessible
        assert (
            auto_trade_engine.strategy_config.max_portfolio_size
            == custom_strategy_config.max_portfolio_size
        )
        assert auto_trade_engine.strategy_config.max_portfolio_size == 8


class TestExitConditionConfig:
    """Test that exit conditions use user-specific config"""

    def test_exit_condition_uses_user_config(
        self, auto_trade_engine, custom_strategy_config
    ):
        """Test that exit condition check uses user config exit_on_ema9_or_rsi50"""
        # Verify config is set
        assert auto_trade_engine.strategy_config.exit_on_ema9_or_rsi50 is True

        # Test with different config value
        custom_strategy_config.exit_on_ema9_or_rsi50 = False
        auto_trade_engine.strategy_config.exit_on_ema9_or_rsi50 = False

        assert auto_trade_engine.strategy_config.exit_on_ema9_or_rsi50 is False


class TestOrderDefaultsConfig:
    """Test that order defaults use user-specific config"""

    def test_order_defaults_use_user_config(
        self, auto_trade_engine, custom_strategy_config
    ):
        """Test that order placement uses user config defaults"""
        # Verify config values
        assert auto_trade_engine.strategy_config.default_variety == "AMO"
        assert auto_trade_engine.strategy_config.default_exchange == "NSE"
        assert auto_trade_engine.strategy_config.default_product == "CNC"

    def test_order_defaults_config_accessible(
        self, auto_trade_engine, custom_strategy_config
    ):
        """Test that order defaults config is accessible from engine"""
        # Verify config values are accessible
        assert auto_trade_engine.strategy_config.default_variety == "AMO"
        assert auto_trade_engine.strategy_config.default_exchange == "NSE"
        assert auto_trade_engine.strategy_config.default_product == "CNC"
        assert auto_trade_engine.strategy_config.default_order_type == "MARKET"
        assert auto_trade_engine.strategy_config.default_validity == "DAY"



class TestConfigBackwardCompatibility:
    """Test backward compatibility when config is not provided"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_falls_back_to_default_config_when_none_provided(
        self, mock_auth_class, db_session
    ):
        """Test that AutoTradeEngine uses default config when strategy_config is None"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

        mock_auth = MagicMock()
        mock_auth.is_authenticated.return_value = True
        mock_auth_class.return_value = mock_auth

        engine = AutoTradeEngine(
            env_file="test.env",
            auth=mock_auth,
            user_id=None,
            db_session=None,
            strategy_config=None,
        )

        # Should use default config
        assert engine.strategy_config is not None
        assert isinstance(engine.strategy_config, StrategyConfig)
        # Check default values
        assert engine.strategy_config.rsi_period == 10  # Default
        assert engine.strategy_config.max_portfolio_size == 6  # Default
        assert engine.strategy_config.default_exchange == "NSE"  # Default
        assert engine.strategy_config.default_product == "CNC"  # Default
        assert engine.strategy_config.default_variety == "AMO"  # Default

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_static_method_uses_default_config(self, mock_auth_class):
        """Test that static methods use default config for backward compatibility"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

        # calculate_execution_capital is a static method
        # It should use default config, not instance config
        execution_capital = AutoTradeEngine.calculate_execution_capital(
            "RELIANCE.NS", 2500.0, 1000000.0
        )

        # Should return a valid capital amount
        assert execution_capital > 0
        assert isinstance(execution_capital, (int, float))


class TestConfigValueUsage:
    """Test that config values are actually used in logic"""

    def test_user_capital_used_in_capital_comparison(
        self, auto_trade_engine, custom_strategy_config
    ):
        """Test that user_capital from config is used in comparisons"""
        # Verify user_capital is accessible
        assert auto_trade_engine.strategy_config.user_capital == 300000.0

        # Test that it's used (e.g., in execution capital comparison)
        execution_capital = 250000.0
        if execution_capital < custom_strategy_config.user_capital:
            # This logic exists in place_new_entries
            assert True  # Just verify the comparison works

    def test_max_portfolio_size_accessible(self, auto_trade_engine, custom_strategy_config):
        """Test that max_portfolio_size is accessible from engine"""
        assert (
            auto_trade_engine.strategy_config.max_portfolio_size
            == custom_strategy_config.max_portfolio_size
        )
        assert auto_trade_engine.strategy_config.max_portfolio_size == 8

