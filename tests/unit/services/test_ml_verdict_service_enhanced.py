#!/usr/bin/env python3
"""
Unit tests for ML verdict service enhanced features (Phase 5).

Tests that MLVerdictService correctly uses new dip features for predictions.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from unittest.mock import Mock, patch
import numpy as np

from services.ml_verdict_service import MLVerdictService


class TestMLDipFeaturesExtraction:
    """Test that ML service extracts new dip features correctly"""
    
    def test_extract_features_includes_dip_features(self):
        """Test that _extract_features includes all new dip features"""
        service = MLVerdictService()
        
        # Create indicators dict with new dip features (as they come from analysis_service)
        indicators = {
            'close': 1000.0,
            'rsi': 25.0,
            'ema200': 950.0,
            'dip_depth_from_20d_high_pct': 15.5,
            'consecutive_red_days': 6,
            'dip_speed_pct_per_day': 2.3,
            'decline_rate_slowing': True,
            'volume_green_vs_red_ratio': 1.6,
            'support_hold_count': 3
        }
        
        features = service._extract_features(
            signals=['rsi_oversold'],
            rsi_value=25.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=True,
            fundamental_ok=True,
            timeframe_confirmation={'alignment_score': 7},
            news_sentiment=None,
            indicators=indicators
        )
        
        # Verify all new dip features are present
        assert 'dip_depth_from_20d_high_pct' in features
        assert 'consecutive_red_days' in features
        assert 'dip_speed_pct_per_day' in features
        assert 'decline_rate_slowing' in features
        assert 'volume_green_vs_red_ratio' in features
        assert 'support_hold_count' in features
        
        # Verify values are correctly extracted
        assert features['dip_depth_from_20d_high_pct'] == 15.5
        assert features['consecutive_red_days'] == 6.0  # Converted to float for ML
        assert features['dip_speed_pct_per_day'] == 2.3
        assert features['decline_rate_slowing'] == 1.0  # Boolean -> 1.0/0.0
        assert features['volume_green_vs_red_ratio'] == 1.6
        assert features['support_hold_count'] == 3.0
    
    def test_extract_features_uses_defaults_when_missing(self):
        """Test that ML service uses default values when dip features are missing"""
        service = MLVerdictService()
        
        # Indicators without new dip features (backward compatible)
        indicators = {
            'close': 1000.0,
            'rsi': 25.0,
            'ema200': 950.0
        }
        
        features = service._extract_features(
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
        
        # Should use default values
        assert features['dip_depth_from_20d_high_pct'] == 0.0
        assert features['consecutive_red_days'] == 0.0
        assert features['dip_speed_pct_per_day'] == 0.0
        assert features['decline_rate_slowing'] == 0.0
        assert features['volume_green_vs_red_ratio'] == 1.0
        assert features['support_hold_count'] == 0.0
    
    def test_extract_features_handles_no_indicators(self):
        """Test that ML service handles missing indicators dict"""
        service = MLVerdictService()
        
        features = service._extract_features(
            signals=[],
            rsi_value=None,
            is_above_ema200=False,
            vol_ok=False,
            vol_strong=False,
            fundamental_ok=True,
            timeframe_confirmation=None,
            news_sentiment=None,
            indicators=None  # No indicators provided
        )
        
        # Should use defaults for all dip features
        assert 'dip_depth_from_20d_high_pct' in features
        assert features['dip_depth_from_20d_high_pct'] == 0.0
        assert features['volume_green_vs_red_ratio'] == 1.0
    
    def test_decline_rate_slowing_boolean_conversion(self):
        """Test that boolean decline_rate_slowing is converted to 1.0/0.0 for ML"""
        service = MLVerdictService()
        
        # Test with True
        indicators_true = {'decline_rate_slowing': True}
        features_true = service._extract_features(
            signals=[], rsi_value=30.0, is_above_ema200=True,
            vol_ok=True, vol_strong=False, fundamental_ok=True,
            timeframe_confirmation=None, news_sentiment=None,
            indicators=indicators_true
        )
        assert features_true['decline_rate_slowing'] == 1.0
        
        # Test with False
        indicators_false = {'decline_rate_slowing': False}
        features_false = service._extract_features(
            signals=[], rsi_value=30.0, is_above_ema200=True,
            vol_ok=True, vol_strong=False, fundamental_ok=True,
            timeframe_confirmation=None, news_sentiment=None,
            indicators=indicators_false
        )
        assert features_false['decline_rate_slowing'] == 0.0
    
    def test_feature_types_for_ml(self):
        """Test that all features have correct types for ML (float)"""
        service = MLVerdictService()
        
        indicators = {
            'close': 1000.0,
            'dip_depth_from_20d_high_pct': 12,  # int
            'consecutive_red_days': 5,  # int
            'dip_speed_pct_per_day': 1.8,  # float
            'decline_rate_slowing': True,  # bool
            'volume_green_vs_red_ratio': 1.4,  # float
            'support_hold_count': 2  # int
        }
        
        features = service._extract_features(
            signals=[], rsi_value=25.0, is_above_ema200=True,
            vol_ok=True, vol_strong=True, fundamental_ok=True,
            timeframe_confirmation=None, news_sentiment=None,
            indicators=indicators
        )
        
        # All features should be float for ML model
        assert isinstance(features['dip_depth_from_20d_high_pct'], float)
        assert isinstance(features['consecutive_red_days'], float)
        assert isinstance(features['dip_speed_pct_per_day'], float)
        assert isinstance(features['decline_rate_slowing'], float)  # 0.0 or 1.0
        assert isinstance(features['volume_green_vs_red_ratio'], float)
        assert isinstance(features['support_hold_count'], float)

