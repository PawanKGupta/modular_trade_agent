#!/usr/bin/env python3
"""
Diagnostic test for LivePriceCache WebSocket connection issues
Tests the connection and logs detailed information
"""

import sys
import time
from pathlib import Path

# Add project root to path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent.parent.resolve()
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster
from modules.kotak_neo_auto_trader.live_price_cache import LivePriceCache

print("=" * 80)
print("LivePriceCache WebSocket Diagnostic Test")
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
test_symbols = ["DALBHARAT", "RELIANCE", "TCS"]
print(f"Testing with symbols: {', '.join(test_symbols)}")
print("-" * 80)

# Initialize LivePriceCache
print("\n📊 Initializing LivePriceCache...")
price_cache = LivePriceCache(
    auth_client=auth.client,
    scrip_master=scrip_master,
    stale_threshold_seconds=60,
    reconnect_delay_seconds=5
)

print("✅ LivePriceCache initialized")

# Start the service
print("\n🚀 Starting WebSocket service...")
price_cache.start()
print("✅ WebSocket service started")

# Wait a moment for initialization
time.sleep(2)

# Subscribe to symbols
print(f"\n📡 Subscribing to {len(test_symbols)} symbols...")
price_cache.subscribe(test_symbols)
print("✅ Subscription request sent")

# Wait for connection
print("\n⏳ Waiting for WebSocket connection (timeout: 10s)...")
connected = price_cache.wait_for_connection(timeout=10.0)

if connected:
    print("✅ WebSocket connected!")
else:
    print("❌ WebSocket connection timeout - connection not established")

# Wait for data
print("\n⏳ Waiting for first price data (timeout: 15s)...")
data_received = price_cache.wait_for_data(timeout=15.0)

if data_received:
    print("✅ Price data received!")
else:
    print("⚠️  No price data received yet")

# Monitor for 30 seconds
print("\n" + "=" * 80)
print("Monitoring WebSocket for 30 seconds...")
print("=" * 80)

start_time = time.time()
check_interval = 5
last_stats = None

while time.time() - start_time < 30:
    time.sleep(check_interval)
    
    # Get current stats
    stats = price_cache.get_stats()
    
    # Print stats if they changed
    if stats != last_stats:
        print(f"\n[{int(time.time() - start_time)}s] Current Status:")
        print(f"  Connected: {stats['connected']}")
        print(f"  Messages Received: {stats['messages_received']}")
        print(f"  Updates Processed: {stats['updates_processed']}")
        print(f"  Errors: {stats['errors']}")
        print(f"  Reconnections: {stats['reconnections']}")
        print(f"  Subscriptions: {stats['subscriptions']}")
        print(f"  Cache Size: {stats['cache_size']}")
        
        if stats['last_update']:
            print(f"  Last Update: {stats['last_update']}")
        
        # Try to get prices
        print(f"\n  Current Prices:")
        for symbol in test_symbols:
            ltp = price_cache.get_ltp(symbol)
            if ltp:
                print(f"    {symbol}: ₹{ltp:.2f}")
            else:
                print(f"    {symbol}: Not available")
        
        last_stats = stats

# Final stats
print("\n" + "=" * 80)
print("Final Statistics:")
print("=" * 80)
final_stats = price_cache.get_stats()
for key, value in final_stats.items():
    print(f"  {key}: {value}")

# Final prices
print("\nFinal Cached Prices:")
prices = price_cache.get_all_prices()
if prices:
    for symbol, ltp in prices.items():
        print(f"  {symbol}: ₹{ltp:.2f}")
else:
    print("  No prices in cache")

# Stop the service
print("\n🛑 Stopping WebSocket service...")
price_cache.stop()
print("✅ Service stopped")

# Logout
print("\n🔓 Logging out...")
auth.logout()
print("✅ Done")

