#!/usr/bin/env python3
"""
Unit tests for AnalysisService ML enhanced dip features integration (Phase 2).

Tests that new dip-buying features are correctly calculated and included in analysis results.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
import pandas as pd
from unittest.mock import Mock, patch

from services.analysis_service import AnalysisService
from core.feature_engineering import calculate_all_dip_features


class TestDipFeaturesCalculation:
    """Test that dip features calculate correctly on sample data"""

    def test_dip_features_on_dip_pattern(self):
        """Test feature calculation on typical dip pattern"""
        # Create dip pattern: start high, then decline
        df = pd.DataFrame({
            'open': [1005, 1000, 995, 990, 985, 975, 970, 965, 960, 955, 950],
            'close': [1000, 995, 990, 985, 975, 970, 965, 960, 955, 950, 945],  # Declining
            'high': [1010, 1005, 1000, 995, 990, 980, 975, 970, 965, 960, 955],  # Declining highs
            'low': [995, 990, 985, 980, 970, 965, 960, 955, 950, 945, 940],
            'volume': [1000000] * 11
        })

        features = calculate_all_dip_features(df)

        # Verify all features calculate and return valid types
        assert isinstance(features['dip_depth_from_20d_high_pct'], (int, float))
        assert features['dip_depth_from_20d_high_pct'] >= 0  # Should be non-negative
        assert isinstance(features['consecutive_red_days'], int)
        assert features['consecutive_red_days'] >= 0
        assert isinstance(features['dip_speed_pct_per_day'], (int, float))
        assert features['dip_speed_pct_per_day'] >= 0
        assert isinstance(features['decline_rate_slowing'], bool)
        assert isinstance(features['volume_green_vs_red_ratio'], (int, float))
        assert features['volume_green_vs_red_ratio'] > 0
        assert isinstance(features['support_hold_count'], int)
        assert features['support_hold_count'] >= 0

    def test_dip_features_on_uptrend(self):
        """Test features on uptrending stock (no dip)"""
        df = pd.DataFrame({
            'open': [1000, 1010, 1020, 1030, 1040],
            'close': [1005, 1015, 1025, 1035, 1045],
            'high': [1010, 1020, 1030, 1040, 1050],
            'low': [995, 1005, 1015, 1025, 1035],
            'volume': [1000000] * 5
        })

        features = calculate_all_dip_features(df)

        # No dip scenario
        assert features['dip_depth_from_20d_high_pct'] == 0.0  # Price at high
        assert features['consecutive_red_days'] == 0  # All green
        assert features['dip_speed_pct_per_day'] == 0.0  # No decline

    def test_dip_features_with_insufficient_data(self):
        """Test features handle insufficient data gracefully"""
        df = pd.DataFrame({
            'open': [1000],
            'close': [995],
            'high': [1005],
            'low': [990],
            'volume': [1000000]
        })

        # Should not crash, return defaults
        features = calculate_all_dip_features(df)

        assert 'dip_depth_from_20d_high_pct' in features
        assert 'consecutive_red_days' in features
        assert isinstance(features, dict)


class TestAnalysisServiceIntegration:
    """Integration tests for AnalysisService with dip features"""

    @patch('services.analysis_service.VerdictService')
    @patch('services.analysis_service.SignalService')
    @patch('services.analysis_service.IndicatorService')
    @patch('services.analysis_service.DataService')
    def test_analyze_ticker_includes_dip_features(
        self,
        mock_data_class,
        mock_indicator_class,
        mock_signal_class,
        mock_verdict_class
    ):
        """Test that analyze_ticker includes dip features in result"""
        # Create simple mock DataFrame
        mock_df = pd.DataFrame({
            'open': [1000, 990, 980, 970, 960],
            'close': [995, 985, 975, 965, 955],
            'high': [1005, 995, 985, 975, 965],
            'low': [990, 980, 970, 960, 950],
            'volume': [1000000] * 5,
            'rsi10': [35.0, 30.0, 25.0, 22.0, 20.0],
            'ema200': [950.0] * 5
        })

        # Setup mock instances
        mock_data = mock_data_class.return_value
        mock_indicator = mock_indicator_class.return_value
        mock_signal = mock_signal_class.return_value
        mock_verdict = mock_verdict_class.return_value

        # Configure mocks
        mock_data.fetch_single_timeframe.return_value = mock_df
        mock_data.clip_to_date.return_value = mock_df
        mock_data.get_latest_row.return_value = mock_df.iloc[-1]
        mock_data.get_previous_row.return_value = mock_df.iloc[-2] if len(mock_df) >= 2 else None
        mock_data.get_recent_extremes.return_value = {'high': 1005.0, 'low': 950.0}

        mock_indicator.compute_indicators.return_value = mock_df
        mock_indicator.get_rsi_value.return_value = 20.0
        mock_indicator.is_above_ema200.return_value = True

        mock_signal.detect_all_signals.return_value = {
            'signals': ['rsi_oversold'],
            'timeframe_confirmation': {'alignment_score': 7},
            'news_sentiment': None
        }

        mock_verdict.fetch_fundamentals.return_value = {'pe': 15.0, 'pb': 2.0}
        mock_verdict.assess_fundamentals.return_value = {'fundamental_ok': True, 'reason': 'Good fundamentals'}
        mock_verdict.assess_chart_quality.return_value = {'passed': True, 'reason': 'Good quality'}
        mock_verdict.assess_volume.return_value = {
                'avg_vol': 1000000,
                'today_vol': 1500000,
                'vol_ok': True,
                'vol_strong': True,
                'volume_analysis': {'quality': 'good'},
                'volume_pattern': 'accumulation',
                'volume_description': 'Strong buying volume'
        }
        mock_verdict.determine_verdict.return_value = ('strong_buy', ['Strong reversal setup'])
        mock_verdict.calculate_trading_parameters.return_value = {
                'buy_range': (950, 960),
                'target': 1050,
                'stop': 900
            }
        mock_verdict.apply_candle_quality_check.return_value = ('strong_buy', 'Bullish reversal', None)

        # Patch calculate_all_dip_features to return proper values
        with patch('services.analysis_service.calculate_all_dip_features') as mock_calc:
            mock_calc.return_value = {
                'dip_depth_from_20d_high_pct': 10.0,
                'consecutive_red_days': 5,
                'dip_speed_pct_per_day': 2.0,
                'decline_rate_slowing': True,
                'volume_green_vs_red_ratio': 1.5,
                'support_hold_count': 3
            }

            # Create service (will use mocked dependencies)
            service = AnalysisService()

            # Analyze
            result = service.analyze_ticker('TEST.NS', enable_multi_timeframe=False)

            # Verify dip features are in result
            assert 'dip_depth_from_20d_high_pct' in result
            assert 'consecutive_red_days' in result
            assert 'dip_speed_pct_per_day' in result
            assert 'decline_rate_slowing' in result
            assert 'volume_green_vs_red_ratio' in result
            assert 'support_hold_count' in result

            # Verify types
            assert isinstance(result['dip_depth_from_20d_high_pct'], (int, float))
            assert isinstance(result['consecutive_red_days'], int)
            assert isinstance(result['dip_speed_pct_per_day'], (int, float))
            assert isinstance(result['decline_rate_slowing'], bool)
            assert isinstance(result['volume_green_vs_red_ratio'], (int, float))
            assert isinstance(result['support_hold_count'], int)

    def test_dip_features_calculation_function_called(self):
        """Test that calculate_all_dip_features is called during analysis"""
        with patch('services.analysis_service.calculate_all_dip_features') as mock_calc:
            # Set return value for the mock
            mock_calc.return_value = {
                'dip_depth_from_20d_high_pct': 10.0,
                'consecutive_red_days': 5,
                'dip_speed_pct_per_day': 2.0,
                'decline_rate_slowing': True,
                'volume_green_vs_red_ratio': 1.5,
                'support_hold_count': 3
            }

            # Create mock DataFrame
            mock_df = pd.DataFrame({
                'open': [100] * 5,
                'close': [100] * 5,
                'high': [105] * 5,
                'low': [95] * 5,
                'volume': [1000000] * 5,
                'rsi10': [25.0] * 5,
                'ema200': [95.0] * 5
            })

            with patch('services.analysis_service.DataService') as mock_data_class:
                with patch('services.analysis_service.IndicatorService') as mock_indicator_class:
                    with patch('services.analysis_service.SignalService') as mock_signal_class:
                        with patch('services.analysis_service.VerdictService') as mock_verdict_class:
                            # Setup mocks
                            mock_data = mock_data_class.return_value
                            mock_indicator = mock_indicator_class.return_value
                            mock_signal = mock_signal_class.return_value
                            mock_verdict = mock_verdict_class.return_value

                            mock_data.fetch_single_timeframe.return_value = mock_df
                            mock_data.clip_to_date.return_value = mock_df
                            mock_data.get_latest_row.return_value = mock_df.iloc[-1]
                            mock_data.get_previous_row.return_value = mock_df.iloc[-2]
                            mock_data.get_recent_extremes.return_value = {'high': 105, 'low': 95}

                            mock_indicator.compute_indicators.return_value = mock_df
                            mock_indicator.get_rsi_value.return_value = 25.0
                            mock_indicator.is_above_ema200.return_value = True

                            mock_signal.detect_all_signals.return_value = {
                                'signals': ['rsi_oversold'],
                                'timeframe_confirmation': {'alignment_score': 7},
                                'news_sentiment': None
                            }

                            mock_verdict.fetch_fundamentals.return_value = {'pe': 15, 'pb': 2}
                            mock_verdict.assess_fundamentals.return_value = {'fundamental_ok': True, 'reason': 'Good'}
                            mock_verdict.assess_chart_quality.return_value = {'passed': True, 'reason': 'Good'}
                            mock_verdict.assess_volume.return_value = {
                                    'avg_vol': 1000000,
                                    'today_vol': 1000000,
                                    'vol_ok': True,
                                    'vol_strong': False,
                                    'volume_analysis': {},
                                    'volume_pattern': 'normal',
                                    'volume_description': 'Normal'
                            }
                            mock_verdict.determine_verdict.return_value = ('buy', ['Test'])
                            mock_verdict.calculate_trading_parameters.return_value = None
                            mock_verdict.apply_candle_quality_check.return_value = ('buy', 'Neutral', None)

                            service = AnalysisService()
                            result = service.analyze_ticker('TEST.NS', enable_multi_timeframe=False)

                            # Verify function was called
                            mock_calc.assert_called_once()

                            # Verify result contains mocked values
                            assert result['dip_depth_from_20d_high_pct'] == 10.0
                            assert result['consecutive_red_days'] == 5
                            assert result['decline_rate_slowing'] == True
