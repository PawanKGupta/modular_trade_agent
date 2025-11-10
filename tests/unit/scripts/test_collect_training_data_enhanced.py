#!/usr/bin/env python3
"""
Unit tests for enhanced training data collection (Phase 4).

Tests that new dip features and outcome features are correctly extracted
during training data collection.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
import pandas as pd
from unittest.mock import Mock, patch

# Import the functions we need to test
# Note: We'll use string path for importing to avoid circular dependencies
sys.path.insert(0, str(project_root / 'scripts'))


class TestEnhancedFeatureExtraction:
    """Test that new features are extracted during training data collection"""
    
    def test_extract_features_includes_dip_features(self):
        """Test that extract_features_at_date includes new dip features"""
        from collect_training_data import extract_features_at_date
        
        # Create mock services
        mock_data = Mock()
        mock_indicator = Mock()
        mock_signal = Mock()
        mock_verdict = Mock()
        
        # Create sample DataFrame with dip pattern (need at least 50 rows)
        n_rows = 60
        base_price = 1000
        prices = [base_price - i * 2 for i in range(n_rows)]  # Gradual decline
        
        df = pd.DataFrame({
            'close': prices,
            'open': [p + 5 for p in prices],
            'high': [p + 10 for p in prices],
            'low': [p - 5 for p in prices],
            'volume': [1000000] * n_rows,
            'rsi10': [max(10, 40 - i * 0.5) for i in range(n_rows)],  # Declining RSI
            'ema200': [900] * n_rows
        })
        
        # Configure mocks
        mock_data.fetch_single_timeframe.return_value = df
        mock_indicator.compute_indicators.return_value = df
        mock_signal.detect_pattern_signals.return_value = []
        mock_verdict.fetch_fundamentals.return_value = {'pe': 15, 'pb': 2}
        
        # Extract features
        features = extract_features_at_date(
            ticker='TEST.NS',
            entry_date='2024-01-15',
            data_service=mock_data,
            indicator_service=mock_indicator,
            signal_service=mock_signal,
            verdict_service=mock_verdict
        )
        
        # Verify new dip features are present
        assert features is not None
        assert 'dip_depth_from_20d_high_pct' in features
        assert 'consecutive_red_days' in features
        assert 'dip_speed_pct_per_day' in features
        assert 'decline_rate_slowing' in features
        assert 'volume_green_vs_red_ratio' in features
        assert 'support_hold_count' in features
    
    def test_extract_features_handles_dip_calculation_error(self):
        """Test that feature extraction handles dip calculation errors gracefully"""
        from collect_training_data import extract_features_at_date
        
        mock_data = Mock()
        mock_indicator = Mock()
        mock_signal = Mock()
        mock_verdict = Mock()
        
        # Create minimal DataFrame that meets minimum size but might cause calculation issues
        df = pd.DataFrame({
            'close': [100] * 55,  # Meets minimum but all same price
            'open': [100] * 55,
            'high': [105] * 55,
            'low': [95] * 55,
            'volume': [1000000] * 55,
            'rsi10': [50] * 55,
            'ema200': [95] * 55
        })
        
        mock_data.fetch_single_timeframe.return_value = df
        mock_indicator.compute_indicators.return_value = df
        mock_signal.detect_pattern_signals.return_value = []
        mock_verdict.fetch_fundamentals.return_value = {'pe': None, 'pb': None}
        
        # Should not crash, should calculate features even with minimal data
        features = extract_features_at_date(
            ticker='TEST.NS',
            entry_date='2024-01-15',
            data_service=mock_data,
            indicator_service=mock_indicator,
            signal_service=mock_signal,
            verdict_service=mock_verdict
        )
        
        # Should have dip features (might be calculated or defaults)
        assert features is not None
        assert 'dip_depth_from_20d_high_pct' in features
        assert 'consecutive_red_days' in features
        assert isinstance(features['dip_depth_from_20d_high_pct'], (int, float))
        assert isinstance(features['consecutive_red_days'], int)


class TestEnhancedLabelCreation:
    """Test that outcome features are extracted from backtest results"""
    
    def test_label_creation_includes_outcome_features(self):
        """Test that labels include exit_reason, max_drawdown, days_to_exit"""
        from collect_training_data import create_labels_from_backtest_results
        
        # Create backtest results with positions including outcome features
        backtest_results = {
            'ticker': 'TEST.NS',
            'full_results': {
                'positions': [
                    {
                        'entry_date': '2024-01-15',
                        'exit_date': '2024-01-22',
                        'return_pct': 12.5,
                        'exit_reason': 'Target reached',
                        'days_to_exit': 7,
                        'max_drawdown_pct': -2.3
                    }
                ]
            }
        }
        
        with patch('collect_training_data.extract_features_at_date') as mock_extract:
            # Mock the feature extraction
            mock_extract.return_value = {
                'rsi_10': 22.0,
                'price': 1000.0,
                'volume_ratio': 1.5,
                'dip_depth_from_20d_high_pct': 15.0,
                'consecutive_red_days': 5
            }
            
            # Create labels
            labels = create_labels_from_backtest_results(backtest_results)
            
            # Verify outcome features are included
            assert len(labels) == 1
            label_data = labels[0]
            
            assert 'exit_reason' in label_data
            assert label_data['exit_reason'] == 'Target reached'
            assert 'max_drawdown_pct' in label_data
            assert label_data['max_drawdown_pct'] == -2.3
            assert 'holding_days' in label_data
            assert label_data['holding_days'] == 7
    
    def test_label_creation_handles_missing_outcome_features(self):
        """Test that label creation handles missing outcome features gracefully"""
        from collect_training_data import create_labels_from_backtest_results
        
        # Old backtest results without outcome features
        backtest_results = {
            'ticker': 'TEST.NS',
            'full_results': {
                'positions': [
                    {
                        'entry_date': '2024-01-15',
                        'exit_date': '2024-01-22',
                        'return_pct': 8.0
                        # No exit_reason, days_to_exit, max_drawdown_pct
                    }
                ]
            }
        }
        
        with patch('collect_training_data.extract_features_at_date') as mock_extract:
            mock_extract.return_value = {
                'rsi_10': 25.0,
                'price': 1000.0
            }
            
            labels = create_labels_from_backtest_results(backtest_results)
            
            # Should use defaults for missing features
            assert len(labels) == 1
            assert 'exit_reason' in labels[0]
            assert labels[0]['exit_reason'] == 'Unknown'  # Default
            assert labels[0]['max_drawdown_pct'] == 0.0  # Default
    
    def test_training_data_completeness(self):
        """Test that training data has all expected features"""
        from collect_training_data import create_labels_from_backtest_results
        
        # Complete backtest results with all features
        backtest_results = {
            'ticker': 'TEST.NS',
            'full_results': {
                'positions': [
                    {
                        'entry_date': '2024-01-15',
                        'exit_date': '2024-01-25',
                        'return_pct': 15.0,
                        'exit_reason': 'Target reached',
                        'days_to_exit': 10,
                        'max_drawdown_pct': -1.5
                    }
                ]
            }
        }
        
        with patch('collect_training_data.extract_features_at_date') as mock_extract:
            # Mock complete feature set
            mock_extract.return_value = {
                # Basic features
                'rsi_10': 20.0,
                'price': 1000.0,
                'price_above_ema200': True,
                # Dip features (new)
                'dip_depth_from_20d_high_pct': 18.0,
                'consecutive_red_days': 7,
                'dip_speed_pct_per_day': 2.1,
                'decline_rate_slowing': True,
                'volume_green_vs_red_ratio': 1.6,
                'support_hold_count': 3,
                # Other features
                'volume_ratio': 2.0,
                'has_divergence': True
            }
            
            labels = create_labels_from_backtest_results(backtest_results)
            
            assert len(labels) == 1
            training_example = labels[0]
            
            # Verify all feature categories are present
            assert 'dip_depth_from_20d_high_pct' in training_example  # Dip features
            assert 'consecutive_red_days' in training_example
            assert 'exit_reason' in training_example  # Outcome features
            assert 'max_drawdown_pct' in training_example
            assert 'holding_days' in training_example
            assert 'label' in training_example  # Label
            assert 'actual_pnl_pct' in training_example  # Actual outcome

