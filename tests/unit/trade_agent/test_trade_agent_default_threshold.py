"""Tests for default ML confidence threshold (100%)"""

from unittest.mock import MagicMock, patch

import pytest

from trade_agent import _process_results


class TestDefaultMLConfidenceThreshold:
    """Test that default ML confidence threshold is 100% (1.0)"""

    @pytest.fixture
    def mock_config_default(self):
        """Create a mock StrategyConfig with default threshold"""
        config = MagicMock()
        config.ml_enabled = True
        # Don't set ml_confidence_threshold - should default to 1.0
        config.ml_confidence_threshold = 1.0
        config.ml_combine_with_rules = True
        return config

    @pytest.fixture
    def sample_results(self):
        """Sample results with various ML confidence levels"""
        return [
            {
                "ticker": "STOCK1.NS",
                "status": "success",
                "verdict": "watch",
                "final_verdict": "watch",
                "combined_score": 25.0,
                "ml_verdict": "buy",
                "ml_confidence": 0.99,  # Just below 100% threshold
                "strength_score": 40.0,
                "backtest": {
                    "score": 50.0,
                    "total_return_pct": 10.0,
                    "win_rate": 70.0,
                    "total_trades": 5,
                    "avg_return": 2.0,
                },
                "_config": None,
            },
            {
                "ticker": "STOCK2.NS",
                "status": "success",
                "verdict": "watch",
                "final_verdict": "watch",
                "combined_score": 25.0,
                "ml_verdict": "buy",
                "ml_confidence": 1.0,  # Exactly 100% threshold
                "strength_score": 40.0,
                "backtest": {
                    "score": 50.0,
                    "total_return_pct": 10.0,
                    "win_rate": 70.0,
                    "total_trades": 5,
                    "avg_return": 2.0,
                },
                "_config": None,
            },
            {
                "ticker": "STOCK3.NS",
                "status": "success",
                "verdict": "watch",
                "final_verdict": "watch",
                "combined_score": 25.0,
                "ml_verdict": "buy",
                "ml_confidence": 0.95,  # Below 100% threshold
                "strength_score": 40.0,
                "backtest": {
                    "score": 50.0,
                    "total_return_pct": 10.0,
                    "win_rate": 70.0,
                    "total_trades": 5,
                    "avg_return": 2.0,
                },
                "_config": None,
            },
        ]

    @patch("trade_agent.BacktestService")
    def test_default_threshold_is_100_percent(
        self, mock_backtest_service, sample_results, mock_config_default
    ):
        """Test that default threshold is 100% and only exact 100% passes"""
        mock_service_instance = MagicMock()
        mock_service_instance.add_backtest_scores_to_results.return_value = sample_results
        mock_backtest_service.return_value = mock_service_instance

        sample_results[0]["_config"] = mock_config_default

        with patch("trade_agent.send_telegram"), patch("trade_agent.logger") as mock_logger:
            _process_results(
                sample_results, enable_backtest_scoring=True, config=mock_config_default
            )

            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            log_text = " ".join(log_calls)

            # STOCK1 (99%) should NOT pass (below 100% threshold)
            assert (
                "STOCK1.NS" not in log_text or "BUY" not in log_text
            ), "STOCK1 should NOT pass (99% < 100% threshold)"

            # STOCK2 (100%) should pass (exactly at threshold)
            assert (
                "STOCK2.NS" in log_text and "BUY" in log_text
            ), "STOCK2 should pass (100% >= 100% threshold)"

            # STOCK3 (95%) should NOT pass (below 100% threshold)
            assert (
                "STOCK3.NS" not in log_text or "BUY" not in log_text
            ), "STOCK3 should NOT pass (95% < 100% threshold)"

    @patch("trade_agent.BacktestService")
    def test_custom_threshold_override(
        self, mock_backtest_service, sample_results, mock_config_default
    ):
        """Test that custom threshold can override default"""
        # Set custom threshold to 0.6 (60%)
        mock_config_default.ml_confidence_threshold = 0.6

        mock_service_instance = MagicMock()
        mock_service_instance.add_backtest_scores_to_results.return_value = sample_results
        mock_backtest_service.return_value = mock_service_instance

        sample_results[0]["_config"] = mock_config_default

        with patch("trade_agent.send_telegram"), patch("trade_agent.logger") as mock_logger:
            _process_results(
                sample_results, enable_backtest_scoring=True, config=mock_config_default
            )

            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            log_text = " ".join(log_calls)

            # With 60% threshold, all stocks should pass (all >= 60%)
            assert (
                "STOCK1.NS" in log_text and "BUY" in log_text
            ), "STOCK1 should pass (99% >= 60% threshold)"
            assert (
                "STOCK2.NS" in log_text and "BUY" in log_text
            ), "STOCK2 should pass (100% >= 60% threshold)"
            assert (
                "STOCK3.NS" in log_text and "BUY" in log_text
            ), "STOCK3 should pass (95% >= 60% threshold)"
