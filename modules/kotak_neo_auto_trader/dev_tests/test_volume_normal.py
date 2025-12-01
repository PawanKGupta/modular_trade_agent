#!/usr/bin/env python3
"""
Test that volume filtering doesn't break normal high-liquidity stocks
"""

from core.volume_analysis import assess_volume_quality_intelligent
from config.settings import MIN_ABSOLUTE_AVG_VOLUME

# Test case 1: High liquidity stock with good volume (like RELIANCE)
print("Test 1: High liquidity stock (RELIANCE-like)")
avg_volume_reliance = 5000000  # 5M shares average
current_volume_reliance = 5000000 * 1.5  # 1.5x average

result = assess_volume_quality_intelligent(
    current_volume=current_volume_reliance,
    avg_volume=avg_volume_reliance,
    enable_time_adjustment=True,
)

print(f"  Avg Volume: {result.get('avg_volume', 'N/A')}")
print(f"  Quality: {result['quality']}")
print(f"  Passes: {result['passes']}")
print(f"  Reason: {result['reason']}")
assert result["passes"] == True, "High liquidity stock should pass"
print("  ? PASS\n")

# Test case 2: Medium liquidity stock with excellent volume
print("Test 2: Medium liquidity stock with strong volume")
avg_volume_medium = 100000  # 100k shares average
current_volume_medium = 100000 * 2.0  # 2x average

result = assess_volume_quality_intelligent(
    current_volume=current_volume_medium, avg_volume=avg_volume_medium, enable_time_adjustment=True
)

print(f"  Avg Volume: {result.get('avg_volume', 'N/A')}")
print(f"  Quality: {result['quality']}")
print(f"  Passes: {result['passes']}")
print(f"  Reason: {result['reason']}")
assert result["passes"] == True, "Medium liquidity stock with strong volume should pass"
print("  ? PASS\n")

# Test case 3: Low liquidity stock (should fail)
print("Test 3: Low liquidity stock (CURAA-like)")
avg_volume_low = 764  # Very low average
current_volume_low = 764 * 3.67  # Even with high ratio

result = assess_volume_quality_intelligent(
    current_volume=current_volume_low, avg_volume=avg_volume_low, enable_time_adjustment=True
)

print(f"  Avg Volume: {result.get('avg_volume', 'N/A')}")
print(f"  Quality: {result['quality']}")
print(f"  Passes: {result['passes']}")
print(f"  Reason: {result['reason']}")
assert result["passes"] == False, "Low liquidity stock should fail"
assert result["quality"] == "illiquid", "Should be marked as illiquid"
print("  ? PASS\n")

print("=" * 60)
print("All tests passed! Volume filtering is working correctly.")
print("=" * 60)
