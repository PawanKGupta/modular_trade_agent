"""
Unit tests for BacktestService ML configuration passing.

Tests that BacktestService correctly passes StrategyConfig to backtest analysis,
ensuring ML predictions are enabled when ml_enabled=True.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from config.strategy_config import StrategyConfig
from services.backtest_service import BacktestService


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


class TestBacktestServiceMLConfig:
    """Test that BacktestService passes ML config to backtest analysis"""

    def test_run_stock_backtest_passes_config_to_integrated_backtest(self, config_ml_enabled):
        """Test that run_stock_backtest passes config to run_integrated_backtest"""
        service = BacktestService(default_years_back=2, dip_mode=False)

        with patch("core.backtest_scoring.run_integrated_backtest") as mock_run_integrated:
            mock_run_integrated.return_value = {
                "total_return_pct": 10.0,
                "win_rate": 60.0,
                "executed_trades": 5,
                "strategy_vs_buy_hold": 2.0,
                "trade_agent_accuracy": 80.0,
            }

            with patch("core.backtest_scoring.BACKTEST_MODE", "integrated"):
                service.run_stock_backtest("TEST.NS", years_back=2, config=config_ml_enabled)

            # Verify config was passed to run_integrated_backtest
            assert mock_run_integrated.called
            call_kwargs = mock_run_integrated.call_args[1]
            assert "config" in call_kwargs
            assert call_kwargs["config"] == config_ml_enabled
            assert call_kwargs["config"].ml_enabled is True

    def test_run_stock_backtest_passes_none_config_when_not_provided(self):
        """Test that run_stock_backtest handles None config gracefully"""
        service = BacktestService(default_years_back=2, dip_mode=False)

        with patch("core.backtest_scoring.run_integrated_backtest") as mock_run_integrated:
            mock_run_integrated.return_value = {
                "total_return_pct": 10.0,
                "win_rate": 60.0,
                "executed_trades": 5,
                "strategy_vs_buy_hold": 2.0,
                "trade_agent_accuracy": 80.0,
            }

            with patch("core.backtest_scoring.BACKTEST_MODE", "integrated"):
                service.run_stock_backtest("TEST.NS", years_back=2, config=None)

            # Verify None config was passed (backward compatibility)
            assert mock_run_integrated.called
            call_kwargs = mock_run_integrated.call_args[1]
            assert "config" in call_kwargs
            assert call_kwargs["config"] is None

    def test_add_backtest_scores_to_results_passes_config(self, config_ml_enabled):
        """Test that add_backtest_scores_to_results passes config to run_stock_backtest"""
        service = BacktestService(default_years_back=2, dip_mode=False)

        stock_results = [
            {
                "ticker": "TEST.NS",
                "strength_score": 50.0,
                "rsi": 25.0,
                "timeframe_analysis": {"alignment_score": 8},
            }
        ]

        with patch.object(service, "run_stock_backtest") as mock_run_backtest:
            mock_run_backtest.return_value = {
                "backtest_score": 60.0,
                "total_return_pct": 30.0,
                "win_rate": 55.0,
                "total_trades": 6,
                "vs_buy_hold": 10.0,
                "execution_rate": 100.0,
            }

            service.add_backtest_scores_to_results(
                stock_results, years_back=2, config=config_ml_enabled
            )

            # Verify config was passed to run_stock_backtest
            assert mock_run_backtest.called
            call_kwargs = mock_run_backtest.call_args[1]
            assert "config" in call_kwargs
            assert call_kwargs["config"] == config_ml_enabled
            assert call_kwargs["config"].ml_enabled is True

    def test_add_backtest_scores_to_results_uses_config_from_stock_result(self, config_ml_enabled):
        """Test that add_backtest_scores_to_results uses _config from stock_result if available"""
        service = BacktestService(default_years_back=2, dip_mode=False)

        stock_results = [
            {
                "ticker": "TEST.NS",
                "strength_score": 50.0,
                "rsi": 25.0,
                "timeframe_analysis": {"alignment_score": 8},
                "_config": config_ml_enabled,  # Config embedded in result
            }
        ]

        with patch.object(service, "run_stock_backtest") as mock_run_backtest:
            mock_run_backtest.return_value = {
                "backtest_score": 60.0,
                "total_return_pct": 30.0,
                "win_rate": 55.0,
                "total_trades": 6,
                "vs_buy_hold": 10.0,
                "execution_rate": 100.0,
            }

            # Don't pass config explicitly - should use from stock_result
            service.add_backtest_scores_to_results(stock_results, years_back=2)

            # Verify config from stock_result was used
            assert mock_run_backtest.called
            call_kwargs = mock_run_backtest.call_args[1]
            assert "config" in call_kwargs
            assert call_kwargs["config"] == config_ml_enabled
            assert call_kwargs["config"].ml_enabled is True

    def test_integrated_backtest_passes_config_to_validation(self, config_ml_enabled):
        """Test that run_integrated_backtest passes config to validate_initial_entry_with_trade_agent"""
        with patch("integrated_backtest.fetch_ohlcv_yf") as mock_fetch:
            # Mock market data
            import pandas as pd

            dates = pd.date_range("2024-01-01", periods=300, freq="D")
            mock_df = pd.DataFrame(
                {
                    "Open": [100.0] * 300,
                    "High": [105.0] * 300,
                    "Low": [95.0] * 300,
                    "Close": [100.0] * 300,
                    "Volume": [1000000] * 300,
                },
                index=dates,
            )
            mock_fetch.return_value = mock_df

            with patch(
                "integrated_backtest.validate_initial_entry_with_trade_agent"
            ) as mock_validate:
                mock_validate.return_value = {"approved": True, "target": 110.0}

                from integrated_backtest import run_integrated_backtest

                run_integrated_backtest(
                    stock_name="TEST.NS",
                    date_range=("2024-01-01", "2024-01-31"),
                    capital_per_position=50000,
                    config=config_ml_enabled,
                )

                # Verify config was passed to validate_initial_entry_with_trade_agent
                if mock_validate.called:
                    call_kwargs = mock_validate.call_args[1]
                    assert "config" in call_kwargs
                    assert call_kwargs["config"] == config_ml_enabled
                    assert call_kwargs["config"].ml_enabled is True

    def test_validate_initial_entry_uses_config_for_analysis_service(self, config_ml_enabled):
        """Test that validate_initial_entry_with_trade_agent uses config for AnalysisService"""
        import pandas as pd

        # Create mock market data
        dates = pd.date_range("2024-01-01", periods=50, freq="D")
        market_data = pd.DataFrame(
            {
                "Close": [100.0] * 50,
                "Open": [100.0] * 50,
                "High": [105.0] * 50,
                "Low": [95.0] * 50,
                "Volume": [1000000] * 50,
            },
            index=dates,
        )

        # Patch AnalysisService where it's imported (inside the function)
        with patch("services.analysis_service.AnalysisService") as mock_analysis_service_class:
            mock_service = MagicMock()
            mock_service.analyze_ticker.return_value = {
                "status": "success",
                "verdict": "buy",
                "target": 110.0,
            }
            mock_analysis_service_class.return_value = mock_service

            from integrated_backtest import validate_initial_entry_with_trade_agent

            validate_initial_entry_with_trade_agent(
                stock_name="TEST.NS",
                signal_date="2024-01-15",
                rsi=25.0,
                ema200=95.0,
                full_market_data=market_data,
                config=config_ml_enabled,
            )

            # Verify AnalysisService was initialized with the correct config
            assert mock_analysis_service_class.called
            call_kwargs = mock_analysis_service_class.call_args[1]
            assert "config" in call_kwargs
            assert call_kwargs["config"] == config_ml_enabled
            assert call_kwargs["config"].ml_enabled is True

    def test_validate_initial_entry_defaults_to_default_config_when_none(
        self,
    ):
        """Test that validate_initial_entry_with_trade_agent uses default config when None"""
        import pandas as pd

        dates = pd.date_range("2024-01-01", periods=50, freq="D")
        market_data = pd.DataFrame(
            {
                "Close": [100.0] * 50,
                "Open": [100.0] * 50,
                "High": [105.0] * 50,
                "Low": [95.0] * 50,
                "Volume": [1000000] * 50,
            },
            index=dates,
        )

        # Patch AnalysisService where it's imported (inside the function)
        with (
            patch("services.analysis_service.AnalysisService") as mock_analysis_service_class,
            patch("integrated_backtest.os.environ.get") as mock_env_get,
        ):
            # Ensure no environment variable is set so it uses default config
            mock_env_get.return_value = None

            mock_service = MagicMock()
            mock_service.analyze_ticker.return_value = {
                "status": "success",
                "verdict": "buy",
                "target": 110.0,
            }
            mock_analysis_service_class.return_value = mock_service

            with patch("config.strategy_config.StrategyConfig.default") as mock_default:
                mock_default_config = StrategyConfig.default()
                mock_default.return_value = mock_default_config

                from integrated_backtest import validate_initial_entry_with_trade_agent

                validate_initial_entry_with_trade_agent(
                    stock_name="TEST.NS",
                    signal_date="2024-01-15",
                    rsi=25.0,
                    ema200=95.0,
                    full_market_data=market_data,
                    config=None,  # None config
                )

                # Verify StrategyConfig.default() was called (at least once)
                assert (
                    mock_default.call_count >= 1
                ), "StrategyConfig.default() should be called when config is None"

                # Verify AnalysisService was initialized with a config
                assert mock_analysis_service_class.called
                call_kwargs = mock_analysis_service_class.call_args[1]
                assert "config" in call_kwargs
                assert call_kwargs["config"] is not None
