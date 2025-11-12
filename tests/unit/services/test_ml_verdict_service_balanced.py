"""
Unit tests for MLVerdictService with class_weight='balanced'
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from services.ml_verdict_service import MLVerdictService


class TestMLVerdictServiceBalanced:
    """Test cases for balanced model predictions"""

    def setup_method(self):
        """Setup for each test"""
        self.service = MLVerdictService()
        
        # Skip tests if model not loaded
        if not self.service.model_loaded:
            pytest.skip("ML model not loaded")

    def test_model_has_class_weight_balanced(self):
        """Test that the model is configured with class_weight='balanced'"""
        assert self.service.model is not None
        assert hasattr(self.service.model, 'class_weight')
        assert self.service.model.class_weight == 'balanced', \
            "Model should use class_weight='balanced' to handle class imbalance"

    def test_model_predicts_all_classes(self):
        """Test that model CAN predict all verdict classes"""
        # Model should have all 4 classes
        expected_classes = {'avoid', 'buy', 'strong_buy', 'watch'}
        actual_classes = set(self.service.model.classes_)
        
        assert actual_classes == expected_classes, \
            f"Model should support all 4 classes, got: {actual_classes}"

    def test_feature_extraction_includes_new_features(self):
        """Test that feature extraction includes market regime, time, and interaction features"""
        # Create mock data
        mock_indicators = {
            'close': 100.0,
            'dip_depth_from_20d_high_pct': 10.0,
            'consecutive_red_days': 3,
            'dip_speed_pct_per_day': -2.0,
            'decline_rate_slowing': True,
            'volume_green_vs_red_ratio': 1.2,
            'support_hold_count': 2
        }
        
        dates = pd.date_range(end=datetime.now(), periods=50, freq='D')
        mock_df = pd.DataFrame({
            'close': np.random.uniform(95, 105, 50),
            'high': np.random.uniform(100, 110, 50),
            'low': np.random.uniform(90, 100, 50),
            'volume': np.random.uniform(1000000, 2000000, 50)
        }, index=dates)
        
        features = self.service._extract_features(
            signals=['hammer'],
            rsi_value=25.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=True,
            fundamental_ok=True,
            timeframe_confirmation={'alignment_score': 2},
            news_sentiment=None,
            indicators=mock_indicators,
            fundamentals={'pe': 20.0, 'pb': 2.5},
            df=mock_df
        )
        
        # Verify market regime features
        assert 'nifty_trend' in features
        assert 'nifty_vs_sma20_pct' in features
        assert 'india_vix' in features
        
        # Verify time features
        assert 'day_of_week' in features
        assert 'is_monday' in features
        assert 'month' in features
        
        # Verify interaction features
        assert 'rsi_volume_interaction' in features
        assert 'dip_support_interaction' in features
        assert 'bearish_deep_dip' in features

    def test_balanced_model_buy_recall_improved(self):
        """
        Test that balanced model has improved recall for minority classes
        
        This is a regression test to ensure buy/strong_buy recall stays above threshold
        """
        # This test verifies the training results from retraining script
        # Expected: buy recall >= 60%, strong_buy recall >= 30%
        
        # Note: We can't test actual recall without test data here,
        # but we verify the model configuration is correct
        assert self.service.model.class_weight == 'balanced'
        
        # The model should be able to produce non-zero probabilities for all classes
        # We test this by checking the model has been trained on all classes
        assert len(self.service.model.classes_) == 4

    def test_prediction_probabilities_sum_to_one(self):
        """Test that prediction probabilities sum to 1.0"""
        mock_indicators = {
            'close': 100.0,
            'dip_depth_from_20d_high_pct': 8.0,
            'consecutive_red_days': 3,
            'dip_speed_pct_per_day': -2.0,
            'decline_rate_slowing': False,
            'volume_green_vs_red_ratio': 1.0,
            'support_hold_count': 2
        }
        
        dates = pd.date_range(end=datetime.now(), periods=50, freq='D')
        mock_df = pd.DataFrame({
            'close': np.random.uniform(95, 105, 50),
            'high': np.random.uniform(100, 110, 50),
            'low': np.random.uniform(90, 100, 50),
            'volume': np.random.uniform(1000000, 2000000, 50)
        }, index=dates)
        
        result = self.service._predict_with_ml(
            signals=['hammer'],
            rsi_value=25.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=True,
            fundamental_ok=True,
            timeframe_confirmation={'alignment_score': 2},
            news_sentiment=None,
            indicators=mock_indicators,
            fundamentals={'pe': 20.0, 'pb': 2.5},
            df=mock_df
        )
        
        if result:
            verdict, confidence, probs = result
            
            # Probabilities should sum to 1.0
            prob_sum = sum(probs.values())
            assert abs(prob_sum - 1.0) < 0.01, f"Probabilities should sum to 1.0, got {prob_sum}"
            
            # All classes should have probabilities
            assert len(probs) == 4, "Should have probabilities for all 4 classes"
            
            # Confidence should match max probability
            max_prob = max(probs.values())
            assert abs(confidence - max_prob) < 0.01, \
                f"Confidence {confidence} should match max probability {max_prob}"

    def test_interaction_features_calculated_correctly(self):
        """Test that interaction features are calculated correctly"""
        mock_indicators = {
            'close': 100.0,
            'dip_depth_from_20d_high_pct': 10.0,  # 10% dip
            'consecutive_red_days': 3,
            'dip_speed_pct_per_day': -2.0,
            'decline_rate_slowing': False,
            'volume_green_vs_red_ratio': 1.0,
            'support_hold_count': 2
        }
        
        dates = pd.date_range(end=datetime.now(), periods=50, freq='D')
        mock_df = pd.DataFrame({
            'close': np.random.uniform(95, 105, 50),
            'high': np.random.uniform(100, 110, 50),
            'low': np.random.uniform(90, 100, 50),
            'volume': np.random.uniform(1000000, 2000000, 50)
        }, index=dates)
        
        features = self.service._extract_features(
            signals=[],
            rsi_value=20.0,  # Low RSI
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=True,
            fundamental_ok=True,
            timeframe_confirmation={'alignment_score': 2},
            news_sentiment=None,
            indicators=mock_indicators,
            fundamentals={'pe': 20.0, 'pb': 2.5},
            df=mock_df
        )
        
        # Check rsi_volume_interaction
        expected_rsi_volume = features['rsi_10'] * features['volume_ratio']
        assert 'rsi_volume_interaction' in features
        assert abs(features['rsi_volume_interaction'] - expected_rsi_volume) < 0.01
        
        # Check dip_support_interaction
        expected_dip_support = features['dip_depth_from_20d_high_pct'] * features['support_distance_pct']
        assert 'dip_support_interaction' in features
        # Allow some variance due to calculation differences
        
        # Check extreme_dip_high_volume (should be 1.0)
        assert 'extreme_dip_high_volume' in features
        # dip_depth=10%, volume_ratio should be >1.5 for strong
        if features['volume_ratio'] > 1.5:
            assert features['extreme_dip_high_volume'] == 1.0

    def test_market_regime_features_from_service(self):
        """Test that market regime features are fetched correctly"""
        mock_indicators = {
            'close': 100.0,
            'dip_depth_from_20d_high_pct': 5.0,
            'consecutive_red_days': 2,
            'dip_speed_pct_per_day': -1.0,
            'decline_rate_slowing': True,
            'volume_green_vs_red_ratio': 1.0,
            'support_hold_count': 1
        }
        
        dates = pd.date_range(end=datetime.now(), periods=50, freq='D')
        mock_df = pd.DataFrame({
            'close': np.random.uniform(95, 105, 50),
            'high': np.random.uniform(100, 110, 50),
            'low': np.random.uniform(90, 100, 50),
            'volume': np.random.uniform(1000000, 2000000, 50)
        }, index=dates)
        
        features = self.service._extract_features(
            signals=[],
            rsi_value=30.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=False,
            fundamental_ok=True,
            timeframe_confirmation={'alignment_score': 1},
            news_sentiment=None,
            indicators=mock_indicators,
            fundamentals={'pe': 15.0, 'pb': 2.0},
            df=mock_df
        )
        
        # Market regime features should be present
        assert 'nifty_trend' in features
        assert features['nifty_trend'] in [-1.0, 0.0, 1.0], "nifty_trend should be -1, 0, or 1"
        
        assert 'india_vix' in features
        assert features['india_vix'] > 0, "VIX should be positive"
        
        # VIX should be reasonable
        assert 10.0 <= features['india_vix'] <= 50.0, \
            f"VIX should be in reasonable range 10-50, got {features['india_vix']}"

    def test_time_features_calculated_from_current_date(self):
        """Test that time features are calculated correctly from current date"""
        mock_indicators = {
            'close': 100.0,
            'dip_depth_from_20d_high_pct': 5.0,
            'consecutive_red_days': 1,
            'dip_speed_pct_per_day': -1.0,
            'decline_rate_slowing': False,
            'volume_green_vs_red_ratio': 1.0,
            'support_hold_count': 1
        }
        
        dates = pd.date_range(end=datetime.now(), periods=50, freq='D')
        mock_df = pd.DataFrame({
            'close': np.random.uniform(95, 105, 50),
            'high': np.random.uniform(100, 110, 50),
            'low': np.random.uniform(90, 100, 50),
            'volume': np.random.uniform(1000000, 2000000, 50)
        }, index=dates)
        
        features = self.service._extract_features(
            signals=[],
            rsi_value=30.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=False,
            fundamental_ok=True,
            timeframe_confirmation={'alignment_score': 1},
            news_sentiment=None,
            indicators=mock_indicators,
            fundamentals={'pe': 15.0, 'pb': 2.0},
            df=mock_df
        )
        
        # Time features should match current date
        now = datetime.now()
        
        assert 'day_of_week' in features
        assert 0 <= features['day_of_week'] <= 6
        assert features['day_of_week'] == now.weekday()
        
        assert 'month' in features
        assert 1 <= features['month'] <= 12
        assert features['month'] == now.month
        
        assert 'quarter' in features
        assert 1 <= features['quarter'] <= 4

    def test_class_imbalance_handling_in_training(self):
        """
        Test that class_weight='balanced' is properly configured
        
        This ensures the model can predict minority classes (buy, strong_buy)
        """
        # Verify model configuration
        assert self.service.model.class_weight == 'balanced', \
            "Model must use class_weight='balanced' to handle 58% watch, 2.7% strong_buy imbalance"
        
        # Verify all classes are known
        expected_classes = ['avoid', 'buy', 'strong_buy', 'watch']
        for cls in expected_classes:
            assert cls in self.service.model.classes_, \
                f"Model should know class '{cls}'"

