"""Tests for ML configuration respect in integrated_backtest.py"""

from unittest.mock import MagicMock, patch

import pytest

from config.strategy_config import StrategyConfig
from integrated_backtest import validate_initial_entry_with_trade_agent


class TestIntegratedBacktestMLConfig:
    """Test that integrated_backtest respects ML configuration"""

    @pytest.fixture
    def mock_market_data(self):
        """Create mock market data DataFrame"""
        import pandas as pd

        return pd.DataFrame(
            {
                "Open": [100, 101, 102],
                "High": [105, 106, 107],
                "Low": [99, 100, 101],
                "Close": [104, 105, 106],
                "Volume": [1000000, 1100000, 1200000],
            }
        )

    @pytest.fixture
    def ml_enabled_config(self):
        """Create config with ML enabled"""
        config = StrategyConfig.default()
        config.ml_enabled = True
        config.ml_confidence_threshold = 0.6
        config.ml_combine_with_rules = True
        return config

    @pytest.fixture
    def ml_disabled_config(self):
        """Create config with ML disabled"""
        config = StrategyConfig.default()
        config.ml_enabled = False
        return config

    def test_validate_initial_entry_uses_provided_config(self, mock_market_data, ml_enabled_config):
        """Test that validate_initial_entry_with_trade_agent uses provided config"""
        with patch("services.analysis_service.AnalysisService") as mock_analysis_service:
            mock_service_instance = MagicMock()
            mock_service_instance.analyze_ticker.return_value = {
                "status": "success",
                "verdict": "buy",
                "target": 110.0,
            }
            mock_analysis_service.return_value = mock_service_instance

            result = validate_initial_entry_with_trade_agent(
                stock_name="TEST.NS",
                signal_date="2024-01-01",
                rsi=25.0,
                ema200=100.0,
                full_market_data=mock_market_data,
                config=ml_enabled_config,
            )

            # Verify AnalysisService was created with the provided config
            mock_analysis_service.assert_called_once()
            call_config = mock_analysis_service.call_args[1]["config"]
            assert call_config.ml_enabled is True, "Should use provided config with ML enabled"

    def test_validate_initial_entry_loads_config_from_env_when_none(
        self, mock_market_data, ml_enabled_config
    ):
        """Test that validate_initial_entry_with_trade_agent loads config from environment when config is None"""
        with (
            patch("services.analysis_service.AnalysisService") as mock_analysis_service,
            patch("integrated_backtest.os.environ.get") as mock_env_get,
            patch("src.infrastructure.db.session.get_session") as mock_get_session,
            patch(
                "src.infrastructure.persistence.user_trading_config_repository.UserTradingConfigRepository"
            ) as mock_repo_class,
            patch(
                "src.application.services.config_converter.user_config_to_strategy_config"
            ) as mock_converter,
        ):
            # Setup environment variable
            mock_env_get.return_value = "123"

            # Setup database mocks
            mock_db_session = MagicMock()
            mock_get_session.return_value = iter([mock_db_session])

            mock_repo = MagicMock()
            mock_user_config = MagicMock()
            mock_user_config.ml_enabled = True
            mock_repo.get_or_create_default.return_value = mock_user_config
            mock_repo_class.return_value = mock_repo

            mock_converter.return_value = ml_enabled_config

            mock_service_instance = MagicMock()
            mock_service_instance.analyze_ticker.return_value = {
                "status": "success",
                "verdict": "buy",
                "target": 110.0,
            }
            mock_analysis_service.return_value = mock_service_instance

            result = validate_initial_entry_with_trade_agent(
                stock_name="TEST.NS",
                signal_date="2024-01-01",
                rsi=25.0,
                ema200=100.0,
                full_market_data=mock_market_data,
                config=None,  # No config provided
            )

            # Verify environment variable was checked
            mock_env_get.assert_called_with("TRADE_AGENT_USER_ID")

            # Verify config was loaded from database
            mock_repo.get_or_create_default.assert_called_once_with(123)
            mock_converter.assert_called_once_with(mock_user_config, db_session=mock_db_session)

            # Verify AnalysisService was created with loaded config
            mock_analysis_service.assert_called_once()
            call_config = mock_analysis_service.call_args[1]["config"]
            assert call_config.ml_enabled is True, "Should load user config with ML enabled"

    def test_validate_initial_entry_defaults_when_no_env_var(self, mock_market_data):
        """Test that validate_initial_entry_with_trade_agent uses default config when no env var and no config"""
        with (
            patch("services.analysis_service.AnalysisService") as mock_analysis_service,
            patch("integrated_backtest.os.environ.get") as mock_env_get,
        ):
            # No environment variable
            mock_env_get.return_value = None

            mock_service_instance = MagicMock()
            mock_service_instance.analyze_ticker.return_value = {
                "status": "success",
                "verdict": "buy",
                "target": 110.0,
            }
            mock_analysis_service.return_value = mock_service_instance

            result = validate_initial_entry_with_trade_agent(
                stock_name="TEST.NS",
                signal_date="2024-01-01",
                rsi=25.0,
                ema200=100.0,
                full_market_data=mock_market_data,
                config=None,  # No config provided
            )

            # Verify AnalysisService was created with default config
            mock_analysis_service.assert_called_once()
            call_config = mock_analysis_service.call_args[1]["config"]
            assert call_config.ml_enabled is False, "Should use default config (ML disabled)"

    def test_validate_initial_entry_logs_config_usage(
        self, mock_market_data, ml_enabled_config, caplog
    ):
        """Test that validate_initial_entry_with_trade_agent logs config usage"""
        with patch("services.analysis_service.AnalysisService") as mock_analysis_service:
            mock_service_instance = MagicMock()
            mock_service_instance.analyze_ticker.return_value = {
                "status": "success",
                "verdict": "buy",
                "target": 110.0,
            }
            mock_analysis_service.return_value = mock_service_instance

            with caplog.at_level("DEBUG"):
                validate_initial_entry_with_trade_agent(
                    stock_name="TEST.NS",
                    signal_date="2024-01-01",
                    rsi=25.0,
                    ema200=100.0,
                    full_market_data=mock_market_data,
                    config=ml_enabled_config,
                )

            # Check that config usage was logged
            assert any(
                "using provided config" in record.message and "ml_enabled=True" in record.message
                for record in caplog.records
            ), "Should log config usage"
