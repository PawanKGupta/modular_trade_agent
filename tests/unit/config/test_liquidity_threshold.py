"""
Unit tests for Liquidity Threshold Configuration

Tests that liquidity threshold is set to 10,000.
"""

import pytest
import os
from unittest.mock import patch
from config.settings import MIN_ABSOLUTE_AVG_VOLUME
from config.strategy_config import StrategyConfig


class TestLiquidityThreshold:
    """Test liquidity threshold configuration"""
    
    def test_settings_min_absolute_avg_volume(self):
        """Test that MIN_ABSOLUTE_AVG_VOLUME is 10000"""
        assert MIN_ABSOLUTE_AVG_VOLUME == 10000
    
    def test_strategy_config_min_absolute_avg_volume(self):
        """Test that StrategyConfig.min_absolute_avg_volume is 10000"""
        config = StrategyConfig.default()
        assert config.min_absolute_avg_volume == 10000
    
    def test_strategy_config_default_min_absolute_avg_volume(self):
        """Test that StrategyConfig default min_absolute_avg_volume is 10000"""
        # Test that the default value is 10000
        # Note: This tests the default, not env var override (which requires module reload)
        config = StrategyConfig.default()
        # The default should be 10000 unless overridden by env var
        # Since we can't easily test env var override without module reload,
        # we just verify the current value is 10000 (the expected default)
        assert config.min_absolute_avg_volume == 10000

