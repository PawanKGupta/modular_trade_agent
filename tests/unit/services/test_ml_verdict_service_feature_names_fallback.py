"""
Unit Tests for ML Verdict Service Feature Names Fallback

Tests for the feature_names_in_ fallback logic when feature file is missing.
"""

import sys
from pathlib import Path
import pytest
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from config.strategy_config import StrategyConfig
from services.ml_verdict_service import MLVerdictService


class TestMLVerdictServiceFeatureNamesFallback:
    """Test feature_names_in_ fallback logic in MLVerdictService"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files"""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.fixture
    def default_config(self):
        """Default configuration"""
        return StrategyConfig.default()

    @pytest.fixture
    def mock_model_with_feature_names(self):
        """Create mock ML model with feature_names_in_"""
        model = MagicMock()
        model.feature_names_in_ = [
            'rsi_10', 'price_above_ema200', 'avg_volume_20', 'volume_ratio',
            'vol_strong', 'recent_high_20', 'recent_low_20', 'support_distance_pct',
            'has_hammer', 'has_bullish_engulfing', 'pe', 'pb', 'fundamental_ok'
        ]
        model.n_features_in_ = 13
        return model

    @pytest.fixture
    def mock_model_without_feature_names(self):
        """Create mock ML model without feature_names_in_"""
        model = MagicMock()
        # Remove feature_names_in_ attribute if it exists
        if hasattr(model, 'feature_names_in_'):
            delattr(model, 'feature_names_in_')
        model.n_features_in_ = 13
        return model

    def test_loads_feature_file_when_exists(self, default_config, temp_dir, mock_model_with_feature_names):
        """Test that service loads feature columns from file when it exists"""
        model_path = temp_dir / "verdict_model_random_forest.pkl"
        model_path.touch()

        # Create feature columns file (new format)
        features_path = temp_dir / "verdict_model_features_random_forest.txt"
        with open(features_path, 'w') as f:
            f.write("rsi_10\n")
            f.write("price_above_ema200\n")
            f.write("avg_volume_20\n")
            f.write("volume_ratio\n")

        with patch('joblib.load') as mock_load:
            mock_load.return_value = mock_model_with_feature_names

            service = MLVerdictService(model_path=str(model_path), config=default_config)

            # Verify feature columns loaded from file (not from model)
            assert len(service.feature_cols) == 4
            assert "rsi_10" in service.feature_cols
            assert "price_above_ema200" in service.feature_cols
            assert "avg_volume_20" in service.feature_cols
            assert "volume_ratio" in service.feature_cols
            # Verify model's feature_names_in_ was NOT used (file took precedence)
            assert "has_hammer" not in service.feature_cols  # In model but not in file

    def test_uses_feature_names_in_when_file_missing(self, default_config, temp_dir, mock_model_with_feature_names):
        """Test that service uses model.feature_names_in_ when feature file is missing"""
        model_path = temp_dir / "verdict_model_random_forest.pkl"
        model_path.touch()

        # Don't create feature file - simulate missing file scenario

        with patch('joblib.load') as mock_load:
            mock_load.return_value = mock_model_with_feature_names

            service = MLVerdictService(model_path=str(model_path), config=default_config)

            # Verify feature columns loaded from model.feature_names_in_
            assert len(service.feature_cols) == 13
            assert "rsi_10" in service.feature_cols
            assert "price_above_ema200" in service.feature_cols
            assert "has_hammer" in service.feature_cols
            assert "has_bullish_engulfing" in service.feature_cols
            assert "pe" in service.feature_cols
            assert "pb" in service.feature_cols
            # Verify all features from model are present
            assert set(service.feature_cols) == set(mock_model_with_feature_names.feature_names_in_)

    def test_warns_when_file_missing_and_no_feature_names(self, default_config, temp_dir, mock_model_without_feature_names):
        """Test that service warns when feature file missing and model has no feature_names_in_"""
        model_path = temp_dir / "verdict_model_random_forest.pkl"
        model_path.touch()

        # Don't create feature file
        # Model doesn't have feature_names_in_

        with patch('joblib.load') as mock_load:
            mock_load.return_value = mock_model_without_feature_names

            with patch('services.ml_verdict_service.logger') as mock_logger:
                service = MLVerdictService(model_path=str(model_path), config=default_config)

                # Verify warning was logged
                warning_calls = [call for call in mock_logger.warning.call_args_list
                               if call and 'Feature columns file not found and model doesn\'t have feature_names_in_' in str(call)]
                assert len(warning_calls) > 0, "Should log warning when both file and feature_names_in_ are missing"

                # Verify feature_cols is empty (will extract dynamically)
                assert len(service.feature_cols) == 0

    def test_tries_multiple_feature_file_paths(self, default_config, temp_dir, mock_model_with_feature_names):
        """Test that service tries multiple filename patterns for feature file"""
        model_path = temp_dir / "verdict_model_random_forest.pkl"
        model_path.touch()

        # Create feature file with alternative format
        # Service should try: verdict_model_features_random_forest.txt first
        # Then: verdict_random_forest_features.txt
        # Then: verdict_model_features_enhanced.txt
        features_path_alt = temp_dir / "verdict_random_forest_features.txt"  # Alternative format
        with open(features_path_alt, 'w') as f:
            f.write("rsi_10\n")
            f.write("ema200\n")

        with patch('joblib.load') as mock_load:
            mock_load.return_value = mock_model_with_feature_names

            service = MLVerdictService(model_path=str(model_path), config=default_config)

            # Should find alternative format file
            assert len(service.feature_cols) == 2
            assert "rsi_10" in service.feature_cols
            assert "ema200" in service.feature_cols

    def test_uses_feature_names_in_for_xgboost_model(self, default_config, temp_dir):
        """Test that service uses feature_names_in_ for XGBoost models"""
        model_path = temp_dir / "verdict_model_xgboost.pkl"
        model_path.touch()

        # Create XGBoost-style model with feature_names_in_
        mock_xgboost_model = MagicMock()
        mock_xgboost_model.feature_names_in_ = [
            'rsi_10', 'price_above_ema200', 'dip_depth_from_20d_high_pct',
            'consecutive_red_days', 'nifty_trend', 'day_of_week'
        ]
        mock_xgboost_model.n_features_in_ = 6

        # Don't create feature file

        with patch('joblib.load') as mock_load:
            mock_load.return_value = mock_xgboost_model

            service = MLVerdictService(model_path=str(model_path), config=default_config)

            # Verify feature columns loaded from model.feature_names_in_
            assert len(service.feature_cols) == 6
            assert "rsi_10" in service.feature_cols
            assert "price_above_ema200" in service.feature_cols
            assert "dip_depth_from_20d_high_pct" in service.feature_cols
            assert "nifty_trend" in service.feature_cols
            assert set(service.feature_cols) == set(mock_xgboost_model.feature_names_in_)

    def test_feature_names_order_matches_model(self, default_config, temp_dir, mock_model_with_feature_names):
        """Test that feature columns order matches model.feature_names_in_ order"""
        model_path = temp_dir / "verdict_model_random_forest.pkl"
        model_path.touch()

        # Don't create feature file

        with patch('joblib.load') as mock_load:
            mock_load.return_value = mock_model_with_feature_names

            service = MLVerdictService(model_path=str(model_path), config=default_config)

            # Verify feature columns order matches model.feature_names_in_
            expected_order = list(mock_model_with_feature_names.feature_names_in_)
            assert service.feature_cols == expected_order, \
                f"Feature order mismatch. Expected: {expected_order}, Got: {service.feature_cols}"

    def test_feature_names_fallback_with_legacy_enhanced_file(self, default_config, temp_dir, mock_model_with_feature_names):
        """Test that service tries legacy enhanced.txt filename as fallback"""
        model_path = temp_dir / "verdict_model_random_forest.pkl"
        model_path.touch()

        # Create legacy feature file
        legacy_features_path = temp_dir / "verdict_model_features_enhanced.txt"
        with open(legacy_features_path, 'w') as f:
            f.write("rsi_10\n")
            f.write("price_above_ema200\n")
            f.write("dip_depth_from_20d_high_pct\n")

        with patch('joblib.load') as mock_load:
            mock_load.return_value = mock_model_with_feature_names

            service = MLVerdictService(model_path=str(model_path), config=default_config)

            # Should load from legacy file (third fallback)
            assert len(service.feature_cols) == 3
            assert "rsi_10" in service.feature_cols
            assert "dip_depth_from_20d_high_pct" in service.feature_cols

