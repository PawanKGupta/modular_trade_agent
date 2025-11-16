#!/usr/bin/env python3
"""
Unit tests for EMA9 calculation in indicators

Tests that EMA9 is correctly calculated and included in the dataframe.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from core.indicators import compute_indicators


class TestEMA9Calculation:
    """Test EMA9 calculation in compute_indicators"""
    
    def test_ema9_is_calculated(self):
        """Test that EMA9 is calculated and added to dataframe"""
        # Create sample data
        df = pd.DataFrame({
            'Close': [100 + i for i in range(50)],
            'High': [102 + i for i in range(50)],
            'Low': [98 + i for i in range(50)],
            'Volume': [1000000] * 50
        })
        
        result = compute_indicators(df)
        
        assert result is not None
        assert 'ema9' in result.columns
        assert not result['ema9'].isna().all()
        
    def test_ema9_calculation_accuracy(self):
        """Test that EMA9 is calculated correctly (spot check)"""
        # Create data with known pattern
        prices = [100] * 10 + [110] * 10 + [120] * 30  # Step changes
        df = pd.DataFrame({
            'Close': prices,
            'High': [p + 2 for p in prices],
            'Low': [p - 2 for p in prices],
            'Volume': [1000000] * 50
        })
        
        result = compute_indicators(df)
        
        # EMA9 should follow the price trend (rising)
        ema9_values = result['ema9'].dropna()
        assert len(ema9_values) > 0
        
        # Last EMA9 should be between the price levels (smoothed)
        last_ema9 = ema9_values.iloc[-1]
        assert 100 < last_ema9 < 130  # Should be in reasonable range
        
    def test_ema9_with_other_emas(self):
        """Test that EMA9 is calculated alongside other EMAs"""
        df = pd.DataFrame({
            'Close': [100 + i * 0.5 for i in range(300)],
            'High': [102 + i * 0.5 for i in range(300)],
            'Low': [98 + i * 0.5 for i in range(300)],
            'Volume': [1000000] * 300
        })
        
        result = compute_indicators(df)
        
        # All EMAs should be present
        assert 'ema9' in result.columns
        assert 'ema20' in result.columns
        assert 'ema50' in result.columns
        assert 'ema200' in result.columns
        
        # EMA9 should be most responsive (closest to current price)
        last_price = result['Close'].iloc[-1]
        last_ema9 = result['ema9'].iloc[-1]
        last_ema20 = result['ema20'].iloc[-1]
        last_ema200 = result['ema200'].iloc[-1]
        
        # In uptrend, EMA9 should be between price and longer EMAs
        # (closest to current price)
        assert abs(last_price - last_ema9) < abs(last_price - last_ema20)
        assert abs(last_price - last_ema9) < abs(last_price - last_ema200)
        
    def test_ema9_handles_lowercase_columns(self):
        """Test that EMA9 works with lowercase column names"""
        df = pd.DataFrame({
            'close': [100 + i for i in range(50)],
            'high': [102 + i for i in range(50)],
            'low': [98 + i for i in range(50)],
            'volume': [1000000] * 50
        })
        
        result = compute_indicators(df)
        
        assert result is not None
        assert 'ema9' in result.columns
        assert not result['ema9'].isna().all()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

