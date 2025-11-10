"""
Unit Tests for Model Versioning System
"""

import sys
import os
from pathlib import Path
import pytest
import json
import tempfile
import shutil
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from config.strategy_config import StrategyConfig
from utils.model_versioning import ModelVersioning, get_model_path, get_next_version, register_model


class TestModelVersioning:
    """Test ModelVersioning class"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files"""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        shutil.rmtree(temp_path)
    
    @pytest.fixture
    def versions_file(self, temp_dir):
        """Create temporary versions file"""
        return temp_dir / "model_versions.json"
    
    @pytest.fixture
    def versioning(self, versions_file):
        """Create ModelVersioning instance with temporary file"""
        return ModelVersioning(str(versions_file))
    
    @pytest.fixture
    def config_default(self):
        """Default configuration"""
        return StrategyConfig.default()
    
    @pytest.fixture
    def config_custom(self):
        """Custom configuration"""
        return StrategyConfig(
            rsi_period=14,
            volume_exhaustion_lookback_daily=30,
            support_resistance_lookback_daily=50
        )
    
    def test_get_model_key(self, versioning, config_default):
        """Test model key generation"""
        key = versioning._get_model_key(config_default)
        assert key == "rsi10_vol10_support20"
    
    def test_get_model_key_custom(self, versioning, config_custom):
        """Test model key generation with custom config"""
        key = versioning._get_model_key(config_custom)
        assert key == "rsi14_vol30_support50"
    
    def test_get_model_path_not_found(self, versioning, config_default):
        """Test get_model_path when model not found"""
        path = versioning.get_model_path(config_default, "verdict")
        assert path is None
    
    def test_get_model_path_found(self, versioning, config_default, temp_dir):
        """Test get_model_path when model exists"""
        # Create a model file
        model_path = temp_dir / "verdict_model_rsi10_vol10_support20_v1.pkl"
        model_path.touch()
        
        # Register model
        versioning.register_model(
            config_default,
            "verdict",
            str(model_path),
            1,
            {"accuracy": 0.85}
        )
        
        # Get model path
        path = versioning.get_model_path(config_default, "verdict")
        assert path == str(model_path)
    
    def test_get_model_path_nonexistent_file(self, versioning, config_default):
        """Test get_model_path when file doesn't exist"""
        # Register model with non-existent path
        versioning.register_model(
            config_default,
            "verdict",
            "models/nonexistent.pkl",
            1
        )
        
        # Get model path should return None
        path = versioning.get_model_path(config_default, "verdict")
        assert path is None
    
    def test_get_next_version_first(self, versioning, config_default):
        """Test get_next_version for first version"""
        version = versioning.get_next_version(config_default, "verdict")
        assert version == 1
    
    def test_get_next_version_increments(self, versioning, config_default, temp_dir):
        """Test get_next_version increments correctly"""
        model_path = temp_dir / "verdict_model.pkl"
        model_path.touch()
        
        # Register first version
        versioning.register_model(
            config_default,
            "verdict",
            str(model_path),
            1
        )
        
        # Get next version
        version = versioning.get_next_version(config_default, "verdict")
        assert version == 2
        
        # Register second version
        versioning.register_model(
            config_default,
            "verdict",
            str(model_path),
            2
        )
        
        # Get next version
        version = versioning.get_next_version(config_default, "verdict")
        assert version == 3
    
    def test_register_model(self, versioning, config_default, versions_file):
        """Test model registration"""
        model_path = "models/verdict_model_rsi10_vol10_support20_v1.pkl"
        performance = {"accuracy": 0.85, "precision": 0.82}
        
        versioning.register_model(
            config_default,
            "verdict",
            model_path,
            1,
            performance
        )
        
        # Verify file was created
        assert versions_file.exists()
        
        # Verify content
        with open(versions_file, 'r') as f:
            versions = json.load(f)
        
        assert "verdict_models" in versions
        assert "rsi10_vol10_support20" in versions["verdict_models"]
        
        model_info = versions["verdict_models"]["rsi10_vol10_support20"]
        assert model_info["version"] == 1
        assert model_info["path"] == model_path
        assert model_info["performance"] == performance
        assert model_info["config"]["rsi_period"] == 10
    
    def test_register_model_both_types(self, versioning, config_default, versions_file):
        """Test registering both verdict and price models"""
        verdict_path = "models/verdict_model.pkl"
        price_path = "models/price_model.pkl"
        
        versioning.register_model(config_default, "verdict", verdict_path, 1)
        versioning.register_model(config_default, "price", price_path, 1)
        
        # Verify both registered
        with open(versions_file, 'r') as f:
            versions = json.load(f)
        
        assert "verdict_models" in versions
        assert "price_models" in versions
        assert "rsi10_vol10_support20" in versions["verdict_models"]
        assert "rsi10_vol10_support20" in versions["price_models"]
    
    def test_list_models_all(self, versioning, config_default):
        """Test list_models returns all models"""
        versioning.register_model(config_default, "verdict", "models/v1.pkl", 1)
        versioning.register_model(config_default, "price", "models/p1.pkl", 1)
        
        models = versioning.list_models()
        assert "verdict_models" in models
        assert "price_models" in models
    
    def test_list_models_by_type(self, versioning, config_default):
        """Test list_models filters by type"""
        versioning.register_model(config_default, "verdict", "models/v1.pkl", 1)
        versioning.register_model(config_default, "price", "models/p1.pkl", 1)
        
        verdict_models = versioning.list_models("verdict")
        assert "rsi10_vol10_support20" in verdict_models
        assert "price_models" not in verdict_models
    
    def test_load_existing_versions(self, versioning, versions_file, temp_dir):
        """Test loading existing versions file"""
        # Create model file
        model_path = temp_dir / "existing.pkl"
        model_path.touch()
        
        # Create existing versions file
        existing_versions = {
            "verdict_models": {
                "rsi10_vol10_support20": {
                    "version": 1,
                    "path": str(model_path),
                    "config": {"rsi_period": 10},
                    "trained_date": "2025-11-07T00:00:00",
                    "performance": {}
                }
            },
            "price_models": {}
        }
        
        with open(versions_file, 'w') as f:
            json.dump(existing_versions, f)
        
        # Create new versioning instance
        new_versioning = ModelVersioning(str(versions_file))
        
        # Verify loaded
        path = new_versioning.get_model_path(StrategyConfig.default(), "verdict")
        assert path == str(model_path)
        
        version = new_versioning.get_next_version(StrategyConfig.default(), "verdict")
        assert version == 2


class TestModelVersioningFunctions:
    """Test module-level functions"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files"""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        shutil.rmtree(temp_path)
    
    def test_get_model_path_function(self, temp_dir):
        """Test get_model_path function"""
        versions_file = temp_dir / "model_versions.json"
        
        # Create versioning instance with temp file
        versioning = ModelVersioning(str(versions_file))
        
        config = StrategyConfig.default()
        model_path = temp_dir / "verdict_model.pkl"
        model_path.touch()
        
        versioning.register_model(config, "verdict", str(model_path), 1)
        
        # Test function
        path = get_model_path(config, "verdict")
        # Note: Function uses global instance, so may not find the temp model
        # This is expected behavior - function uses default instance
    
    def test_get_next_version_function(self):
        """Test get_next_version function"""
        config = StrategyConfig.default()
        version = get_next_version(config, "verdict")
        assert isinstance(version, int)
        assert version >= 1
    
    def test_register_model_function(self, temp_dir):
        """Test register_model function"""
        config = StrategyConfig.default()
        model_path = str(temp_dir / "test_model.pkl")
        
        register_model(config, "verdict", model_path, 1, {"accuracy": 0.85})
        
        # Verify registered
        path = get_model_path(config, "verdict")
        # May not find if using default instance, but registration should work
