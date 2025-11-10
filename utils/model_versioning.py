"""
Model Versioning System

Manages ML model versions based on configuration.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from utils.logger import logger
from config.strategy_config import StrategyConfig


class ModelVersioning:
    """Manages ML model versions based on configuration."""
    
    def __init__(self, versions_file: str = "models/model_versions.json"):
        """
        Initialize model versioning system.
        
        Args:
            versions_file: Path to model versions JSON file
        """
        self.versions_file = Path(versions_file)
        self.versions: Dict[str, Any] = self._load_versions()
    
    def _load_versions(self) -> Dict[str, Any]:
        """Load model versions from file."""
        if self.versions_file.exists():
            try:
                with open(self.versions_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load model versions: {e}")
                return {"verdict_models": {}, "price_models": {}}
        return {"verdict_models": {}, "price_models": {}}
    
    def _save_versions(self):
        """Save model versions to file."""
        try:
            self.versions_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.versions_file, 'w') as f:
                json.dump(self.versions, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save model versions: {e}")
    
    def _get_model_key(self, config: StrategyConfig) -> str:
        """Generate model key from configuration."""
        return f"rsi{config.rsi_period}_vol{config.volume_exhaustion_lookback_daily}_support{config.support_resistance_lookback_daily}"
    
    def get_model_path(self, config: StrategyConfig, model_type: str = "verdict") -> Optional[str]:
        """
        Get model path for given configuration.
        
        Args:
            config: Strategy configuration
            model_type: "verdict" or "price"
        
        Returns:
            Model path or None if not found
        """
        model_key = self._get_model_key(config)
        models_key = f"{model_type}_models"
        
        if models_key in self.versions and model_key in self.versions[models_key]:
            model_info = self.versions[models_key][model_key]
            model_path = model_info.get("path")
            
            if model_path and Path(model_path).exists():
                return model_path
            else:
                logger.warning(f"Model path {model_path} does not exist")
        
        return None
    
    def get_next_version(self, config: StrategyConfig, model_type: str = "verdict") -> int:
        """
        Get next version number for model.
        
        Args:
            config: Strategy configuration
            model_type: "verdict" or "price"
        
        Returns:
            Next version number
        """
        model_key = self._get_model_key(config)
        models_key = f"{model_type}_models"
        
        if models_key in self.versions and model_key in self.versions[models_key]:
            current_version = self.versions[models_key][model_key].get("version", 0)
            return current_version + 1
        
        return 1
    
    def register_model(
        self,
        config: StrategyConfig,
        model_type: str,
        model_path: str,
        version: int,
        performance: Optional[Dict[str, Any]] = None
    ):
        """
        Register a new model version.
        
        Args:
            config: Strategy configuration
            model_type: "verdict" or "price"
            model_path: Path to model file
            version: Version number
            performance: Model performance metrics
        """
        model_key = self._get_model_key(config)
        models_key = f"{model_type}_models"
        
        if models_key not in self.versions:
            self.versions[models_key] = {}
        
        self.versions[models_key][model_key] = {
            "version": version,
            "path": model_path,
            "config": {
                "rsi_period": config.rsi_period,
                "volume_exhaustion_lookback_daily": config.volume_exhaustion_lookback_daily,
                "support_resistance_lookback_daily": config.support_resistance_lookback_daily
            },
            "trained_date": datetime.now().isoformat(),
            "performance": performance or {}
        }
        
        self._save_versions()
        logger.info(f"Registered {model_type} model: {model_key} v{version}")
    
    def list_models(self, model_type: Optional[str] = None) -> Dict[str, Any]:
        """
        List all registered models.
        
        Args:
            model_type: "verdict", "price", or None for both
        
        Returns:
            Dictionary of registered models
        """
        if model_type:
            return self.versions.get(f"{model_type}_models", {})
        return self.versions


# Global instance
_model_versioning = ModelVersioning()


def get_model_path(config: StrategyConfig, model_type: str = "verdict") -> Optional[str]:
    """
    Get model path for given configuration.
    
    Args:
        config: Strategy configuration
        model_type: "verdict" or "price"
    
    Returns:
        Model path or None if not found
    """
    return _model_versioning.get_model_path(config, model_type)


def get_next_version(config: StrategyConfig, model_type: str = "verdict") -> int:
    """
    Get next version number for model.
    
    Args:
        config: Strategy configuration
        model_type: "verdict" or "price"
    
    Returns:
        Next version number
    """
    return _model_versioning.get_next_version(config, model_type)


def register_model(
    config: StrategyConfig,
    model_type: str,
    model_path: str,
    version: int,
    performance: Optional[Dict[str, Any]] = None
):
    """
    Register a new model version.
    
    Args:
        config: Strategy configuration
        model_type: "verdict" or "price"
        model_path: Path to model file
        version: Version number
        performance: Model performance metrics
    """
    _model_versioning.register_model(config, model_type, model_path, version, performance)




