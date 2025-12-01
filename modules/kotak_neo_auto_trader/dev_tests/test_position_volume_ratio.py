#!/usr/bin/env python3
"""
Test position-to-volume ratio filter with real CURAA data
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.settings import MAX_POSITION_TO_VOLUME_RATIO
from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

print(f"Position-to-Volume Ratio Filter Test")
print(f"Max allowed ratio: {MAX_POSITION_TO_VOLUME_RATIO:.2%}\n")

# CURAA actual data from logs
curaa_avg_volume = 764  # Average daily volume
curaa_price = 153.86
curaa_qty = 649  # Calculated from Rs 100k / Rs 153.86

print(f"Test 1: CURAA (Low liquidity stock)")
print(f"  Price: Rs {curaa_price}")
print(f"  Quantity: {curaa_qty} shares")
print(f"  Avg Daily Volume: {curaa_avg_volume} shares")
print(f"  Position/Volume Ratio: {curaa_qty/curaa_avg_volume:.2%}")

result = AutoTradeEngine.check_position_volume_ratio(curaa_qty, curaa_avg_volume, "CURAA")
print(f"  Result: {'? PASS' if result else '? FAIL (Filtered out)'}")
assert result == False, "CURAA should be filtered out"
print()

# Normal stock example (RELIANCE-like)
reliance_avg_volume = 5000000  # 5M shares daily
reliance_price = 2500
reliance_qty = int(100000 / reliance_price)  # ~40 shares

print(f"Test 2: RELIANCE (High liquidity stock)")
print(f"  Price: Rs {reliance_price}")
print(f"  Quantity: {reliance_qty} shares")
print(f"  Avg Daily Volume: {reliance_avg_volume:,} shares")
print(f"  Position/Volume Ratio: {reliance_qty/reliance_avg_volume:.4%}")

result = AutoTradeEngine.check_position_volume_ratio(reliance_qty, reliance_avg_volume, "RELIANCE")
print(f"  Result: {'? PASS' if result else '? FAIL'}")
assert result == True, "RELIANCE should pass"
print()

# Medium stock at threshold
medium_avg_volume = 100000  # 100k shares daily
medium_price = 150
medium_qty = int(100000 / medium_price)  # ~666 shares

print(f"Test 3: Medium liquidity stock (Near threshold)")
print(f"  Price: Rs {medium_price}")
print(f"  Quantity: {medium_qty} shares")
print(f"  Avg Daily Volume: {medium_avg_volume:,} shares")
print(f"  Position/Volume Ratio: {medium_qty/medium_avg_volume:.2%}")

result = AutoTradeEngine.check_position_volume_ratio(medium_qty, medium_avg_volume, "MEDIUM")
print(f"  Result: {'? PASS' if result else '? FAIL'}")
assert result == True, "Medium stock should pass (0.67% < 1%)"
print()

print("=" * 60)
print("All tests passed! Position-to-volume ratio filter working correctly.")
print("=" * 60)
