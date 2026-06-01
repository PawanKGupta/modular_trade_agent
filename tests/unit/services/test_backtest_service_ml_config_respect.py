"""Tests for BacktestService ML configuration respect"""

from unittest.mock import patch

import pytest

from config.strategy_config import StrategyConfig
from services.backtest_service import BacktestService


def _config_from_call(call_args):
    if "config" in call_args.kwargs:
        return call_args.kwargs["config"]
    if len(call_args.args) > 3:
        return call_args.args[3]
    return None


class TestBacktestServiceMLConfigRespect:
    """Test that BacktestService respects ML configuration"""

    @pytest.fixture
    def ml_enabled_config(self):
        """Create config with ML enabled"""
        config = StrategyConfig.default()
        config.ml_enabled = True
        config.ml_confidence_threshold = 0.6
        config.ml_combine_with_rules = True
        return config

    @pytest.fixture
    def sample_stock_result(self):
        """Create sample stock result"""
        return {
            "ticker": "TEST.NS",
            "status": "success",
            "verdict": "buy",
            "combined_score": 30.0,
            "strength_score": 50.0,
            "_config": None,  # Will be set in tests
        }

    def test_backtest_service_passes_config_to_run_stock_backtest(
        self, ml_enabled_config, sample_stock_result
    ):
        """Test that BacktestService passes config to run_stock_backtest"""
        service = BacktestService()
        with patch.object(service, "run_stock_backtest") as mock_run_backtest:
            mock_run_backtest.return_value = {
                "backtest_score": 50.0,
                "total_return_pct": 10.0,
                "win_rate": 70.0,
                "total_trades": 5,
                "avg_return": 2.0,
            }

            service.add_backtest_scores_to_results(
                [sample_stock_result],
                config=ml_enabled_config,
            )

            mock_run_backtest.assert_called_once()
            call_config = _config_from_call(mock_run_backtest.call_args)
            assert call_config is not None and call_config.ml_enabled is True

    def test_backtest_service_uses_config_from_result_if_available(
        self, ml_enabled_config, sample_stock_result
    ):
        """Test that BacktestService uses config from result if available"""
        # Set config in result
        sample_stock_result["_config"] = ml_enabled_config

        service = BacktestService()
        with patch.object(service, "run_stock_backtest") as mock_run_backtest:
            mock_run_backtest.return_value = {
                "backtest_score": 50.0,
                "total_return_pct": 10.0,
                "win_rate": 70.0,
                "total_trades": 5,
                "avg_return": 2.0,
            }

            service.add_backtest_scores_to_results(
                [sample_stock_result],
                config=None,  # No config passed, should use from result
            )

            mock_run_backtest.assert_called_once()
            call_config = _config_from_call(mock_run_backtest.call_args)
            assert call_config is not None and call_config.ml_enabled is True

    def test_backtest_service_logs_config_usage(
        self, ml_enabled_config, sample_stock_result, caplog
    ):
        """Test that BacktestService logs config usage"""
        sample_stock_result["_config"] = ml_enabled_config

        service = BacktestService()
        with patch.object(service, "run_stock_backtest") as mock_run_backtest:
            mock_run_backtest.return_value = {
                "backtest_score": 50.0,
                "total_return_pct": 10.0,
                "win_rate": 70.0,
                "total_trades": 5,
                "avg_return": 2.0,
            }

            with caplog.at_level("DEBUG"):
                service.add_backtest_scores_to_results(
                    [sample_stock_result],
                    config=None,
                )

            # Check that config usage was logged
            assert any(
                "Using config for backtest" in record.message
                and "ml_enabled=True" in record.message
                for record in caplog.records
            ), "Should log config usage"

    def test_backtest_service_warns_when_no_config(self, sample_stock_result, caplog):
        """Test that BacktestService warns when no config is available"""
        # No config in result and no config passed
        sample_stock_result["_config"] = None

        service = BacktestService()
        with patch.object(service, "run_stock_backtest") as mock_run_backtest:
            mock_run_backtest.return_value = {
                "backtest_score": 50.0,
                "total_return_pct": 10.0,
                "win_rate": 70.0,
                "total_trades": 5,
                "avg_return": 2.0,
            }

            with caplog.at_level("WARNING"):
                service.add_backtest_scores_to_results(
                    [sample_stock_result],
                    config=None,
                )

            # Check that warning was logged
            assert any(
                "No config available for backtest" in record.message for record in caplog.records
            ), "Should warn when no config available"
