#!/usr/bin/env python3
"""
Test script to validate login and diagnose WebSocket/LTP issues
"""

import sys
from pathlib import Path
import time

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger
from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster
from modules.kotak_neo_auto_trader.live_price_cache import LivePriceCache
from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
from modules.kotak_neo_auto_trader.orders import KotakNeoOrders

def main():
    print("=" * 80)
    print("Login and WebSocket Validation Test")
    print("=" * 80)
    print()
    
    config_file = "modules/kotak_neo_auto_trader/kotak_neo.env"
    
    # Step 1: Initialize and Login
    print("Step 1: Authentication")
    print("-" * 80)
    auth = KotakNeoAuth(config_file)
    print(f"✅ Auth initialized (Environment: {auth.environment})")
    
    login_success = auth.login()
    print(f"Login result: {'✅ SUCCESS' if login_success else '❌ FAILED'}")
    print()
    
    if not login_success:
        print("❌ Login failed - cannot proceed with tests")
        return 1
    
    # Step 2: Validate Login
    print("Step 2: Login Validation")
    print("-" * 80)
    is_valid, validation_details = auth.validate_login(test_api_call=True)
    
    print(f"Overall Status: {'✅ VALID' if is_valid else '❌ INVALID'}")
    print(f"  • Is Logged In: {'✅' if validation_details['is_logged_in'] else '❌'}")
    print(f"  • Client Exists: {'✅' if validation_details['client_exists'] else '❌'}")
    print(f"  • Session Token: {'✅' if validation_details['session_token_exists'] else '⚠️  Not set'}")
    
    if validation_details['api_test_passed'] is not None:
        api_status = '✅' if validation_details['api_test_passed'] else '❌'
        print(f"  • API Test: {api_status} - {validation_details['api_test_message']}")
    
    if validation_details['errors']:
        print("\n❌ Errors:")
        for error in validation_details['errors']:
            print(f"  • {error}")
    
    if validation_details['warnings']:
        print("\n⚠️  Warnings:")
        for warning in validation_details['warnings']:
            print(f"  • {warning}")
    
    print()
    
    if not is_valid:
        print("❌ Login validation failed - cannot proceed with WebSocket tests")
        return 1
    
    # Step 3: Test WebSocket Initialization
    print("Step 3: WebSocket Price Feed Initialization")
    print("-" * 80)
    
    try:
        # Initialize scrip master
        print("Loading scrip master...")
        scrip_master = KotakNeoScripMaster(
            auth_client=auth.client,
            exchanges=['NSE']
        )
        scrip_master.load_scrip_master(force_download=False)
        print("✅ Scrip master loaded")
        
        # Initialize LivePriceCache
        print("Initializing LivePriceCache...")
        price_cache = LivePriceCache(
            auth_client=auth.client,
            scrip_master=scrip_master,
            stale_threshold_seconds=60,
            reconnect_delay_seconds=5
        )
        
        # Start WebSocket service
        print("Starting WebSocket service...")
        price_cache.start()
        print("✅ WebSocket service started")
        
        # Wait for connection
        print("Waiting for WebSocket connection (timeout: 10s)...")
        if price_cache.wait_for_connection(timeout=10):
            print("✅ WebSocket connection established")
        else:
            print("⚠️  WebSocket connection timeout")
            print("   (This may be normal if market is closed or connection takes longer)")
        
        # Step 4: Test Symbol Subscription
        print()
        print("Step 4: Symbol Subscription Test")
        print("-" * 80)
        
        # Get pending sell orders to find symbols
        print("Getting pending sell orders...")
        orders_client = KotakNeoOrders(auth)
        pending_orders = orders_client.get_pending_orders()
        
        symbols = []
        if pending_orders:
            for order in pending_orders:
                symbol = order.get('trdSym') or order.get('tradingSymbol') or ''
                if symbol:
                    symbol = symbol.upper()
                    if symbol not in symbols:
                        symbols.append(symbol)
        
        if symbols:
            print(f"Found {len(symbols)} symbols with pending sell orders: {', '.join(symbols)}")
            print("Subscribing to WebSocket...")
            price_cache.subscribe(symbols)
            print(f"✅ Subscribed to: {', '.join(symbols)}")
            
            # Wait a moment for prices to arrive
            print("Waiting 3 seconds for initial price data...")
            time.sleep(3)
            
            # Test LTP retrieval
            print()
            print("Step 5: LTP Retrieval Test")
            print("-" * 80)
            
            for symbol in symbols[:3]:  # Test first 3 symbols
                print(f"\nTesting {symbol}:")
                ltp = price_cache.get_ltp(symbol)
                if ltp:
                    print(f"  ✅ WebSocket LTP: ₹{ltp:.2f}")
                else:
                    print(f"  ⚠️  No LTP data available yet (may need more time or symbol not found)")
                    
                    # Check if symbol is in cache
                    if hasattr(price_cache, 'price_cache'):
                        cache_keys = list(price_cache.price_cache.keys()) if hasattr(price_cache.price_cache, 'keys') else []
                        print(f"  Cache keys: {cache_keys[:5] if cache_keys else 'Empty'}")
        else:
            print("No pending sell orders found")
            print("Testing with DALBHARAT-EQ as example...")
            test_symbol = "DALBHARAT-EQ"
            print(f"Subscribing to {test_symbol}...")
            price_cache.subscribe([test_symbol])
            print("Waiting 3 seconds for price data...")
            time.sleep(3)
            
            ltp = price_cache.get_ltp(test_symbol)
            if ltp:
                print(f"✅ {test_symbol} LTP from WebSocket: ₹{ltp:.2f}")
            else:
                print(f"⚠️  {test_symbol} LTP not available from WebSocket")
        
        # Step 6: Test SellOrderManager Integration
        print()
        print("Step 6: SellOrderManager Integration Test")
        print("-" * 80)
        
        sell_manager = SellOrderManager(
            auth=auth,
            price_manager=price_cache
        )
        print("✅ SellOrderManager initialized with price_manager")
        
        # Test LTP retrieval through SellOrderManager
        if symbols:
            test_symbol_base = symbols[0].split('-')[0]  # Remove -EQ suffix
            test_ticker = f"{test_symbol_base}.NS"
            broker_symbol = symbols[0]
            
            print(f"\nTesting SellOrderManager.get_current_ltp() for {test_symbol_base}:")
            print(f"  Ticker: {test_ticker}")
            print(f"  Broker Symbol: {broker_symbol}")
            
            ltp = sell_manager.get_current_ltp(test_ticker, broker_symbol=broker_symbol)
            if ltp:
                print(f"  ✅ LTP retrieved: ₹{ltp:.2f}")
            else:
                print(f"  ⚠️  LTP not available (will fallback to yfinance)")
        
        # Cleanup
        print()
        print("Cleaning up...")
        price_cache.stop()
        print("✅ WebSocket stopped")
        
        print()
        print("=" * 80)
        print("✅ All tests completed")
        print("=" * 80)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error during WebSocket tests: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

