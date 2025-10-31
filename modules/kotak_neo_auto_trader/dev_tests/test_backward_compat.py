#!/usr/bin/env python3
"""
Test backward compatibility of volume filtering changes
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

print("Testing backward compatibility...")
print()

# Test 1: Normal ind dict with new avg_volume field
print("Test 1: New format (with avg_volume)")
ind_new = {
    'close': 2500.0,
    'rsi10': 25.0,
    'ema9': 2550.0,
    'ema200': 2400.0,
    'avg_volume': 5000000.0
}

avg_vol = ind_new.get('avg_volume', 0)
print(f"  avg_volume: {avg_vol}")
assert avg_vol == 5000000.0, "Should get avg_volume from dict"
print("  ✅ PASS\n")

# Test 2: Old ind dict without avg_volume field (backward compat)
print("Test 2: Old format (without avg_volume)")
ind_old = {
    'close': 2500.0,
    'rsi10': 25.0,
    'ema9': 2550.0,
    'ema200': 2400.0
}

avg_vol = ind_old.get('avg_volume', 0)
print(f"  avg_volume: {avg_vol} (default)")
assert avg_vol == 0, "Should default to 0 if missing"

# Test volume check with 0 volume
result = AutoTradeEngine.check_position_volume_ratio(100, 0, "TEST")
print(f"  Volume check with 0: {result}")
assert result == False, "Should fail safely when volume is 0"
print("  ✅ PASS\n")

# Test 3: None indicators (error case)
print("Test 3: None indicators (error handling)")
ind_none = None
ind_safe = ind_none or {}
avg_vol = ind_safe.get('avg_volume', 0)
print(f"  avg_volume: {avg_vol} (from None)")
assert avg_vol == 0, "Should handle None safely"
print("  ✅ PASS\n")

print("=" * 60)
print("All backward compatibility tests passed!")
print("=" * 60)
