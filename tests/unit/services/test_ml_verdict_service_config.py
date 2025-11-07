"""
Unit Tests for ML Verdict Service Configuration-Based Model Selection
"""

import sys
import os
from pathlib import Path
import pytest
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from config.strategy_config import StrategyConfig
from services.ml_verdict_service import MLVerdictService


class TestMLVerdictServiceConfigBasedModelSelection:
    """Test configuration-based model selection in MLVerdictService"""
    
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
    def custom_config(self):
        """Custom configuration"""
        return StrategyConfig(
            rsi_period=14,
            volume_exhaustion_lookback_daily=30,
            support_resistance_lookback_daily=50
        )
    
    @pytest.fixture
    def mock_model(self):
        """Create mock ML model"""
        model = MagicMock()
        model.predict_proba.return_value = [[0.2, 0.8]]  # [avoid, buy]
        return model
    
    def test_init_without_model_path_uses_config(self, default_config, temp_dir):
        """Test that service tries to find model based on config when no path provided"""
        # Mock model versioning to return a path
        with patch('utils.model_versioning.get_model_path') as mock_get_path:
            mock_model_path = str(temp_dir / "config_model.pkl")
            Path(mock_model_path).touch()
            mock_get_path.return_value = mock_model_path
            
            with patch('joblib.load') as mock_load:
                mock_model = MagicMock()
                mock_load.return_value = mock_model
                
                service = MLVerdictService(model_path=None, config=default_config)
                
                # Verify get_model_path was called
                mock_get_path.assert_called_once_with(default_config, "verdict")
                
                # Verify model was loaded
                assert service.model_loaded is True
    
    def test_init_falls_back_to_default_model(self, default_config, temp_dir):
        """Test that service falls back to default model if config-based model not found"""
        # Mock model versioning to return None
        with patch('utils.model_versioning.get_model_path') as mock_get_path:
            mock_get_path.return_value = None
            
            # Create default model file
            default_model_path = temp_dir / "verdict_model_random_forest.pkl"
            default_model_path.touch()
            
            # Mock Path to return True for default model
            with patch('services.ml_verdict_service.Path') as mock_path_class:
                def path_side_effect(path_str):
                    mock_path = MagicMock()
                    if "random_forest" in str(path_str) or str(path_str).endswith("verdict_model_random_forest.pkl"):
                        mock_path.exists.return_value = True
                    else:
                        mock_path.exists.return_value = False
                    return mock_path
                
                mock_path_class.side_effect = path_side_effect
                
                with patch('joblib.load') as mock_load:
                    mock_model = MagicMock()
                    mock_load.return_value = mock_model
                    
                    service = MLVerdictService(model_path=None, config=default_config)
                    
                    # Verify fallback to default
                    assert service.model_loaded is True
    
    def test_init_with_explicit_model_path(self, default_config, temp_dir):
        """Test that explicit model_path overrides config-based lookup"""
        explicit_path = str(temp_dir / "explicit_model.pkl")
        Path(explicit_path).touch()
        
        with patch('utils.model_versioning.get_model_path') as mock_get_path:
            with patch('joblib.load') as mock_load:
                mock_model = MagicMock()
                mock_load.return_value = mock_model
                
                service = MLVerdictService(model_path=explicit_path, config=default_config)
                
                # Verify get_model_path was NOT called (explicit path provided)
                mock_get_path.assert_not_called()
                
                # Verify model was loaded from explicit path
                assert service.model_loaded is True
    
    def test_init_with_custom_config(self, custom_config, temp_dir):
        """Test that service uses custom config for model lookup"""
        with patch('utils.model_versioning.get_model_path') as mock_get_path:
            mock_model_path = str(temp_dir / "custom_model.pkl")
            Path(mock_model_path).touch()
            mock_get_path.return_value = mock_model_path
            
            with patch('joblib.load') as mock_load:
                mock_model = MagicMock()
                mock_load.return_value = mock_model
                
                service = MLVerdictService(model_path=None, config=custom_config)
                
                # Verify get_model_path was called with custom config
                mock_get_path.assert_called_once_with(custom_config, "verdict")
    
    def test_init_handles_model_versioning_error(self, default_config):
        """Test that service handles errors in model versioning gracefully"""
        # Mock get_model_path to raise exception
        with patch('utils.model_versioning.get_model_path') as mock_get_path:
            mock_get_path.side_effect = Exception("Versioning error")
            
            # Mock default model path to not exist
            with patch('services.ml_verdict_service.Path') as mock_path_class:
                def path_side_effect(path_str):
                    mock_path = MagicMock()
                    mock_path.exists.return_value = False  # Default model doesn't exist
                    return mock_path
                
                mock_path_class.side_effect = path_side_effect
                
                # Should not raise exception, should fall back
                service = MLVerdictService(model_path=None, config=default_config)
                
                # Should not have loaded model (default model also doesn't exist)
                assert service.model_loaded is False
    
    def test_init_no_model_available(self, default_config):
        """Test that service handles case when no model is available"""
        # Mock get_model_path to return None
        with patch('utils.model_versioning.get_model_path') as mock_get_path:
            mock_get_path.return_value = None
            
            # Mock default model path to not exist
            with patch('services.ml_verdict_service.Path') as mock_path_class:
                def path_side_effect(path_str):
                    mock_path = MagicMock()
                    mock_path.exists.return_value = False
                    return mock_path
                
                mock_path_class.side_effect = path_side_effect
                
                service = MLVerdictService(model_path=None, config=default_config)
                
                # Should not have loaded model
                assert service.model_loaded is False
                assert service.model is None
    
    def test_init_loads_feature_columns(self, default_config, temp_dir):
        """Test that service loads feature columns if available"""
        model_path = temp_dir / "verdict_model_random_forest.pkl"
        model_path.touch()
        
        # Create feature columns file (name should match model name pattern)
        # The service looks for: {model_stem.replace('model_', '')}_features.txt
        # For "verdict_model_random_forest.pkl", it looks for "verdict_random_forest_features.txt"
        features_path = temp_dir / "verdict_random_forest_features.txt"
        with open(features_path, 'w') as f:
            f.write("rsi_10\n")
            f.write("ema200\n")
            f.write("volume_ratio\n")
        
        with patch('utils.model_versioning.get_model_path') as mock_get_path:
            mock_get_path.return_value = str(model_path)
            
            with patch('joblib.load') as mock_load:
                mock_model = MagicMock()
                mock_load.return_value = mock_model
                
                service = MLVerdictService(model_path=None, config=default_config)
                
                # Verify feature columns loaded
                assert len(service.feature_cols) == 3
                assert "rsi_10" in service.feature_cols
                assert "ema200" in service.feature_cols
                assert "volume_ratio" in service.feature_cols

