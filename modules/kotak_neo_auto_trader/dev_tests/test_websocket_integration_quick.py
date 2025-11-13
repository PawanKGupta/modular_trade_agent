#!/usr/bin/env python3
"""
Quick test to verify WebSocket integration is working
Tests the exact production flow
"""

import sys
import os
import time
from pathlib import Path

# Add project root to path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent.parent.resolve()
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
from modules.kotak_neo_auto_trader.live_price_cache import LivePriceCache
from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster

print("=" * 80)
print("Quick WebSocket Integration Test")
print("=" * 80)
print()

# Login
print("🔐 Logging in...")
auth = KotakNeoAuth("modules/kotak_neo_auto_trader/kotak_neo.env")
if not auth.login():
    print("❌ Login failed")
    sys.exit(1)
print("✅ Logged in\n")

# Initialize like production does (run_trading_service.py)
print("📊 Initializing like production...")

# Load scrip master
scrip_master = KotakNeoScripMaster(auth_client=auth.client, exchanges=['NSE'])
scrip_master.load_scrip_master(force_download=False)
print("✅ Scrip master loaded")

# Initialize LivePriceCache
price_cache = LivePriceCache(
    auth_client=auth.client,
    scrip_master=scrip_master,
    stale_threshold_seconds=60,
    reconnect_delay_seconds=5
)

# Start WebSocket
price_cache.start()
print("✅ WebSocket started")

# Wait for connection
print("⏳ Waiting for connection...")
if price_cache.wait_for_connection(timeout=10):
    print("✅ WebSocket connected")
else:
    print("⚠️  Connection timeout")

# Subscribe to test symbol
test_symbol = "DALBHARAT"
print(f"\n📡 Subscribing to {test_symbol}...")
price_cache.subscribe([test_symbol])
time.sleep(3)  # Wait for data

# Initialize SellOrderManager with LivePriceCache (like production)
print(f"\n🔧 Initializing SellOrderManager with LivePriceCache...")
sell_manager = SellOrderManager(auth=auth, price_manager=price_cache)
print("✅ SellOrderManager initialized")

# Test get_current_ltp() - this is what was failing before
print(f"\n🧪 Testing get_current_ltp() for {test_symbol}...")
print("-" * 80)

try:
    ltp = sell_manager.get_current_ltp(ticker=f"{test_symbol}.NS", broker_symbol=f"{test_symbol}-EQ")
    
    if ltp is not None and ltp > 0:
        print(f"✅ SUCCESS! LTP: ₹{ltp:.2f}")
        
        # Check WebSocket stats
        stats = price_cache.get_stats()
        print(f"\n📊 WebSocket Stats:")
        print(f"  Connected: {stats['connected']}")
        print(f"  Messages Received: {stats['messages_received']}")
        print(f"  Updates Processed: {stats['updates_processed']}")
        print(f"  Errors: {stats['errors']}")
        print(f"  Cache Size: {stats['cache_size']}")
        
        if stats['connected'] and stats['messages_received'] > 0:
            print(f"\n✅ WebSocket is working! Getting real-time prices.")
        else:
            print(f"\n⚠️  WebSocket connected but no data received yet (may need more time)")
            
    else:
        print(f"❌ Got None or invalid LTP: {ltp}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Cleanup
print("\n" + "=" * 80)
price_cache.stop()
auth.logout()
print("✅ Test complete")

