"""
Unit tests for look-ahead bias fix in training data collection.

Tests that features are extracted from signal_date (entry_date - 1 trading day)
instead of entry_date to prevent look-ahead bias.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
import pandas as pd
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from scripts.collect_training_data import extract_features_at_date


class TestLookAheadBiasFix:
    """Test suite for look-ahead bias fix in feature extraction"""

    def test_signal_date_calculation_weekday(self):
        """Test signal_date = entry_date - 1 for weekdays"""
        # Wednesday entry -> Tuesday signal
        entry_date = "2024-11-13"  # Wednesday
        expected_signal_date = "2024-11-12"  # Tuesday

        with patch('scripts.collect_training_data.IndicatorService') as mock_is:
            mock_indicator_service = mock_is.return_value
            mock_df = self._create_mock_dataframe()
            mock_indicator_service.compute_indicators.return_value = mock_df

            with patch('scripts.collect_training_data.SignalService') as mock_ss, \
                 patch('scripts.collect_training_data.VerdictService') as mock_vs, \
                 patch('core.data_fetcher.fetch_ohlcv_yf', return_value=mock_df) as mock_fetch:

                extract_features_at_date(
                    ticker="TEST.NS",
                    entry_date=entry_date,
                    data_service=Mock(),
                    indicator_service=mock_indicator_service,
                    signal_service=mock_ss.return_value,
                    verdict_service=mock_vs.return_value
                )

                # Verify fetch_ohlcv_yf was called with signal_date, not entry_date
                call_args = mock_fetch.call_args
                assert call_args[1]['end_date'] == expected_signal_date, \
                    f"Should use signal_date {expected_signal_date}, not entry_date {entry_date}"

    def test_signal_date_calculation_monday_entry(self):
        """Test signal_date skips weekend for Monday entry"""
        # Monday entry -> Friday signal (skip Sat/Sun)
        entry_date = "2024-11-11"  # Monday
        expected_signal_date = "2024-11-08"  # Friday (not Nov 10 Sunday!)

        with patch('scripts.collect_training_data.IndicatorService') as mock_is:
            mock_indicator_service = mock_is.return_value
            mock_df = self._create_mock_dataframe()
            mock_indicator_service.compute_indicators.return_value = mock_df

            with patch('scripts.collect_training_data.SignalService') as mock_ss, \
                 patch('scripts.collect_training_data.VerdictService') as mock_vs, \
                 patch('core.data_fetcher.fetch_ohlcv_yf', return_value=mock_df) as mock_fetch:

                extract_features_at_date(
                    ticker="TEST.NS",
                    entry_date=entry_date,
                    data_service=Mock(),
                    indicator_service=mock_indicator_service,
                    signal_service=mock_ss.return_value,
                    verdict_service=mock_vs.return_value
                )

                call_args = mock_fetch.call_args
                assert call_args[1]['end_date'] == expected_signal_date, \
                    f"Monday entry should use Friday signal, got {call_args[1]['end_date']}"

    def test_signal_date_calculation_tuesday_entry(self):
        """Test signal_date for Tuesday entry (skip weekend correctly)"""
        # Tuesday entry -> Monday signal (not Saturday!)
        entry_date = "2024-11-12"  # Tuesday
        expected_signal_date = "2024-11-11"  # Monday

        with patch('scripts.collect_training_data.IndicatorService') as mock_is:
            mock_indicator_service = mock_is.return_value
            mock_df = self._create_mock_dataframe()
            mock_indicator_service.compute_indicators.return_value = mock_df

            with patch('scripts.collect_training_data.SignalService') as mock_ss, \
                 patch('scripts.collect_training_data.VerdictService') as mock_vs, \
                 patch('core.data_fetcher.fetch_ohlcv_yf', return_value=mock_df) as mock_fetch:

                extract_features_at_date(
                    ticker="TEST.NS",
                    entry_date=entry_date,
                    data_service=Mock(),
                    indicator_service=mock_indicator_service,
                    signal_service=mock_ss.return_value,
                    verdict_service=mock_vs.return_value
                )

                call_args = mock_fetch.call_args
                assert call_args[1]['end_date'] == expected_signal_date

    def test_signal_date_calculation_friday_entry(self):
        """Test signal_date for Friday entry"""
        # Friday entry -> Thursday signal
        entry_date = "2024-11-15"  # Friday
        expected_signal_date = "2024-11-14"  # Thursday

        with patch('scripts.collect_training_data.IndicatorService') as mock_is:
            mock_indicator_service = mock_is.return_value
            mock_df = self._create_mock_dataframe()
            mock_indicator_service.compute_indicators.return_value = mock_df

            with patch('scripts.collect_training_data.SignalService') as mock_ss, \
                 patch('scripts.collect_training_data.VerdictService') as mock_vs, \
                 patch('core.data_fetcher.fetch_ohlcv_yf', return_value=mock_df) as mock_fetch:

                extract_features_at_date(
                    ticker="TEST.NS",
                    entry_date=entry_date,
                    data_service=Mock(),
                    indicator_service=mock_indicator_service,
                    signal_service=mock_ss.return_value,
                    verdict_service=mock_vs.return_value
                )

                call_args = mock_fetch.call_args
                assert call_args[1]['end_date'] == expected_signal_date

    def test_features_not_using_entry_date_data(self):
        """Test that features don't leak entry_date's data"""
        entry_date = "2024-11-11"  # Monday
        signal_date = "2024-11-08"  # Friday

        # Create different data for signal_date vs entry_date
        signal_date_df = self._create_mock_dataframe(
            close_price=1278.64,
            volume=19814406,
            rsi=28.84
        )

        entry_date_df = self._create_mock_dataframe(
            close_price=1267.64,  # Different!
            volume=9056552,       # Different!
            rsi=26.53              # Different!
        )

        with patch('scripts.collect_training_data.DataService') as mock_ds:
            mock_data_service = mock_ds.return_value

            # Return signal_date_df for signal_date, entry_date_df for entry_date
            def fetch_side_effect(ticker, end_date, **kwargs):
                if end_date == signal_date:
                    return signal_date_df
                elif end_date == entry_date:
                    return entry_date_df
                return None

            mock_data_service.fetch_single_timeframe.side_effect = fetch_side_effect

            with patch('scripts.collect_training_data.IndicatorService') as mock_is:
                mock_indicator_service = mock_is.return_value
                mock_indicator_service.compute_indicators.side_effect = lambda df: df

                with patch('scripts.collect_training_data.SignalService') as mock_ss, \
                     patch('scripts.collect_training_data.VerdictService') as mock_vs, \
                     patch('scripts.collect_training_data.calculate_all_dip_features', return_value={}):

                    features = extract_features_at_date(
                        ticker="TEST.NS",
                        entry_date=entry_date,
                        data_service=mock_data_service,
                        indicator_service=mock_indicator_service,
                        signal_service=mock_ss.return_value,
                        verdict_service=mock_vs.return_value
                    )

                    # Verify features use signal_date data, not entry_date data
                    if features:
                        # Should use signal_date RSI (28.84), not entry_date RSI (26.53)
                        assert features.get('rsi_10') == 28.84, \
                            "Features should use signal_date RSI, not entry_date RSI"

    def test_entry_date_preserved_in_features(self):
        """Test that entry_date is still preserved in features dict"""
        entry_date = "2024-11-11"

        with patch('scripts.collect_training_data.IndicatorService') as mock_is:
            mock_indicator_service = mock_is.return_value
            mock_df = self._create_mock_dataframe()
            mock_indicator_service.compute_indicators.return_value = mock_df

            with patch('scripts.collect_training_data.SignalService') as mock_ss, \
                 patch('scripts.collect_training_data.VerdictService') as mock_vs, \
                 patch('scripts.collect_training_data.calculate_all_dip_features', return_value={}), \
                 patch('core.data_fetcher.fetch_ohlcv_yf', return_value=mock_df):

                features = extract_features_at_date(
                    ticker="TEST.NS",
                    entry_date=entry_date,
                    data_service=Mock(),
                    indicator_service=mock_indicator_service,
                    signal_service=mock_ss.return_value,
                    verdict_service=mock_vs.return_value
                )

                # entry_date should be in features (for tracking)
                assert features is not None
                assert features.get('entry_date') == entry_date, \
                    "entry_date should be preserved in features dict"

    def test_weekend_skipping_saturday(self):
        """Test that Saturday signal_date is adjusted to Friday"""
        # If entry_date - 1 = Saturday, should use Friday
        entry_date = "2024-11-10"  # Sunday
        expected_signal_date = "2024-11-08"  # Friday (skip Sat & Sun)

        with patch('scripts.collect_training_data.IndicatorService') as mock_is:
            mock_indicator_service = mock_is.return_value
            mock_df = self._create_mock_dataframe()
            mock_indicator_service.compute_indicators.return_value = mock_df

            with patch('scripts.collect_training_data.SignalService') as mock_ss, \
                 patch('scripts.collect_training_data.VerdictService') as mock_vs, \
                 patch('core.data_fetcher.fetch_ohlcv_yf', return_value=mock_df) as mock_fetch:

                extract_features_at_date(
                    ticker="TEST.NS",
                    entry_date=entry_date,
                    data_service=Mock(),
                    indicator_service=mock_indicator_service,
                    signal_service=mock_ss.return_value,
                    verdict_service=mock_vs.return_value
                )

                call_args = mock_fetch.call_args
                assert call_args[1]['end_date'] == expected_signal_date

    def test_no_lookahead_for_multiple_dates(self):
        """Test signal_date calculation for various entry dates"""
        test_cases = [
            ("2024-11-11", "2024-11-08"),  # Mon -> Fri
            ("2024-11-12", "2024-11-11"),  # Tue -> Mon
            ("2024-11-13", "2024-11-12"),  # Wed -> Tue
            ("2024-11-14", "2024-11-13"),  # Thu -> Wed
            ("2024-11-15", "2024-11-14"),  # Fri -> Thu
        ]

        for entry_date, expected_signal_date in test_cases:
            with patch('scripts.collect_training_data.IndicatorService') as mock_is:
                mock_indicator_service = mock_is.return_value
                mock_df = self._create_mock_dataframe()
                mock_indicator_service.compute_indicators.return_value = mock_df

                with patch('scripts.collect_training_data.SignalService') as mock_ss, \
                     patch('scripts.collect_training_data.VerdictService') as mock_vs, \
                     patch('core.data_fetcher.fetch_ohlcv_yf', return_value=mock_df) as mock_fetch:

                    extract_features_at_date(
                        ticker="TEST.NS",
                        entry_date=entry_date,
                        data_service=Mock(),
                        indicator_service=mock_indicator_service,
                        signal_service=mock_ss.return_value,
                        verdict_service=mock_vs.return_value
                    )

                    call_args = mock_fetch.call_args
                    actual_signal_date = call_args[1]['end_date']

                    assert actual_signal_date == expected_signal_date, \
                        f"Entry {entry_date}: expected signal {expected_signal_date}, got {actual_signal_date}"

    # Helper method
    def _create_mock_dataframe(self, close_price=1278.64, volume=19814406, rsi=28.84):
        """Create a mock DataFrame with indicators"""
        dates = pd.date_range(end='2024-11-08', periods=50)
        df = pd.DataFrame({
            'open': [close_price] * 50,
            'high': [close_price * 1.01] * 50,
            'low': [close_price * 0.99] * 50,
            'close': [close_price] * 50,
            'volume': [volume] * 50,
            'rsi10': [rsi] * 50,
            'ema200': [close_price * 0.98] * 50,
        }, index=dates)
        return df

