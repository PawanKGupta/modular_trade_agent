#!/usr/bin/env python3
"""
Test Backtest Integration

Quick test to verify the backtest scoring integration works.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trade_agent import main
from utils.logger import logger

def test_backtest_integration():
    """Test the backtest scoring integration"""
    
    print("Testing backtest integration...")
    
    # Test without backtest scoring (should be fast)
    print("\n1. Testing without backtest scoring:")
    main(export_csv=False, enable_multi_timeframe=True, enable_backtest_scoring=False)
    
    print("\n" + "="*60)
    
    # Test with backtest scoring (will be slower)
    print("\n2. Testing WITH backtest scoring:")
    main(export_csv=False, enable_multi_timeframe=True, enable_backtest_scoring=True)

if __name__ == "__main__":
    test_backtest_integration()
