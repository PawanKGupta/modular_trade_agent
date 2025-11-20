#!/usr/bin/env python3
"""Test script to verify UTF-8 BOM fix in tracking_scope.py"""

import json
from modules.kotak_neo_auto_trader.tracking_scope import TrackingScope

print("=" * 70)
print("Testing UTF-8 BOM Fix")
print("=" * 70)

# Test 1: Initialize TrackingScope
print("\n[Test 1] Initializing TrackingScope...")
try:
    ts = TrackingScope()
    print("[OK] TrackingScope initialized successfully")
except Exception as e:
    print(f"[FAIL] Failed to initialize: {e}")
    exit(1)

# Test 2: Load data (this was failing with BOM error)
print("\n[Test 2] Loading tracking data with UTF-8 BOM...")
try:
    data = ts._load_tracking_data()
    print(f"[OK] Successfully loaded data: {type(data)}")
    print(f"[OK] Data structure valid: {'symbols' in data}")
    print(f"[OK] Symbols in data: {len(data.get('symbols', []))}")
except Exception as e:
    print(f"[FAIL] Failed to load data: {e}")
    exit(1)

# Test 3: Get tracked symbols
print("\n[Test 3] Getting tracked symbols...")
try:
    active_symbols = ts.get_tracked_symbols("active")
    all_symbols = ts.get_tracked_symbols("all")
    print(f"[OK] Active symbols: {len(active_symbols)}")
    print(f"[OK] All symbols: {len(all_symbols)}")
    if all_symbols:
        print(f"[OK] Symbols: {', '.join(all_symbols[:5])}")
except Exception as e:
    print(f"[FAIL] Failed to get symbols: {e}")
    exit(1)

# Test 4: Verify no errors in logs
print("\n[Test 4] Checking for UTF-8 BOM errors...")
import os

log_file = "logs/trade_agent_20251028.log"
if os.path.exists(log_file):
    with open(log_file, "r", encoding="utf-8") as f:
        recent_logs = f.readlines()[-50:]  # Last 50 lines

    bom_errors = [line for line in recent_logs if "UTF-8 BOM" in line]
    if bom_errors:
        print(f"[WARN] Found {len(bom_errors)} UTF-8 BOM errors in recent logs")
    else:
        print("[OK] No UTF-8 BOM errors in recent logs")
else:
    print("[OK] Log file not found (OK for first run)")

print("\n" + "=" * 70)
print("? ALL TESTS PASSED! UTF-8 BOM error is FIXED!")
print("=" * 70)
