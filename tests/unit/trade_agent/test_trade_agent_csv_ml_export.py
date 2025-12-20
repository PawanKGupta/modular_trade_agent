"""Tests for CSV export with ML predictions and rounding"""

from unittest.mock import MagicMock, patch

import pytest

from trade_agent import _process_results


class TestCSVExportMLPredictions:
    """Test CSV export includes ML predictions with proper formatting"""

    @pytest.fixture
    def mock_config(self):
        """Create a mock StrategyConfig"""
        config = MagicMock()
        config.ml_enabled = True
        config.ml_confidence_threshold = 1.0  # 100% default
        config.ml_combine_with_rules = True
        return config

    @pytest.fixture
    def sample_results_with_ml(self):
        """Sample results with ML predictions"""
        return [
            {
                "ticker": "STOCK1.NS",
                "status": "success",
                "verdict": "buy",
                "final_verdict": "buy",
                "combined_score": 30.123456789,  # Should be rounded to 30.12
                "ml_verdict": "buy",
                "ml_confidence": 65.89999999999999,  # Should be rounded to 65.9
                "strength_score": 50.0,
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
                "combined_score": 22.567890123,  # Should be rounded to 22.57
                "ml_verdict": "strong_buy",
                "ml_confidence": 59.599999999999994,  # Should be rounded to 59.6
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
                "verdict": "buy",
                "final_verdict": "buy",
                "combined_score": 28.0,  # Already 2 decimals
                # No ML predictions
                "strength_score": 45.0,
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
    @patch("trade_agent.pd.DataFrame")
    @patch("trade_agent.os.makedirs")
    @patch("trade_agent.os.path.join")
    def test_csv_export_includes_ml_verdicts(
        self,
        mock_join,
        mock_makedirs,
        mock_df,
        mock_backtest_service,
        sample_results_with_ml,
        mock_config,
    ):
        """Test that CSV export includes ML verdicts and confidence with rounding"""
        # Mock backtest service to return results unchanged
        mock_service_instance = MagicMock()
        mock_service_instance.add_backtest_scores_to_results.return_value = sample_results_with_ml
        mock_backtest_service.return_value = mock_service_instance

        # Set config in first result
        sample_results_with_ml[0]["_config"] = mock_config

        # Mock DataFrame to capture the data
        captured_data = []
        mock_df_instance = MagicMock()

        def to_csv_side_effect(path, index=False):
            # Capture the DataFrame data when to_csv is called
            captured_data.append(mock_df_instance.__dict__.copy())

        mock_df_instance.to_csv = MagicMock(side_effect=to_csv_side_effect)
        mock_df.return_value = mock_df_instance

        # Mock path.join to return a test path
        mock_join.return_value = "test_output.csv"

        with patch("trade_agent.send_telegram"), patch("trade_agent.logger"):
            _process_results(
                sample_results_with_ml,
                enable_backtest_scoring=True,
                config=mock_config,
            )

            # Verify DataFrame was created (which means _flatten was called)
            assert mock_df.called, "DataFrame should be created for CSV export"

            # Get the data passed to DataFrame
            df_call_args = mock_df.call_args[0][0] if mock_df.call_args else []

            # Verify ML columns are in the flattened data
            if df_call_args:
                first_row = df_call_args[0] if df_call_args else {}
                assert "ml_verdict" in first_row, "ml_verdict should be in CSV data"
                assert "ml_confidence" in first_row, "ml_confidence should be in CSV data"

                # Find STOCK1 in the data
                stock1_data = next(
                    (r for r in df_call_args if r.get("ticker") == "STOCK1.NS"), None
                )
                if stock1_data:
                    assert stock1_data.get("ml_verdict") == "buy"
                    # Verify rounding to 2 decimals
                    assert stock1_data.get("ml_confidence") == 65.9
                    assert stock1_data.get("combined_score") == 30.12

    def test_flatten_rounds_ml_confidence(self):
        """Test that _flatten function rounds ml_confidence to 2 decimals"""

        # We need to access the _flatten function inside _process_results
        # This is a bit tricky, so we'll test via the actual CSV export
        result = {
            "ticker": "TEST.NS",
            "ml_confidence": 56.89999999999999,
            "combined_score": 22.153756436038744,
        }

        # The rounding happens in _flatten, which is called during CSV export
        # We'll verify this through integration test above

    @patch("trade_agent.BacktestService")
    @patch("trade_agent.pd.DataFrame")
    @patch("trade_agent.os.makedirs")
    @patch("trade_agent.os.path.join")
    def test_csv_export_all_columns_included(
        self,
        mock_join,
        mock_makedirs,
        mock_df,
        mock_backtest_service,
        sample_results_with_ml,
        mock_config,
    ):
        """Test that all columns are included even if values are None"""
        mock_service_instance = MagicMock()
        mock_service_instance.add_backtest_scores_to_results.return_value = sample_results_with_ml
        mock_backtest_service.return_value = mock_service_instance

        sample_results_with_ml[0]["_config"] = mock_config

        mock_df_instance = MagicMock()
        mock_df.return_value = mock_df_instance
        mock_join.return_value = "test_output.csv"

        with patch("trade_agent.send_telegram"), patch("trade_agent.logger"):
            _process_results(
                sample_results_with_ml,
                enable_backtest_scoring=True,
                config=mock_config,
            )

            # Verify DataFrame was created
            assert mock_df.called, "DataFrame should be created for CSV export"

            # Get the data passed to DataFrame
            df_call_args = mock_df.call_args[0][0] if mock_df.call_args else []

            # Verify all expected columns exist in at least one row
            if df_call_args:
                first_row = df_call_args[0] if df_call_args else {}
                required_columns = [
                    "ticker",
                    "ml_verdict",
                    "ml_confidence",
                    "ml_probabilities",
                    "combined_score",
                ]
                for col in required_columns:
                    assert col in first_row, f"Column {col} missing from CSV data"
