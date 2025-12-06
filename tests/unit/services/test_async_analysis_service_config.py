"""
Unit tests for AsyncAnalysisService config passing.

Tests that AsyncAnalysisService correctly uses the provided config.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from config.strategy_config import StrategyConfig
from services.async_analysis_service import AsyncAnalysisService


@pytest.fixture
def config_ml_enabled():
    """Create config with ML enabled"""
    return StrategyConfig(
        ml_enabled=True,
        ml_verdict_model_path="models/verdict_model_random_forest.pkl",
        ml_confidence_threshold=0.7,
        ml_combine_with_rules=True,
    )


@pytest.fixture
def config_ml_disabled():
    """Create config with ML disabled"""
    return StrategyConfig(
        ml_enabled=False,
        ml_verdict_model_path="models/verdict_model_random_forest.pkl",
        ml_confidence_threshold=0.5,
        ml_combine_with_rules=True,
    )


class TestAsyncAnalysisServiceConfig:
    """Test that AsyncAnalysisService uses provided config"""

    def test_uses_provided_config_ml_enabled(self, config_ml_enabled):
        """Test that AsyncAnalysisService uses provided config when ML is enabled"""
        service = AsyncAnalysisService(max_concurrent=5, config=config_ml_enabled)

        assert service.config == config_ml_enabled, "Service should use provided config"
        assert service.config.ml_enabled is True, "Config should have ml_enabled=True"
        assert service.analysis_service.config == config_ml_enabled, "AnalysisService should use same config"

    def test_uses_provided_config_ml_disabled(self, config_ml_disabled):
        """Test that AsyncAnalysisService uses provided config when ML is disabled"""
        service = AsyncAnalysisService(max_concurrent=5, config=config_ml_disabled)

        assert service.config == config_ml_disabled, "Service should use provided config"
        assert service.config.ml_enabled is False, "Config should have ml_enabled=False"
        assert service.analysis_service.config == config_ml_disabled, "AnalysisService should use same config"

    def test_uses_default_config_when_none_provided(self):
        """Test that AsyncAnalysisService uses default config when None is provided"""
        service = AsyncAnalysisService(max_concurrent=5, config=None)

        assert service.config is not None, "Service should have a config"
        assert service.config.ml_enabled is False, "Default config should have ml_enabled=False"
        assert isinstance(service.config, StrategyConfig), "Config should be StrategyConfig instance"

    def test_passes_config_to_analysis_service(self, config_ml_enabled):
        """Test that config is passed to underlying AnalysisService"""
        with patch("services.async_analysis_service.AnalysisService") as mock_analysis_service_class:
            mock_analysis_service = MagicMock()
            mock_analysis_service_class.return_value = mock_analysis_service

            service = AsyncAnalysisService(max_concurrent=5, config=config_ml_enabled)

            # Verify AnalysisService was called with the config
            mock_analysis_service_class.assert_called_once()
            call_kwargs = mock_analysis_service_class.call_args[1]
            assert "config" in call_kwargs, "AnalysisService should be called with config"
            assert call_kwargs["config"] == config_ml_enabled, "Config should match provided config"

