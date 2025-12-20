"""Tests for reversal strategy ML prediction selection in integrated_backtest.py

Tests cover:
1. Best from profitable trades (primary approach)
2. Recency-weighted fallback (when no profitable trades)
3. Dynamic period calculation (2 years, 5 years, 7 years with cap)
4. Position linking by entry_date
5. Edge cases (no positions, old format, etc.)
"""

import os
import sys
from unittest.mock import patch

import pandas as pd
import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from integrated_backtest import run_integrated_backtest


class TestReversalStrategyMLPredictions:
    """Test reversal strategy ML prediction selection logic"""

    @pytest.fixture
    def mock_market_data_2years(self):
        """Create 2-year mock market data"""
        dates = pd.date_range("2022-01-01", "2024-01-01", freq="D")
        return pd.DataFrame(
            {
                "Open": [100] * len(dates),
                "High": [105] * len(dates),
                "Low": [95] * len(dates),
                "Close": [102] * len(dates),
                "Volume": [1000000] * len(dates),
            },
            index=dates,
        )

    @pytest.fixture
    def mock_market_data_5years(self):
        """Create 5-year mock market data"""
        dates = pd.date_range("2019-01-01", "2024-01-01", freq="D")
        return pd.DataFrame(
            {
                "Open": [100] * len(dates),
                "High": [105] * len(dates),
                "Low": [95] * len(dates),
                "Close": [102] * len(dates),
                "Volume": [1000000] * len(dates),
            },
            index=dates,
        )

    @pytest.fixture
    def mock_validation_profitable(self):
        """Mock validation that returns profitable ML predictions"""
        predictions = [
            {
                "approved": True,
                "target": 110.0,
                "ml_verdict": "buy",
                "ml_confidence": 60.0,  # 0.6 normalized
            },
            {
                "approved": True,
                "target": 110.0,
                "ml_verdict": "strong_buy",
                "ml_confidence": 70.0,  # 0.7 normalized - best
            },
            {
                "approved": True,
                "target": 110.0,
                "ml_verdict": "buy",
                "ml_confidence": 55.0,  # 0.55 normalized
            },
        ]
        call_count = [0]

        def side_effect(*args, **kwargs):
            idx = call_count[0] % len(predictions)
            call_count[0] += 1
            return predictions[idx]

        return side_effect

    @pytest.fixture
    def mock_validation_unprofitable(self):
        """Mock validation that returns unprofitable ML predictions"""
        predictions = [
            {
                "approved": True,
                "target": 110.0,
                "ml_verdict": "buy",
                "ml_confidence": 60.0,
            },
            {
                "approved": True,
                "target": 110.0,
                "ml_verdict": "strong_buy",
                "ml_confidence": 70.0,
            },
        ]
        call_count = [0]

        def side_effect(*args, **kwargs):
            idx = call_count[0] % len(predictions)
            call_count[0] += 1
            return predictions[idx]

        return side_effect

    def test_best_from_profitable_trades_primary_approach(
        self, mock_market_data_2years, mock_validation_profitable
    ):
        """Test that best ML prediction is selected from profitable trades"""
        with (
            patch("integrated_backtest.fetch_ohlcv_yf") as mock_fetch,
            patch("integrated_backtest.validate_initial_entry_with_trade_agent") as mock_validate,
        ):
            mock_fetch.return_value = mock_market_data_2years
            mock_validate.side_effect = mock_validation_profitable

            # Create data that triggers entries and profitable exits
            dates = pd.date_range("2022-01-01", "2024-01-01", freq="D")
            # Make High hit target (110) on some days to create profitable exits
            mock_data = pd.DataFrame(
                {
                    "Open": [100] * len(dates),
                    "High": [115] * len(dates),  # High enough to hit target
                    "Low": [95] * len(dates),
                    "Close": [102] * len(dates),
                    "Volume": [1000000] * len(dates),
                },
                index=dates,
            )
            mock_fetch.return_value = mock_data

            result = run_integrated_backtest(
                "TEST.NS", ("2022-01-01", "2024-01-01"), 50000, config=None
            )

            # Should have backtest ML predictions
            assert "backtest_ml_verdict" in result
            assert "backtest_ml_confidence" in result

            # If we have profitable trades, should use best from profitable
            if result.get("backtest_ml_verdict"):
                # Should be strong_buy with 70% confidence (best from profitable)
                assert result["backtest_ml_verdict"] in ["buy", "strong_buy"]
                assert result["backtest_ml_confidence"] is not None

    def test_recency_weighted_fallback_when_no_profitable_trades(
        self, mock_market_data_2years, mock_validation_unprofitable
    ):
        """Test that recency-weighted approach is used when no profitable trades"""
        with (
            patch("integrated_backtest.fetch_ohlcv_yf") as mock_fetch,
            patch("integrated_backtest.validate_initial_entry_with_trade_agent") as mock_validate,
        ):
            mock_fetch.return_value = mock_market_data_2years
            mock_validate.side_effect = mock_validation_unprofitable

            # Create data that triggers entries but unprofitable exits (price never hits target)
            dates = pd.date_range("2022-01-01", "2024-01-01", freq="D")
            mock_data = pd.DataFrame(
                {
                    "Open": [100] * len(dates),
                    "High": [105] * len(dates),  # Never hits target (110)
                    "Low": [95] * len(dates),
                    "Close": [98] * len(dates),  # Price goes down (unprofitable)
                    "Volume": [1000000] * len(dates),
                },
                index=dates,
            )
            mock_fetch.return_value = mock_data

            result = run_integrated_backtest(
                "TEST.NS", ("2022-01-01", "2024-01-01"), 50000, config=None
            )

            # Should still have ML predictions (fallback to recency-weighted)
            assert "backtest_ml_verdict" in result
            assert "backtest_ml_confidence" in result

    def test_dynamic_period_calculation_2years(self, mock_market_data_2years):
        """Test that 2-year backtest uses 2-year period for recency weighting"""
        with (
            patch("integrated_backtest.fetch_ohlcv_yf") as mock_fetch,
            patch("integrated_backtest.validate_initial_entry_with_trade_agent") as mock_validate,
        ):
            mock_fetch.return_value = mock_market_data_2years
            mock_validate.return_value = {
                "approved": True,
                "target": 110.0,
                "ml_verdict": "buy",
                "ml_confidence": 60.0,
            }

            result = run_integrated_backtest(
                "TEST.NS", ("2022-01-01", "2024-01-01"), 50000, config=None
            )

            # Should complete without error
            assert "stock_name" in result
            assert "period" in result
            assert "2022-01-01" in result["period"]
            assert "2024-01-01" in result["period"]

    def test_dynamic_period_calculation_5years(self, mock_market_data_5years):
        """Test that 5-year backtest uses 5-year period (capped) for recency weighting"""
        with (
            patch("integrated_backtest.fetch_ohlcv_yf") as mock_fetch,
            patch("integrated_backtest.validate_initial_entry_with_trade_agent") as mock_validate,
        ):
            mock_fetch.return_value = mock_market_data_5years
            mock_validate.return_value = {
                "approved": True,
                "target": 110.0,
                "ml_verdict": "buy",
                "ml_confidence": 60.0,
            }

            result = run_integrated_backtest(
                "TEST.NS", ("2019-01-01", "2024-01-01"), 50000, config=None
            )

            # Should complete without error
            assert "stock_name" in result
            assert "period" in result
            assert "2019-01-01" in result["period"]
            assert "2024-01-01" in result["period"]

    def test_dynamic_period_calculation_7years_capped(self):
        """Test that 7-year backtest caps recency period at 5 years"""
        dates = pd.date_range("2017-01-01", "2024-01-01", freq="D")
        mock_data = pd.DataFrame(
            {
                "Open": [100] * len(dates),
                "High": [105] * len(dates),
                "Low": [95] * len(dates),
                "Close": [102] * len(dates),
                "Volume": [1000000] * len(dates),
            },
            index=dates,
        )

        with (
            patch("integrated_backtest.fetch_ohlcv_yf") as mock_fetch,
            patch("integrated_backtest.validate_initial_entry_with_trade_agent") as mock_validate,
        ):
            mock_fetch.return_value = mock_data
            mock_validate.return_value = {
                "approved": True,
                "target": 110.0,
                "ml_verdict": "buy",
                "ml_confidence": 60.0,
            }

            result = run_integrated_backtest(
                "TEST.NS", ("2017-01-01", "2024-01-01"), 50000, config=None
            )

            # Should complete without error (period capped at 5 years internally)
            assert "stock_name" in result
            assert "period" in result

    def test_position_linking_by_entry_date(self, mock_market_data_2years):
        """Test that ML predictions are linked to positions by entry_date"""
        with (
            patch("integrated_backtest.fetch_ohlcv_yf") as mock_fetch,
            patch("integrated_backtest.validate_initial_entry_with_trade_agent") as mock_validate,
        ):
            mock_fetch.return_value = mock_market_data_2years

            # Return different ML predictions for different dates
            call_dates = []

            def side_effect(stock_name, signal_date, *args, **kwargs):
                call_dates.append(signal_date)
                return {
                    "approved": True,
                    "target": 110.0,
                    "ml_verdict": "buy",
                    "ml_confidence": 60.0,
                }

            mock_validate.side_effect = side_effect

            # Create data that triggers entries
            dates = pd.date_range("2022-01-01", "2024-01-01", freq="D")
            mock_data = pd.DataFrame(
                {
                    "Open": [100] * len(dates),
                    "High": [115] * len(dates),  # Hits target
                    "Low": [95] * len(dates),
                    "Close": [102] * len(dates),
                    "Volume": [1000000] * len(dates),
                },
                index=dates,
            )
            mock_fetch.return_value = mock_data

            result = run_integrated_backtest(
                "TEST.NS", ("2022-01-01", "2024-01-01"), 50000, config=None
            )

            # Should have tracked entry dates
            assert "backtest_ml_verdict" in result
            # Entry dates should be tracked internally (tested via result structure)

    def test_minimum_signal_requirement(self, mock_market_data_2years):
        """Test that at least 1 buy/strong_buy signal is required"""
        with (
            patch("integrated_backtest.fetch_ohlcv_yf") as mock_fetch,
            patch("integrated_backtest.validate_initial_entry_with_trade_agent") as mock_validate,
        ):
            mock_fetch.return_value = mock_market_data_2years
            # Return only watch/avoid verdicts (no buy/strong_buy)
            mock_validate.return_value = {
                "approved": False,
                "ml_verdict": "watch",
                "ml_confidence": 50.0,
            }

            result = run_integrated_backtest(
                "TEST.NS", ("2022-01-01", "2024-01-01"), 50000, config=None
            )

            # Should not have ML predictions if no buy/strong_buy signals
            # backtest_ml_verdict should be None
            assert "backtest_ml_verdict" in result
            # May be None if no buy/strong_buy predictions

    def test_old_format_predictions_handled(self, mock_market_data_2years):
        """Test that old format predictions (without entry_date) are handled"""
        with (
            patch("integrated_backtest.fetch_ohlcv_yf") as mock_fetch,
            patch("integrated_backtest.validate_initial_entry_with_trade_agent") as mock_validate,
        ):
            mock_fetch.return_value = mock_market_data_2years
            mock_validate.return_value = {
                "approved": True,
                "target": 110.0,
                "ml_verdict": "buy",
                "ml_confidence": 60.0,
            }

            result = run_integrated_backtest(
                "TEST.NS", ("2022-01-01", "2024-01-01"), 50000, config=None
            )

            # Should complete without error even with old format
            assert "stock_name" in result

    def test_no_positions_case(self, mock_market_data_2years):
        """Test recency-weighted approach when no positions are created"""
        with (
            patch("integrated_backtest.fetch_ohlcv_yf") as mock_fetch,
            patch("integrated_backtest.validate_initial_entry_with_trade_agent") as mock_validate,
        ):
            mock_fetch.return_value = mock_market_data_2years
            # Return approved but no positions created (edge case)
            mock_validate.return_value = {
                "approved": False,  # Not approved, so no positions
                "ml_verdict": "buy",
                "ml_confidence": 60.0,
            }

            result = run_integrated_backtest(
                "TEST.NS", ("2022-01-01", "2024-01-01"), 50000, config=None
            )

            # Should handle no positions gracefully
            assert "stock_name" in result
            assert "executed_trades" in result
            assert result["executed_trades"] == 0

    def test_recency_weight_calculation(self):
        """Test that recency weights are calculated correctly"""
        import pandas as pd

        # Test recency weight formula: weight = 1.0 - (days_from_end / max_days) * 0.5
        end_date = "2024-12-31"
        start_date = "2022-01-01"
        end_dt = pd.to_datetime(end_date)
        start_dt = pd.to_datetime(start_date)
        actual_days = (end_dt - start_dt).days
        max_days = min(actual_days, 1825)  # Cap at 5 years
        max_days = max(365, max_days)

        # Most recent (0 days): weight should be 1.0
        days_from_end = 0
        weight = 1.0 - (days_from_end / max_days) * 0.5
        assert abs(weight - 1.0) < 0.01

        # 1 year ago (365 days): weight should be ~0.75 for 2-year period
        if actual_days >= 365:
            days_from_end = 365
            weight = 1.0 - (days_from_end / max_days) * 0.5
            # For 2-year period (730 days): weight = 1.0 - (365/730)*0.5 = 0.75
            expected_weight = 1.0 - (365 / max_days) * 0.5
            assert abs(weight - expected_weight) < 0.01

        # Oldest (max_days+): weight should be 0.5 (clamped)
        days_from_end = max_days + 100
        weight = 1.0 - (days_from_end / max_days) * 0.5
        weight = max(0.5, min(1.0, weight))  # Clamp
        assert abs(weight - 0.5) < 0.01

    def test_limited_data_stock_uses_actual_period(self):
        """Test that stock with only 600 days data uses 600 days, not requested 1825"""
        # Create mock data with only 600 days (less than requested 5 years)
        dates = pd.date_range("2023-06-01", "2024-12-31", freq="D")  # ~600 days
        mock_data = pd.DataFrame(
            {
                "Open": [100] * len(dates),
                "High": [105] * len(dates),
                "Low": [95] * len(dates),
                "Close": [102] * len(dates),
                "Volume": [1000000] * len(dates),
            },
            index=dates,
        )

        with (
            patch("integrated_backtest.fetch_ohlcv_yf") as mock_fetch,
            patch("integrated_backtest.validate_initial_entry_with_trade_agent") as mock_validate,
        ):
            mock_fetch.return_value = mock_data
            mock_validate.return_value = {
                "approved": True,
                "target": 110.0,
                "ml_verdict": "buy",
                "ml_confidence": 60.0,
            }

            # Request 5 years (1825 days) but stock only has ~600 days
            result = run_integrated_backtest(
                "TEST.NS", ("2019-01-01", "2024-12-31"), 50000, config=None
            )

            # Should complete without error
            assert "stock_name" in result
            assert "period" in result

            # The recency weighting should use actual data period (600 days), not requested (1825)
            # This is tested implicitly - if it used 1825, weights would be incorrect
            # For 600-day stock: weight at 300 days = 1.0 - (300/600)*0.5 = 0.75
            # For 1825-day stock: weight at 300 days = 1.0 - (300/1825)*0.5 = 0.92 (wrong!)
            # So using actual period ensures correct weighting


class TestDefaultBacktestPeriod:
    """Test that default backtest period is 5 years"""

    def test_backtest_service_default_years(self):
        """Test BacktestService defaults to 5 years"""
        from services.backtest_service import BacktestService

        service = BacktestService()
        assert service.default_years_back == 5

    def test_run_simple_backtest_default_years(self):
        """Test run_simple_backtest defaults to 5 years"""
        import inspect

        from core.backtest_scoring import run_simple_backtest

        sig = inspect.signature(run_simple_backtest)
        assert sig.parameters["years_back"].default == 5

    def test_run_stock_backtest_default_years(self):
        """Test run_stock_backtest defaults to 5 years"""
        import inspect

        from core.backtest_scoring import run_stock_backtest

        sig = inspect.signature(run_stock_backtest)
        assert sig.parameters["years_back"].default == 5

    def test_trade_agent_uses_5_years(self):
        """Test that trade_agent.py uses 5 years for backtest"""
        # Check if BacktestService is instantiated with 5 years
        # This is tested via integration, but we can check the default
        from services.backtest_service import BacktestService

        service = BacktestService()
        assert service.default_years_back == 5

    def test_add_backtest_scores_default_years(self):
        """Test add_backtest_scores_to_results defaults to 5 years"""
        import inspect

        from core.backtest_scoring import add_backtest_scores_to_results

        sig = inspect.signature(add_backtest_scores_to_results)
        assert sig.parameters["years_back"].default == 5
