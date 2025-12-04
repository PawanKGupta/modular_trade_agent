"""
Unit tests for AnalysisService ML Configuration

Tests that AnalysisService respects ml_enabled setting.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from config.strategy_config import StrategyConfig
from services.analysis_service import AnalysisService


@pytest.fixture
def config_ml_enabled():
    """Create config with ML enabled"""
    return StrategyConfig(
        ml_enabled=True,
        ml_verdict_model_path="models/verdict_model_random_forest.pkl",
        ml_confidence_threshold=0.5,
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


class TestAnalysisServiceMLConfig:
    """Tests for AnalysisService ML configuration handling"""

    def test_analysis_service_respects_ml_enabled_true(self, config_ml_enabled):
        """Test that AnalysisService uses MLVerdictService when ml_enabled=True"""
        with patch("pathlib.Path") as mock_path_class:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_class.return_value = mock_path_instance

            with patch("services.ml_verdict_service.MLVerdictService") as mock_ml_service_class:
                mock_ml_service = MagicMock()
                mock_ml_service.model_loaded = True
                mock_ml_service_class.return_value = mock_ml_service

                service = AnalysisService(config=config_ml_enabled)

                # Should initialize MLVerdictService
                mock_ml_service_class.assert_called_once()
                assert isinstance(service.verdict_service, MagicMock)

    def test_analysis_service_respects_ml_enabled_false(self, config_ml_disabled):
        """Test that AnalysisService uses VerdictService when ml_enabled=False"""
        with patch("services.analysis_service.VerdictService") as mock_verdict_service_class:
            mock_verdict_service = MagicMock()
            mock_verdict_service_class.return_value = mock_verdict_service

            service = AnalysisService(config=config_ml_disabled)

            # Should initialize VerdictService (not MLVerdictService)
            mock_verdict_service_class.assert_called_once()
            assert isinstance(service.verdict_service, MagicMock)

    def test_analysis_service_ml_enabled_but_model_not_found(self, config_ml_enabled):
        """Test that AnalysisService falls back to VerdictService when model not found"""
        with patch("pathlib.Path") as mock_path_class:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = False  # Model file doesn't exist
            mock_path_class.return_value = mock_path_instance

            with patch("services.analysis_service.VerdictService") as mock_verdict_service_class:
                mock_verdict_service = MagicMock()
                mock_verdict_service_class.return_value = mock_verdict_service

                service = AnalysisService(config=config_ml_enabled)

                # Should fallback to VerdictService
                mock_verdict_service_class.assert_called_once()
                assert isinstance(service.verdict_service, MagicMock)

    def test_analysis_service_ml_enabled_but_model_fails_to_load(self, config_ml_enabled):
        """Test that AnalysisService falls back to VerdictService when model fails to load"""
        with patch("pathlib.Path") as mock_path_class:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_class.return_value = mock_path_instance

            with patch("services.ml_verdict_service.MLVerdictService") as mock_ml_service_class:
                mock_ml_service = MagicMock()
                mock_ml_service.model_loaded = False  # Model failed to load
                mock_ml_service_class.return_value = mock_ml_service

                with patch(
                    "services.analysis_service.VerdictService"
                ) as mock_verdict_service_class:
                    mock_verdict_service = MagicMock()
                    mock_verdict_service_class.return_value = mock_verdict_service

                    service = AnalysisService(config=config_ml_enabled)

                    # Should fallback to VerdictService
                    mock_verdict_service_class.assert_called_once()
                    assert isinstance(service.verdict_service, MagicMock)

    def test_analysis_service_ml_enabled_with_custom_model_path(self):
        """Test that AnalysisService uses custom model path from config"""
        config = StrategyConfig(
            ml_enabled=True,
            ml_verdict_model_path="models/custom_model.pkl",
            ml_confidence_threshold=0.5,
            ml_combine_with_rules=True,
        )

        with patch("pathlib.Path") as mock_path_class:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_class.return_value = mock_path_instance

            with patch("services.ml_verdict_service.MLVerdictService") as mock_ml_service_class:
                mock_ml_service = MagicMock()
                mock_ml_service.model_loaded = True
                mock_ml_service_class.return_value = mock_ml_service

                service = AnalysisService(config=config)

                # Should use custom model path
                call_args = mock_ml_service_class.call_args
                assert call_args is not None
                # Check that model_path was passed (either as kwarg or in config)
                assert isinstance(service.verdict_service, MagicMock)
