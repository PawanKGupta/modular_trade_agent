"""
Unit Tests for Phase 2: Auto-Trader Config Sync

Tests for:
1. Auto-trader config syncs with StrategyConfig
2. RSI period consistency
3. Backward compatibility
"""
import sys
from pathlib import Path
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader import config as auto_trader_config
from config.strategy_config import StrategyConfig


class TestAutoTraderConfigSync:
    """Test auto-trader config syncs with StrategyConfig"""
    
    def test_auto_trader_rsi_period_synced(self):
        """Test auto-trader RSI_PERIOD is synced with StrategyConfig"""
        strategy_config = StrategyConfig.default()
        
        # Auto-trader RSI_PERIOD should match StrategyConfig
        assert auto_trader_config.RSI_PERIOD == strategy_config.rsi_period
    
    def test_auto_trader_rsi_period_default(self):
        """Test auto-trader RSI_PERIOD has correct default"""
        assert auto_trader_config.RSI_PERIOD == 10
    
    def test_auto_trader_ema_settings_separate(self):
        """Test auto-trader EMA settings are separate from StrategyConfig"""
        # EMA settings should be auto-trader specific
        assert hasattr(auto_trader_config, 'EMA_SHORT')
        assert hasattr(auto_trader_config, 'EMA_LONG')
        assert auto_trader_config.EMA_SHORT == 9
        assert auto_trader_config.EMA_LONG == 200
    
    def test_auto_trader_config_importable(self):
        """Test auto-trader config can be imported"""
        from modules.kotak_neo_auto_trader.config import RSI_PERIOD, EMA_SHORT, EMA_LONG
        
        assert RSI_PERIOD == 10
        assert EMA_SHORT == 9
        assert EMA_LONG == 200
    
    def test_auto_trader_config_uses_strategy_config(self):
        """Test auto-trader config uses StrategyConfig internally"""
        # The config module should import StrategyConfig
        assert hasattr(auto_trader_config, 'RSI_PERIOD')
        
        # Verify it's synced
        strategy_config = StrategyConfig.default()
        assert auto_trader_config.RSI_PERIOD == strategy_config.rsi_period


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
