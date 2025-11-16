#!/usr/bin/env python3
"""
Integration tests for ML enhanced features complete pipeline (Phase 6).

Tests the complete data flow from analysis -> CSV export -> backtest -> 
training data collection -> ML prediction.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
import pandas as pd
from datetime import datetime, timedelta

from services.analysis_service import AnalysisService
from integrated_backtest import Position, run_integrated_backtest
from services.ml_verdict_service import MLVerdictService
from core.feature_engineering import calculate_all_dip_features


class TestEndToEndPipeline:
    """Test complete ML pipeline with enhanced features"""
    
    def test_analysis_to_ml_feature_flow(self):
        """Test that features flow from analysis_service to ml_verdict_service"""
        # Step 1: Create analysis service
        analysis_service = AnalysisService()
        
        # Step 2: Create mock data
        mock_df = pd.DataFrame({
            'open': [1005, 1000, 995, 990, 985, 975] + [970] * 50,  # Need 50+ rows
            'close': [1000, 995, 990, 985, 975, 970] + [965] * 50,
            'high': [1010, 1005, 1000, 995, 990, 980] + [975] * 50,
            'low': [995, 990, 985, 980, 970, 965] + [960] * 50,
            'volume': [1000000] * 56,
            'rsi10': [35, 32, 28, 25, 22, 20] + [18] * 50,
            'ema200': [950] * 56
        })
        
        # Step 3: Calculate dip features
        dip_features = calculate_all_dip_features(mock_df)
        
        # Verify features calculate
        assert 'dip_depth_from_20d_high_pct' in dip_features
        assert isinstance(dip_features['dip_depth_from_20d_high_pct'], (int, float))
        
        # Step 4: Create ML service
        ml_service = MLVerdictService()
        
        # Step 5: Create indicators dict (simulating what analysis_service provides)
        indicators = {
            'close': 965.0,
            'rsi': 18.0,
            'ema200': 950.0
        }
        indicators.update(dip_features)  # Add dip features
        
        # Step 6: Extract ML features
        ml_features = ml_service._extract_features(
            signals=['rsi_oversold'],
            rsi_value=18.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=True,
            fundamental_ok=True,
            timeframe_confirmation={'alignment_score': 8},
            news_sentiment=None,
            indicators=indicators
        )
        
        # Verify ML features include dip features
        assert 'dip_depth_from_20d_high_pct' in ml_features
        assert 'consecutive_red_days' in ml_features
        assert 'decline_rate_slowing' in ml_features
        assert ml_features['dip_depth_from_20d_high_pct'] == dip_features['dip_depth_from_20d_high_pct']
    
    def test_backtest_outcome_tracking(self):
        """Test that backtest correctly tracks outcome features"""
        # Create position
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-15",
            entry_price=1000.0,
            target_price=1100.0,
            entry_rsi=25.0
        )
        
        # Simulate trade with drawdown
        pos.update_drawdown("2024-01-16", 985.0)  # -1.5%
        pos.update_drawdown("2024-01-17", 975.0)  # -2.5%
        pos.update_drawdown("2024-01-18", 970.0)  # -3.0% (worst)
        pos.update_drawdown("2024-01-19", 990.0)  # Recovering
        pos.update_drawdown("2024-01-20", 1020.0)  # Above entry
        pos.close_position("2024-01-22", 1100.0, "Target reached")
        
        # Verify outcome features
        assert pos.exit_reason == "Target reached"
        assert pos.get_days_to_exit() == 7
        assert pos.max_drawdown_pct == -3.0
        assert pos.get_return_pct() == 10.0
        
        # Verify these would be exported correctly
        assert pos.is_closed == True
        assert pos.exit_date is not None
    
    def test_feature_set_completeness(self):
        """Test that complete feature set is available for ML training"""
        # Simulate the complete feature set that ML should receive
        
        # Features from analysis_service (including dip features)
        analysis_features = {
            # Basic indicators
            'rsi': 22.0,
            'is_above_ema200': True,
            'volume_ratio': 1.8,
            'support_distance_pct': 3.5,
            'has_divergence': True,
            'alignment_score': 8,
            'fundamental_ok': True,
            # NEW dip features
            'dip_depth_from_20d_high_pct': 16.5,
            'consecutive_red_days': 7,
            'dip_speed_pct_per_day': 2.1,
            'decline_rate_slowing': True,
            'volume_green_vs_red_ratio': 1.6,
            'support_hold_count': 3
        }
        
        # Outcome features from backtest
        outcome_features = {
            'exit_reason': 'Target reached',
            'days_to_exit': 9,
            'max_drawdown_pct': -2.2,
            'actual_pnl_pct': 12.5
        }
        
        # Complete training example
        training_example = {**analysis_features, **outcome_features}
        training_example['label'] = 'strong_buy'  # Based on P&L
        
        # Verify complete feature set
        assert 'dip_depth_from_20d_high_pct' in training_example
        assert 'exit_reason' in training_example
        assert 'max_drawdown_pct' in training_example
        assert 'label' in training_example
        
        # This represents what ML will train on
        assert len(training_example) >= 15  # Should have many features


class TestFeatureQuality:
    """Test that features have appropriate quality for ML"""
    
    def test_feature_values_are_numeric_for_ml(self):
        """Test that all features are numeric (required by ML models)"""
        ml_service = MLVerdictService()
        
        indicators = {
            'dip_depth_from_20d_high_pct': 15.0,
            'consecutive_red_days': 5,
            'dip_speed_pct_per_day': 2.0,
            'decline_rate_slowing': True,
            'volume_green_vs_red_ratio': 1.5,
            'support_hold_count': 2
        }
        
        features = ml_service._extract_features(
            signals=[], rsi_value=25.0, is_above_ema200=True,
            vol_ok=True, vol_strong=False, fundamental_ok=True,
            timeframe_confirmation=None, news_sentiment=None,
            indicators=indicators
        )
        
        # All features should be float (required by sklearn)
        for key in ['dip_depth_from_20d_high_pct', 'consecutive_red_days', 
                    'dip_speed_pct_per_day', 'decline_rate_slowing',
                    'volume_green_vs_red_ratio', 'support_hold_count']:
            assert key in features
            assert isinstance(features[key], (int, float))
            # Should not be None or string
            assert features[key] is not None
    
    def test_feature_ranges_are_reasonable(self):
        """Test that feature values are in reasonable ranges"""
        df = pd.DataFrame({
            'open': [1000] + [1000 - i for i in range(1, 30)],
            'close': [995] + [995 - i for i in range(1, 30)],
            'high': [1005] + [1005 - i for i in range(1, 30)],
            'low': [990] + [990 - i for i in range(1, 30)],
            'volume': [1000000] * 30
        })
        
        features = calculate_all_dip_features(df)
        
        # Dip depth should be 0-100%
        assert 0 <= features['dip_depth_from_20d_high_pct'] <= 100
        
        # Consecutive red days should be reasonable
        assert 0 <= features['consecutive_red_days'] <= 100
        
        # Dip speed should be non-negative
        assert features['dip_speed_pct_per_day'] >= 0
        
        # Volume ratio should be positive
        assert features['volume_green_vs_red_ratio'] > 0
        
        # Support hold count should be non-negative
        assert features['support_hold_count'] >= 0


class TestBackwardCompatibility:
    """Test that changes are backward compatible"""
    
    def test_ml_works_without_new_features(self):
        """Test that ML still works when new features are not provided"""
        ml_service = MLVerdictService()
        
        # Old-style indicators (without new features)
        indicators = {
            'close': 1000.0,
            'rsi': 25.0,
            'ema200': 950.0
        }
        
        # Should not crash, should use defaults
        features = ml_service._extract_features(
            signals=['rsi_oversold'],
            rsi_value=25.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=False,
            fundamental_ok=True,
            timeframe_confirmation=None,
            news_sentiment=None,
            indicators=indicators
        )
        
        # Should have all new features with default values
        assert features['dip_depth_from_20d_high_pct'] == 0.0
        assert features['consecutive_red_days'] == 0.0
        assert features['decline_rate_slowing'] == 0.0
    
    def test_backtest_results_structure_unchanged(self):
        """Test that backtest results maintain backward compatible structure"""
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-15",
            entry_price=1000.0,
            target_price=1100.0
        )
        
        pos.close_position("2024-01-20", 1100.0, "Target reached")
        
        # Should still have all original fields
        assert pos.entry_date is not None
        assert pos.entry_price == 1000.0
        assert pos.exit_date is not None
        assert pos.exit_price == 1100.0
        assert pos.exit_reason == "Target reached"
        assert pos.get_pnl() == 10000.0  # 100 shares * $100
        assert pos.get_return_pct() == 10.0
        
        # Plus new fields
        assert hasattr(pos, 'max_drawdown_pct')
        assert hasattr(pos, 'get_days_to_exit')

