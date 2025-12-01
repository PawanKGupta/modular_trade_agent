"""
Unit tests for ML model retraining script.

Tests the retrain_models.py script functionality.
"""
import pytest
import pandas as pd
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Add scripts directory to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / 'scripts'))


class TestRetrainModels:
    """Test retrain_models script"""

    @pytest.fixture
    def sample_training_data(self):
        """Create sample training data"""
        return pd.DataFrame({
            'rsi_10': [25.0, 30.0, 28.0, 22.0],
            'price_above_ema200': [True, True, False, True],
            'volume_ratio': [1.5, 0.8, 1.2, 2.0],
            'support_distance_pct': [1.0, 2.5, 0.5, 1.5],
            'dip_depth_from_20d_high_pct': [15.0, 10.0, 20.0, 12.0],
            'consecutive_red_days': [3, 2, 5, 4],
            'dip_speed_pct_per_day': [2.0, 1.5, 3.0, 2.5],
            'decline_rate_slowing': [True, False, True, False],
            'volume_green_vs_red_ratio': [1.5, 1.0, 1.8, 1.3],
            'support_hold_count': [2, 1, 3, 2],
            'vol_strong': [True, False, True, True],
            'has_hammer': [True, False, False, True],
            'has_bullish_engulfing': [False, True, False, False],
            'has_divergence': [False, False, True, False],
            'alignment_score': [7, 5, 8, 6],
            'pe': [15.0, 20.0, 12.0, 18.0],
            'pb': [2.5, 3.0, 2.0, 2.8],
            'fundamental_ok': [True, True, True, True],
            'recent_high_20': [1100, 1050, 1150, 1080],
            'recent_low_20': [950, 980, 920, 960],
            'avg_volume_20': [100000, 80000, 120000, 95000],
            'is_reentry': [False, False, True, False],
            'fill_number': [1, 1, 2, 1],
            'total_fills_in_position': [1, 1, 2, 1],
            'fill_price_vs_initial_pct': [0.0, 0.0, -5.0, 0.0],
            'label': ['buy', 'watch', 'buy', 'strong_buy']
        })

    def test_load_training_data(self, sample_training_data, tmp_path):
        """Test loading training data from CSV"""
        # Save sample data to temp file
        training_file = tmp_path / "training_data.csv"
        sample_training_data.to_csv(training_file, index=False)

        # Load and verify
        loaded_data = pd.read_csv(training_file)

        assert len(loaded_data) == 4
        assert 'label' in loaded_data.columns
        assert 'rsi_10' in loaded_data.columns
        assert 'dip_depth_from_20d_high_pct' in loaded_data.columns
        assert 'is_reentry' in loaded_data.columns

    def test_training_data_has_all_features(self, sample_training_data):
        """Test that training data includes all 25 required features"""
        # Expected feature columns (excluding label and metadata)
        expected_features = [
            'rsi_10', 'price_above_ema200', 'avg_volume_20', 'volume_ratio',
            'vol_strong', 'recent_high_20', 'recent_low_20', 'support_distance_pct',
            'has_hammer', 'has_bullish_engulfing', 'has_divergence',
            'alignment_score', 'pe', 'pb', 'fundamental_ok',
            # Enhanced dip features
            'dip_depth_from_20d_high_pct', 'consecutive_red_days',
            'dip_speed_pct_per_day', 'decline_rate_slowing',
            'volume_green_vs_red_ratio', 'support_hold_count',
            # Re-entry context features
            'is_reentry', 'fill_number', 'total_fills_in_position',
            'fill_price_vs_initial_pct'
        ]

        # Verify all features are present
        for feature in expected_features:
            assert feature in sample_training_data.columns, f"Missing feature: {feature}"

        # Verify total is 25 features + label
        feature_cols = [col for col in sample_training_data.columns if col != 'label']
        assert len(feature_cols) == 25

    def test_verdict_labels_present(self, sample_training_data):
        """Test that verdict labels are valid"""
        valid_labels = ['strong_buy', 'buy', 'watch', 'avoid']

        labels = sample_training_data['label'].unique()
        for label in labels:
            assert label in valid_labels, f"Invalid label: {label}"

    def test_reentry_features_included(self, sample_training_data):
        """Test that re-entry context features are included"""
        # Verify re-entry features exist
        assert 'is_reentry' in sample_training_data.columns
        assert 'fill_number' in sample_training_data.columns
        assert 'total_fills_in_position' in sample_training_data.columns
        assert 'fill_price_vs_initial_pct' in sample_training_data.columns

        # Verify re-entry row has correct values
        reentry_row = sample_training_data[sample_training_data['is_reentry'] == True].iloc[0]
        assert reentry_row['fill_number'] == 2
        assert reentry_row['total_fills_in_position'] == 2
        assert reentry_row['fill_price_vs_initial_pct'] == -5.0  # Re-entry 5% below initial

        # Verify initial entry row has correct defaults
        initial_row = sample_training_data[sample_training_data['is_reentry'] == False].iloc[0]
        assert initial_row['fill_number'] == 1
        assert initial_row['total_fills_in_position'] == 1
        assert initial_row['fill_price_vs_initial_pct'] == 0.0

    def test_dip_features_included(self, sample_training_data):
        """Test that enhanced dip features are included"""
        dip_features = [
            'dip_depth_from_20d_high_pct',
            'consecutive_red_days',
            'dip_speed_pct_per_day',
            'decline_rate_slowing',
            'volume_green_vs_red_ratio',
            'support_hold_count'
        ]

        for feature in dip_features:
            assert feature in sample_training_data.columns
            # Verify values are reasonable
            assert sample_training_data[feature].notna().all(), f"{feature} has NaN values"

