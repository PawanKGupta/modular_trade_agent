"""Tests for quality-focused filtering enhancements in trade_agent.py"""

from unittest.mock import MagicMock, patch

import pytest

from trade_agent import _process_results


class TestQualityFocusedFiltering:
    """Test quality-focused filtering with backtest quality filters"""

    @pytest.fixture
    def mock_config(self):
        """Create a mock StrategyConfig"""
        config = MagicMock()
        config.ml_enabled = True
        config.ml_confidence_threshold = 0.6
        config.ml_combine_with_rules = True
        return config

    @pytest.fixture
    def sample_results_with_backtest(self):
        """Sample results with backtest data"""
        return [
            {
                "ticker": "STOCK1.NS",
                "status": "success",
                "verdict": "buy",
                "final_verdict": "strong_buy",
                "combined_score": 30.0,
                "ml_verdict": "buy",
                "ml_confidence": 0.65,
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
                "combined_score": 22.0,
                "ml_verdict": "buy",
                "ml_confidence": 0.68,
                "strength_score": 40.0,
                "backtest": {
                    "score": 48.0,
                    "total_return_pct": 12.0,
                    "win_rate": 72.0,
                    "total_trades": 6,
                    "avg_return": 2.0,
                },
                "_config": None,
            },
            {
                "ticker": "STOCK3.NS",
                "status": "success",
                "verdict": "buy",
                "final_verdict": "buy",
                "combined_score": 28.0,
                "ml_verdict": "buy",
                "ml_confidence": 0.55,
                "strength_score": 45.0,
                "backtest": {
                    "score": 50.0,
                    "total_return_pct": 8.0,
                    "win_rate": 68.0,
                    "total_trades": 4,
                    "avg_return": 2.0,
                },
                "_config": None,
            },
            {
                "ticker": "STOCK4.NS",
                "status": "success",
                "verdict": "buy",
                "final_verdict": "buy",
                "combined_score": 30.0,
                "ml_verdict": "buy",
                "ml_confidence": 0.70,
                "strength_score": 50.0,
                "backtest": {
                    "score": 30.0,  # Low backtest score
                    "total_return_pct": 5.0,
                    "win_rate": 50.0,  # Low win rate
                    "total_trades": 2,
                    "avg_return": 2.5,
                },
                "_config": None,
            },
            {
                "ticker": "STOCK5.NS",
                "status": "success",
                "verdict": "buy",
                "final_verdict": "buy",
                "combined_score": 25.0,
                "ml_verdict": "buy",
                "ml_confidence": 0.65,
                "strength_score": 45.0,
                "backtest": {
                    "score": 50.0,
                    "total_return_pct": -2.0,  # Negative return
                    "win_rate": 70.0,
                    "total_trades": 3,
                    "avg_return": 1.8,
                },
                "_config": None,
            },
        ]

    def test_backtest_quality_filters_pass_high_quality_stocks(
        self, sample_results_with_backtest, mock_config
    ):
        """Test that high-quality stocks pass backtest quality filters"""
        # Set config in first result
        sample_results_with_backtest[0]["_config"] = mock_config

        with patch("trade_agent.BacktestService") as mock_backtest_service:
            mock_backtest_service.return_value.add_backtest_scores_to_results.return_value = (
                sample_results_with_backtest
            )

            with patch("trade_agent.send_telegram"), patch("trade_agent.logger") as mock_logger:
                processed = _process_results(
                    sample_results_with_backtest, enable_backtest_scoring=True, config=mock_config
                )

                # Check logs to verify which stocks passed filtering
                log_calls = [str(call) for call in mock_logger.info.call_args_list]
                log_text = " ".join(log_calls)

                # STOCK1 should pass (strong_buy, score 30, good backtest)
                assert (
                    "STOCK1.NS" in log_text and "STRONG_BUY" in log_text
                ), "STOCK1 should pass quality filters"

                # STOCK2 should pass (weak final_verdict but ML buy with good backtest)
                assert (
                    "STOCK2.NS" in log_text and "BUY" in log_text
                ), "STOCK2 should pass quality filters (ML-only with weak final_verdict)"

                # STOCK3 should pass (buy, score 28, good backtest)
                assert (
                    "STOCK3.NS" in log_text and "BUY" in log_text
                ), "STOCK3 should pass quality filters"

                # STOCK4 should fail (low backtest score and win rate)
                assert (
                    "STOCK4.NS" not in log_text or "Backtest quality filter failed" in log_text
                ), "STOCK4 should fail quality filters (low backtest score)"

                # STOCK5 should fail (negative return)
                assert (
                    "STOCK5.NS" not in log_text or "Backtest quality filter failed" in log_text
                ), "STOCK5 should fail quality filters (negative return)"

    def test_ml_verdict_checked_when_final_verdict_weak(
        self, sample_results_with_backtest, mock_config
    ):
        """Test that ML verdict is checked even when combine=true if final_verdict is weak"""
        # Set config in first result
        sample_results_with_backtest[0]["_config"] = mock_config
        mock_config.ml_combine_with_rules = True

        with patch("trade_agent.BacktestService") as mock_backtest_service:
            mock_backtest_service.return_value.add_backtest_scores_to_results.return_value = (
                sample_results_with_backtest
            )

            with patch("trade_agent.send_telegram"), patch("trade_agent.logger") as mock_logger:
                processed = _process_results(
                    sample_results_with_backtest, enable_backtest_scoring=True, config=mock_config
                )

                # STOCK2 has weak final_verdict (watch) but ML says buy with good confidence and score
                log_calls = [str(call) for call in mock_logger.info.call_args_list]
                log_text = " ".join(log_calls)
                assert (
                    "STOCK2.NS" in log_text and "BUY" in log_text
                ), "STOCK2 should pass (ML checked even with weak final_verdict)"

    def test_ml_only_minimum_score_threshold(self, sample_results_with_backtest, mock_config):
        """Test that ML-only signals require minimum score of 20"""
        # Create a stock with ML buy but low score
        low_score_stock = {
            "ticker": "STOCK6.NS",
            "status": "success",
            "verdict": "watch",
            "final_verdict": "watch",
            "combined_score": 15.0,  # Below threshold of 20
            "ml_verdict": "buy",
            "ml_confidence": 0.70,
            "strength_score": 30.0,
            "backtest": {
                "score": 50.0,
                "total_return_pct": 10.0,
                "win_rate": 70.0,
                "total_trades": 5,
                "avg_return": 2.0,
            },
            "_config": None,
        }
        sample_results_with_backtest.append(low_score_stock)
        sample_results_with_backtest[0]["_config"] = mock_config

        with patch("trade_agent.BacktestService") as mock_backtest_service:
            mock_backtest_service.return_value.add_backtest_scores_to_results.return_value = (
                sample_results_with_backtest
            )

            with patch("trade_agent.send_telegram") as mock_telegram:
                processed = _process_results(
                    sample_results_with_backtest, enable_backtest_scoring=True, config=mock_config
                )

                assert mock_telegram.called
                telegram_msg = mock_telegram.call_args[0][0]
                assert (
                    "STOCK6.NS" not in telegram_msg
                ), "STOCK6 should fail (score 15 < 20 threshold)"

    def test_no_minimum_trades_requirement(self, sample_results_with_backtest, mock_config):
        """Test that even 1 trade with 100% win rate passes quality filters"""
        single_trade_stock = {
            "ticker": "STOCK7.NS",
            "status": "success",
            "verdict": "buy",
            "final_verdict": "buy",
            "combined_score": 30.0,
            "ml_verdict": "buy",
            "ml_confidence": 0.65,
            "strength_score": 50.0,
            "backtest": {
                "score": 50.0,
                "total_return_pct": 5.0,
                "win_rate": 100.0,  # 100% win rate
                "total_trades": 1,  # Only 1 trade
                "avg_return": 5.0,
            },
            "_config": None,
        }
        sample_results_with_backtest.append(single_trade_stock)
        sample_results_with_backtest[0]["_config"] = mock_config

        with patch("trade_agent.BacktestService") as mock_backtest_service:
            mock_backtest_service.return_value.add_backtest_scores_to_results.return_value = (
                sample_results_with_backtest
            )

            with patch("trade_agent.send_telegram"), patch("trade_agent.logger") as mock_logger:
                processed = _process_results(
                    sample_results_with_backtest, enable_backtest_scoring=True, config=mock_config
                )

                log_calls = [str(call) for call in mock_logger.info.call_args_list]
                log_text = " ".join(log_calls)
                assert (
                    "STOCK7.NS" in log_text and "BUY" in log_text
                ), "STOCK7 should pass (1 trade with 100% win rate is valuable)"

    def test_config_extracted_first(self, sample_results_with_backtest, mock_config):
        """Test that config is extracted first before any filtering"""
        # Don't set config in results initially
        for result in sample_results_with_backtest:
            result["_config"] = None

        with patch("trade_agent.BacktestService") as mock_backtest_service:
            mock_backtest_service.return_value.add_backtest_scores_to_results.return_value = (
                sample_results_with_backtest
            )

            # Pass config as parameter
            processed = _process_results(
                sample_results_with_backtest, enable_backtest_scoring=True, config=mock_config
            )

            # Should still work correctly with config passed as parameter
            assert processed is not None

    def test_ml_enabled_respected_in_filtering(self, sample_results_with_backtest, mock_config):
        """Test that ML-only signals are filtered out when ml_enabled=False"""
        # Set ml_enabled=False
        mock_config.ml_enabled = False
        mock_config.ml_combine_with_rules = False  # Even if combine is false, ML should be ignored

        # Set config in first result
        sample_results_with_backtest[0]["_config"] = mock_config

        with patch("trade_agent.BacktestService") as mock_backtest_service:
            mock_backtest_service.return_value.add_backtest_scores_to_results.return_value = (
                sample_results_with_backtest
            )

            with patch("trade_agent.send_telegram"), patch("trade_agent.logger") as mock_logger:
                processed = _process_results(
                    sample_results_with_backtest, enable_backtest_scoring=True, config=mock_config
                )

                # Check logs - STOCK2 has ML-only buy but ml_enabled=False, so it should NOT pass
                log_calls = [str(call) for call in mock_logger.info.call_args_list]
                log_text = " ".join(log_calls)

                # STOCK1 should pass (rule-based strong_buy)
                assert (
                    "STOCK1.NS" in log_text and "STRONG_BUY" in log_text
                ), "STOCK1 should pass (rule-based)"

                # STOCK2 should NOT pass (ML-only but ml_enabled=False)
                assert (
                    "STOCK2.NS" not in log_text or "BUY" not in log_text
                ), "STOCK2 should NOT pass (ML-only but ml_enabled=False)"

                # STOCK3 should pass (rule-based buy)
                assert (
                    "STOCK3.NS" in log_text and "BUY" in log_text
                ), "STOCK3 should pass (rule-based)"

    def test_ml_confidence_normalization_logging(
        self, sample_results_with_backtest, mock_config, caplog
    ):
        """Test that ML confidence normalization is logged when converting percentage to decimal"""
        # Create stock with percentage confidence (0-100)
        percentage_confidence_stock = {
            "ticker": "STOCK8.NS",
            "status": "success",
            "verdict": "watch",
            "final_verdict": "watch",
            "combined_score": 25.0,
            "ml_verdict": "buy",
            "ml_confidence": 65.0,  # Percentage format (0-100)
            "strength_score": 40.0,
            "backtest": {
                "score": 50.0,
                "total_return_pct": 10.0,
                "win_rate": 70.0,
                "total_trades": 5,
                "avg_return": 2.0,
            },
            "_config": None,
        }
        sample_results_with_backtest.append(percentage_confidence_stock)
        sample_results_with_backtest[0]["_config"] = mock_config

        with patch("trade_agent.BacktestService") as mock_backtest_service:
            mock_backtest_service.return_value.add_backtest_scores_to_results.return_value = (
                sample_results_with_backtest
            )

            with caplog.at_level("DEBUG"):
                _process_results(
                    sample_results_with_backtest, enable_backtest_scoring=True, config=mock_config
                )

            # Check that normalization was logged
            assert any("Normalized ML confidence" in record.message for record in caplog.records)
