#!/usr/bin/env python3
"""
Test SellOrderManager integration with LivePriceCache
This simulates the production setup where LivePriceCache is passed to SellOrderManager
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
print("Testing SellOrderManager with LivePriceCache (Production Integration)")
print("=" * 80)
print()

# Login
print("🔐 Logging in...")
auth = KotakNeoAuth("modules/kotak_neo_auto_trader/kotak_neo.env")
if not auth.login():
    print("❌ Login failed")
    sys.exit(1)

print("✅ Logged in successfully\n")

# Load scrip master
print("📋 Loading scrip master...")
scrip_master = KotakNeoScripMaster(auth_client=auth.client, exchanges=['NSE'])
if not scrip_master.load_scrip_master(force_download=False):
    print("❌ Failed to load scrip master")
    sys.exit(1)

print("✅ Scrip master loaded\n")

# Initialize LivePriceCache (like production does)
print("📊 Initializing LivePriceCache...")
price_cache = LivePriceCache(
    auth_client=auth.client,
    scrip_master=scrip_master,
    stale_threshold_seconds=60,
    reconnect_delay_seconds=5
)

# Start WebSocket service
print("▶️  Starting WebSocket service...")
price_cache.start()

# Wait for connection
print("⏳ Waiting for WebSocket connection...")
if price_cache.wait_for_connection(timeout=10):
    print("✅ WebSocket connected\n")
else:
    print("⚠️  Connection timeout\n")

# Subscribe to test symbols
test_symbols = ["RELIANCE", "TCS", "DALBHARAT"]
print(f"📡 Subscribing to {len(test_symbols)} symbols...")
price_cache.subscribe(test_symbols)
time.sleep(2)  # Wait for subscriptions to process

# Initialize SellOrderManager with LivePriceCache (like production does)
print("\n🔧 Initializing SellOrderManager with LivePriceCache...")
sell_manager = SellOrderManager(
    auth=auth,
    price_manager=price_cache  # Pass LivePriceCache directly (not LivePriceManager)
)

print("✅ SellOrderManager initialized\n")

# Test get_current_ltp() method (this is what fails in production)
print("=" * 80)
print("Testing get_current_ltp() method...")
print("=" * 80)
print()

for symbol in test_symbols:
    ticker = f"{symbol}.NS"
    print(f"Testing: {symbol}")
    print(f"  Ticker: {ticker}")
    
    try:
        # This is what sell_engine calls - should work with LivePriceCache now
        ltp = sell_manager.get_current_ltp(ticker=ticker, broker_symbol=f"{symbol}-EQ")
        
        if ltp is not None and ltp > 0:
            print(f"  ✅ LTP: ₹{ltp:.2f}")
        else:
            print(f"  ❌ Got None or invalid LTP: {ltp}")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print()

# Cleanup
print("=" * 80)
print("Cleaning up...")
price_cache.stop()
auth.logout()
print("✅ Done")

