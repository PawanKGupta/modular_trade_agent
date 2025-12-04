"""
Unit tests for _process_results config extraction in trade_agent.py.

Tests that _process_results extracts config from results and passes to backtest.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.strategy_config import StrategyConfig


@pytest.fixture
def config_ml_enabled():
    """Create config with ML enabled"""
    return StrategyConfig(
        ml_enabled=True,
        ml_verdict_model_path="models/verdict_model_random_forest.pkl",
        ml_confidence_threshold=0.7,
        ml_combine_with_rules=True,
    )


class TestProcessResultsConfigExtraction:
    """Test config extraction from results in _process_results"""

    @patch("trade_agent.BacktestService")
    @patch("trade_agent.compute_strength_score")
    @patch("trade_agent.compute_trading_priority_score")
    @patch("services.ml_verdict_service.MLVerdictService")
    @patch("pathlib.Path.exists")
    def test_extracts_config_from_results(self, mock_path_exists, mock_ml_service, mock_priority_score, mock_strength_score, mock_backtest_service_class, config_ml_enabled):
        """Test that config is extracted from results and passed to backtest"""
        # Setup mocks to avoid loading ML model
        mock_path_exists.return_value = False
        mock_strength_score.return_value = 50.0
        mock_priority_score.return_value = 60.0
        
        # Import the function
        import trade_agent
        _process_results = trade_agent._process_results

        # Create mock results with config
        results = [
            {
                "ticker": "TEST1.NS",
                "status": "success",
                "strength_score": 50.0,
                "_config": config_ml_enabled,  # Config stored in result
            },
            {
                "ticker": "TEST2.NS",
                "status": "success",
                "strength_score": 60.0,
                "_config": config_ml_enabled,  # Config stored in result
            },
        ]

        # Setup mock backtest service
        mock_backtest_service = MagicMock()
        mock_backtest_service_class.return_value = mock_backtest_service
        mock_backtest_service.add_backtest_scores_to_results.return_value = results

        # Process results with backtest enabled
        processed_results = _process_results(results, enable_backtest_scoring=True, dip_mode=False)

        # Verify backtest service was called with config
        assert mock_backtest_service.add_backtest_scores_to_results.called
        call_kwargs = mock_backtest_service.add_backtest_scores_to_results.call_args[1]
        assert "config" in call_kwargs, "Backtest service should be called with config"
        assert call_kwargs["config"] == config_ml_enabled, "Config should match extracted config"
        assert call_kwargs["config"].ml_enabled is True, "Config should have ml_enabled=True"

    @patch("trade_agent.BacktestService")
    @patch("trade_agent.compute_strength_score")
    @patch("trade_agent.compute_trading_priority_score")
    @patch("services.ml_verdict_service.MLVerdictService")
    @patch("pathlib.Path.exists")
    def test_handles_results_without_config(self, mock_path_exists, mock_ml_service, mock_priority_score, mock_strength_score, mock_backtest_service_class):
        """Test that None config is used when results don't have _config field"""
        # Setup mocks
        mock_path_exists.return_value = False  # Model doesn't exist to avoid loading
        mock_strength_score.return_value = 50.0
        mock_priority_score.return_value = 60.0
        
        import trade_agent
        _process_results = trade_agent._process_results

        # Create results without config
        results = [
            {
                "ticker": "TEST1.NS",
                "status": "success",
                "strength_score": 50.0,
                # No _config field
            },
        ]

        # Setup mock backtest service
        mock_backtest_service = MagicMock()
        mock_backtest_service_class.return_value = mock_backtest_service
        mock_backtest_service.add_backtest_scores_to_results.return_value = results

        # Process results
        processed_results = _process_results(results, enable_backtest_scoring=True, dip_mode=False)

        # Verify backtest service was called (with None config)
        assert mock_backtest_service.add_backtest_scores_to_results.called
        call_kwargs = mock_backtest_service.add_backtest_scores_to_results.call_args[1]
        assert "config" in call_kwargs, "Backtest service should be called with config parameter"
        # Config should be None when not in results
        assert call_kwargs["config"] is None, "Config should be None when not in results"

    @patch("trade_agent.BacktestService")
    @patch("trade_agent.compute_strength_score")
    @patch("trade_agent.compute_trading_priority_score")
    @patch("services.ml_verdict_service.MLVerdictService")
    @patch("pathlib.Path.exists")
    def test_extracts_config_from_first_result(self, mock_path_exists, mock_ml_service, mock_priority_score, mock_strength_score, mock_backtest_service_class, config_ml_enabled):
        """Test that config is extracted from first result when available"""
        # Setup mocks
        mock_path_exists.return_value = False  # Model doesn't exist to avoid loading
        mock_strength_score.return_value = 50.0
        mock_priority_score.return_value = 60.0
        
        import trade_agent
        _process_results = trade_agent._process_results

        # Create results with config in first result only
        results = [
            {
                "ticker": "TEST1.NS",
                "status": "success",
                "strength_score": 50.0,
                "_config": config_ml_enabled,  # Config in first result
            },
            {
                "ticker": "TEST2.NS",
                "status": "success",
                "strength_score": 60.0,
                # No config in second result
            },
        ]

        # Setup mock backtest service
        mock_backtest_service = MagicMock()
        mock_backtest_service_class.return_value = mock_backtest_service
        mock_backtest_service.add_backtest_scores_to_results.return_value = results

        # Process results
        processed_results = _process_results(results, enable_backtest_scoring=True, dip_mode=False)

        # Verify config from first result was used
        assert mock_backtest_service.add_backtest_scores_to_results.called
        call_kwargs = mock_backtest_service.add_backtest_scores_to_results.call_args[1]
        assert call_kwargs["config"] == config_ml_enabled, "Config from first result should be used"

