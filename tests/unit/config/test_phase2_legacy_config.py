"""
Unit Tests for Phase 2: Legacy Config Constants Deprecation

Tests for:
1. Legacy constants synced with StrategyConfig
2. Backward compatibility
3. Deprecation warnings (if implemented)
"""
import sys
from pathlib import Path
import pytest
import warnings

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from config.settings import RSI_OVERSOLD, RSI_NEAR_OVERSOLD
from config.strategy_config import StrategyConfig


class TestLegacyConfigDeprecation:
    """Test legacy config constants deprecation"""
    
    def test_legacy_constants_exist(self):
        """Test legacy constants still exist for backward compatibility"""
        assert RSI_OVERSOLD is not None
        assert RSI_NEAR_OVERSOLD is not None
    
    def test_legacy_constants_synced_with_strategy_config(self):
        """Test legacy constants are synced with StrategyConfig"""
        config = StrategyConfig.default()
        
        # Legacy constants should match StrategyConfig values
        assert RSI_OVERSOLD == config.rsi_oversold
        assert RSI_NEAR_OVERSOLD == config.rsi_near_oversold
    
    def test_legacy_constants_default_values(self):
        """Test legacy constants have correct default values"""
        assert RSI_OVERSOLD == 30.0
        assert RSI_NEAR_OVERSOLD == 40.0
    
    def test_legacy_constants_importable(self):
        """Test legacy constants can still be imported"""
        from config.settings import RSI_OVERSOLD, RSI_NEAR_OVERSOLD
        
        assert RSI_OVERSOLD == 30.0
        assert RSI_NEAR_OVERSOLD == 40.0
    
    def test_strategy_config_preferred(self):
        """Test StrategyConfig is the preferred way to access RSI thresholds"""
        config = StrategyConfig.default()
        
        # StrategyConfig should be the source of truth
        assert config.rsi_oversold == 30.0
        assert config.rsi_extreme_oversold == 20.0
        assert config.rsi_near_oversold == 40.0
        
        # Legacy constants should match
        assert RSI_OVERSOLD == config.rsi_oversold
        assert RSI_NEAR_OVERSOLD == config.rsi_near_oversold


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
