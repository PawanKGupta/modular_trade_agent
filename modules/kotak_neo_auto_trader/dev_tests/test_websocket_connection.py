#!/usr/bin/env python3
"""
Test WebSocket connection and diagnose disconnection issues
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
from modules.kotak_neo_auto_trader.live_price_cache import LivePriceCache
from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster
from utils.logger import logger

print("=" * 80)
print("Testing WebSocket Connection with Improved Error Handling")
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

# Test symbols
test_symbols = ["RELIANCE", "TCS", "DALBHARAT"]
print(f"📊 Testing WebSocket with symbols: {', '.join(test_symbols)}")

# Initialize LivePriceCache
print("\n🔌 Initializing LivePriceCache...")
price_cache = LivePriceCache(
    auth_client=auth.client,
    scrip_master=scrip_master,
    stale_threshold_seconds=60,
    reconnect_delay_seconds=5
)

# Start WebSocket service
print("▶️  Starting WebSocket service...")
price_cache.start()

# Subscribe to test symbols
print(f"\n📡 Subscribing to {len(test_symbols)} symbols...")
price_cache.subscribe(test_symbols)

# Wait for connection
print("\n⏳ Waiting for WebSocket connection (max 15 seconds)...")
connection_established = price_cache.wait_for_connection(timeout=15)

if connection_established:
    print("✅ WebSocket connection established!")
else:
    print("❌ WebSocket connection timeout")

# Wait for data
print("\n⏳ Waiting for price data (max 20 seconds)...")
data_received = price_cache.wait_for_data(timeout=20)

if data_received:
    print("✅ Price data received!")
else:
    print("⚠️  No price data received yet")

# Monitor for 30 seconds
print("\n📊 Monitoring WebSocket for 30 seconds...")
print("-" * 80)

start_time = time.time()
last_stats_time = start_time
check_interval = 5  # Print stats every 5 seconds

try:
    while time.time() - start_time < 30:
        current_time = time.time()
        
        # Print stats periodically
        if current_time - last_stats_time >= check_interval:
            stats = price_cache.get_stats()
            is_connected = price_cache.is_connected()
            
            print(f"\n[{int(current_time - start_time)}s] Stats:")
            print(f"  Connected: {is_connected}")
            print(f"  Messages received: {stats.get('messages_received', 0)}")
            print(f"  Updates processed: {stats.get('updates_processed', 0)}")
            print(f"  Errors: {stats.get('errors', 0)}")
            print(f"  Reconnections: {stats.get('reconnections', 0)}")
            print(f"  Cache size: {stats.get('cache_size', 0)}")
            
            # Check for cached prices
            prices = price_cache.get_all_prices()
            if prices:
                print(f"  Cached prices: {len(prices)} symbols")
                for symbol, ltp in list(prices.items())[:3]:  # Show first 3
                    print(f"    {symbol}: ₹{ltp:.2f}")
            else:
                print(f"  Cached prices: None")
            
            if not is_connected:
                print(f"  ⚠️  WebSocket disconnected!")
            
            last_stats_time = current_time
        
        time.sleep(1)
        
except KeyboardInterrupt:
    print("\n\n⚠️  Interrupted by user")

# Final stats
print("\n" + "=" * 80)
print("Final Statistics:")
print("-" * 80)
stats = price_cache.get_stats()
print(f"Connected: {price_cache.is_connected()}")
print(f"Messages received: {stats.get('messages_received', 0)}")
print(f"Updates processed: {stats.get('updates_processed', 0)}")
print(f"Errors: {stats.get('errors', 0)}")
print(f"Reconnections: {stats.get('reconnections', 0)}")
print(f"Cache size: {stats.get('cache_size', 0)}")

# Test getting LTP
print("\n" + "=" * 80)
print("Testing LTP Retrieval:")
print("-" * 80)
for symbol in test_symbols:
    ltp = price_cache.get_ltp(symbol)
    if ltp:
        print(f"✅ {symbol}: ₹{ltp:.2f}")
    else:
        print(f"❌ {symbol}: No LTP available")

# Stop service
print("\n" + "=" * 80)
print("🛑 Stopping WebSocket service...")
price_cache.stop()

# Logout
print("\n🔓 Logging out...")
auth.logout()
print("✅ Test complete")

