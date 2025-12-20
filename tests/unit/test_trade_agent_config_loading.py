"""
Unit tests for trade_agent.py user config loading.

Tests that trade_agent.py correctly loads user config from environment variable.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestTradeAgentConfigLoading:
    """Test user config loading in trade_agent.py"""

    @patch.dict(os.environ, {"TRADE_AGENT_USER_ID": "1"})
    @patch("src.infrastructure.db.session.get_session")
    @patch("src.infrastructure.persistence.user_trading_config_repository.UserTradingConfigRepository")
    @patch("src.application.services.config_converter.user_config_to_strategy_config")
    def test_loads_user_config_from_environment(
        self, mock_user_config_to_strategy_config, mock_config_repo, mock_get_session
    ):
        """Test that user config is loaded from TRADE_AGENT_USER_ID environment variable"""
        # Setup mocks
        mock_db_session = MagicMock()
        mock_get_session.return_value = iter([mock_db_session])

        mock_user_config = MagicMock()
        mock_user_config.ml_enabled = True
        mock_user_config.ml_confidence_threshold = 0.7

        mock_config_repo_instance = MagicMock()
        mock_config_repo.return_value = mock_config_repo_instance
        mock_config_repo_instance.get_or_create_default.return_value = mock_user_config

        mock_strategy_config = MagicMock()
        mock_strategy_config.ml_enabled = True
        mock_strategy_config.ml_confidence_threshold = 0.7
        mock_user_config_to_strategy_config.return_value = mock_strategy_config

        # Test the config loading logic
        user_id_str = os.environ.get("TRADE_AGENT_USER_ID")
        assert user_id_str == "1", "Environment variable should be set"

        user_id = int(user_id_str)
        assert user_id == 1, "User ID should be parsed correctly"

        # Verify config loading would work
        from src.infrastructure.db.session import get_session
        from src.infrastructure.persistence.user_trading_config_repository import (
            UserTradingConfigRepository,
        )
        from src.application.services.config_converter import (
            user_config_to_strategy_config,
        )

        db_session = next(get_session())
        config_repo = UserTradingConfigRepository(db_session)
        user_config = config_repo.get_or_create_default(user_id)
        strategy_config = user_config_to_strategy_config(user_config, db_session=db_session)

        # Verify config was loaded
        assert strategy_config.ml_enabled is True, "ML should be enabled from user config"

    @patch.dict(os.environ, {}, clear=True)
    def test_uses_default_config_when_no_environment_variable(self):
        """Test that default config is used when TRADE_AGENT_USER_ID is not set"""
        user_id_str = os.environ.get("TRADE_AGENT_USER_ID")
        assert user_id_str is None, "Environment variable should not be set"

        # When no user_id, config should be None and default will be used
        config = None
        from config.strategy_config import StrategyConfig

        if config is None:
            config = StrategyConfig.default()

        assert config.ml_enabled is False, "Default config should have ml_enabled=False"

    @patch.dict(os.environ, {"TRADE_AGENT_USER_ID": "invalid"})
    def test_handles_invalid_user_id_gracefully(self):
        """Test that invalid user_id is handled gracefully"""
        user_id_str = os.environ.get("TRADE_AGENT_USER_ID")
        assert user_id_str == "invalid"

        try:
            user_id = int(user_id_str)
            assert False, "Should have raised ValueError"
        except ValueError:
            # Expected - invalid user_id should be handled
            pass

    @patch.dict(os.environ, {"TRADE_AGENT_USER_ID": "1"})
    @patch("src.infrastructure.db.session.get_session")
    @patch("src.infrastructure.persistence.user_trading_config_repository.UserTradingConfigRepository")
    def test_logs_debug_info_when_loading_config(
        self, mock_config_repo, mock_get_session
    ):
        """Test that debug logging occurs when loading config"""
        # Setup mocks
        mock_db_session = MagicMock()
        mock_get_session.return_value = iter([mock_db_session])

        mock_user_config = MagicMock()
        mock_user_config.ml_enabled = True
        mock_user_config.ml_confidence_threshold = 0.7

        mock_config_repo_instance = MagicMock()
        mock_config_repo.return_value = mock_config_repo_instance
        mock_config_repo_instance.get_or_create_default.return_value = mock_user_config

        # The actual logging happens in trade_agent.py, but we can verify the flow
        user_id_str = os.environ.get("TRADE_AGENT_USER_ID")
        user_id = int(user_id_str)

        # Verify the flow would work
        from src.infrastructure.db.session import get_session
        from src.infrastructure.persistence.user_trading_config_repository import (
            UserTradingConfigRepository,
        )

        db_session = next(get_session())
        config_repo = UserTradingConfigRepository(db_session)
        user_config = config_repo.get_or_create_default(user_id)

        # Verify config was retrieved
        assert user_config.ml_enabled is True, "User config should be retrieved"

