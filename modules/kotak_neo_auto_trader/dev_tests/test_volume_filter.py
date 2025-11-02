#!/usr/bin/env python3
"""
Test volume filtering for low liquidity stocks like CURAA
"""

from core.volume_analysis import assess_volume_quality_intelligent
from config.settings import MIN_ABSOLUTE_AVG_VOLUME

# CURAA's actual data from logs
avg_volume_curaa = 764  # Average daily volume
current_volume_curaa = 764 * 3.67  # Today's volume (3.67x average)

print(f"Testing volume filter for CURAA")
print(f"Average volume: {avg_volume_curaa}")
print(f"Current volume: {current_volume_curaa}")
print(f"Minimum required: {MIN_ABSOLUTE_AVG_VOLUME}")
print()

result = assess_volume_quality_intelligent(
    current_volume=current_volume_curaa,
    avg_volume=avg_volume_curaa,
    enable_time_adjustment=True
)

print("Volume Analysis Result:")
print(f"  Quality: {result['quality']}")
print(f"  Ratio: {result['ratio']}x")
print(f"  Passes: {result['passes']}")
print(f"  Avg Volume: {result.get('avg_volume', 'N/A')}")
print(f"  Reason: {result['reason']}")
print()

if not result['passes']:
    print("✅ CURAA would be filtered out due to low liquidity")
else:
    print("❌ CURAA would NOT be filtered (volume check needs adjustment)")
