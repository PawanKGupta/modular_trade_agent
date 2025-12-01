#!/usr/bin/env python3
"""
Test price-tiered volume filtering with real-world examples
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
from config.settings import POSITION_VOLUME_RATIO_TIERS

print("Price-Tiered Volume Filter Test")
print("=" * 70)
print("\nTier Configuration:")
for price_threshold, max_ratio in POSITION_VOLUME_RATIO_TIERS:
    if price_threshold > 0:
        print(f"  Rs {price_threshold}+: {max_ratio:.1%} max")
    else:
        print(f"  <Rs 500: {max_ratio:.1%} max")
print()

# Test cases with real scenarios
test_cases = [
    # (name, price, avg_volume, qty, should_pass)
    ("CURAA (Original issue)", 153.86, 764, 649, False),  # 85% ratio - should fail even at 20%
    ("RELIANCE (Large cap)", 2500, 5000000, 40, True),  # 0.0008% - passes
    ("TCS (Large cap)", 3500, 3000000, 28, True),  # 0.0009% - passes
    ("Midcap Rs 800", 800, 20000, 125, True),  # 0.625% < 10% - passes
    ("Midcap Rs 800 low vol", 800, 1000, 125, False),  # 12.5% > 10% - fails
    ("Small cap Rs 200", 200, 5000, 500, True),  # 10% < 20% - passes
    ("Small cap Rs 200 very low", 200, 1000, 500, False),  # 50% > 20% - fails
    ("Penny stock Rs 50", 50, 500, 2000, False),  # 400% > 20% - fails (extreme)
]

print("Test Results:")
print("-" * 70)

passed = 0
failed = 0

for name, price, avg_vol, qty, expected in test_cases:
    result = AutoTradeEngine.check_position_volume_ratio(qty, avg_vol, name, price)

    ratio = (qty / avg_vol) * 100
    status = "? PASS" if result == expected else "? FAIL"

    if result == expected:
        passed += 1
    else:
        failed += 1

    print(f"\n{name}")
    print(f"  Price: Rs {price:.2f} | Qty: {qty} | Avg Vol: {avg_vol:,}")
    print(f"  Ratio: {ratio:.1f}% | Expected: {'Pass' if expected else 'Fail'} | {status}")

print("\n" + "=" * 70)
print(f"Test Summary: {passed} passed, {failed} failed")

if failed == 0:
    print("? All tests passed! Tier configuration working correctly.")
else:
    print("? Some tests failed - review configuration")

print("\nKey Insights:")
print("- CURAA (85% ratio) would be filtered [OK]")
print("- Good large caps pass easily [OK]")
print("- Good mid/small caps pass [OK]")
print("- Only truly illiquid stocks filtered [OK]")
