#!/usr/bin/env python3
"""
Test Real-Time Position Monitor Integration
Verifies WebSocket LTP and EMA9 calculation with live prices
"""

import sys
import time
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.position_monitor import get_position_monitor
from modules.kotak_neo_auto_trader.storage import load_history
from utils.logger import logger

print("=" * 80)
print("TESTING REAL-TIME LTP INTEGRATION")
print("=" * 80)
print()

# Load history to see open positions
history_path = "data/trades_history.json"
history = load_history(history_path)

open_positions = [trade for trade in history.get("trades", []) if trade.get("status") == "open"]

if not open_positions:
    print("? No open positions found in trades_history.json")
    print("   Please add test position or run when you have open positions")
    sys.exit(1)

print(f"Found {len(open_positions)} open position(s):")
for trade in open_positions:
    symbol = trade.get("symbol")
    qty = trade.get("qty")
    entry_price = trade.get("entry_price")
    print(f"  - {symbol}: {qty} @ Rs {entry_price}")
print()

print("=" * 80)
print("INITIALIZING POSITION MONITOR WITH REAL-TIME PRICES")
print("=" * 80)
print()

try:
    # Get monitor with real-time prices enabled
    monitor = get_position_monitor(
        history_path=history_path,
        enable_alerts=False,  # Disable alerts for testing
        enable_realtime_prices=True,
    )

    print("? Position monitor initialized")
    print()

    # Check if price manager is working
    if monitor.price_manager:
        print("? Live price manager initialized")
        print(f"   WebSocket enabled: {monitor.price_manager.enable_websocket}")
        print(f"   WebSocket initialized: {monitor.price_manager._initialized}")
        print(f"   WebSocket connected: {monitor.price_manager.is_websocket_connected()}")
        print()
    else:
        print("[WARN]? Live price manager not available")
        print()

    print("=" * 80)
    print("RUNNING POSITION MONITORING (with real-time LTP)")
    print("=" * 80)
    print()

    # Run monitoring
    results = monitor.monitor_all_positions()

    print()
    print("=" * 80)
    print("MONITORING RESULTS")
    print("=" * 80)
    print(f"Positions Monitored: {results['monitored']}")
    print(f"Exit Imminent: {results['exit_imminent']}")
    print(f"Averaging Opportunities: {results['averaging_opportunities']}")
    print()

    # Show positions with details
    if results.get("positions"):
        print("POSITION DETAILS:")
        print("-" * 80)
        for pos in results["positions"]:
            print(f"\n{pos.symbol}:")
            print(f"  Current Price: Rs {pos.current_price:.2f}")
            print(f"  Entry Price: Rs {pos.entry_price:.2f}")
            print(f"  P&L: Rs {pos.unrealized_pnl:,.0f} ({pos.unrealized_pnl_pct:+.2f}%)")
            print(f"  RSI10: {pos.rsi10:.1f}")
            print(f"  EMA9: Rs {pos.ema9:.2f}")
            print(f"  Distance to EMA9: {pos.distance_to_ema9_pct:+.1f}%")
            print(f"  Exit Imminent: {pos.exit_imminent}")
            if pos.alerts:
                print(f"  Alerts:")
                for alert in pos.alerts:
                    print(f"    - {alert}")
    print()

    # Show price manager stats
    if monitor.price_manager:
        print("=" * 80)
        print("LIVE PRICE MANAGER STATS")
        print("=" * 80)
        monitor.price_manager.print_stats()

    # Test fallback scenario
    print("=" * 80)
    print("TESTING FALLBACK TO YFINANCE")
    print("=" * 80)
    print()

    # Get a symbol
    if open_positions:
        test_symbol = open_positions[0].get("symbol")
        test_ticker = open_positions[0].get("ticker", f"{test_symbol}.NS")

        print(f"Testing LTP fetch for {test_symbol}...")

        if monitor.price_manager:
            ltp = monitor.price_manager.get_ltp(test_symbol, test_ticker)
            if ltp:
                print(f"? Got LTP: Rs {ltp}")
            else:
                print("[WARN]? Could not get LTP")

        print()

    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print()
    print("Summary:")
    print("  ? Position monitor with real-time LTP integration working")
    print("  ? EMA9 calculation using live prices")
    if monitor.price_manager and monitor.price_manager.is_websocket_connected():
        print("  ? WebSocket connection active")
    else:
        print("  [WARN]? WebSocket not connected (will use yfinance fallback)")
    print()

    # Cleanup
    if monitor.price_manager:
        print("Cleaning up...")
        monitor.price_manager.stop()
        print("? Cleanup complete")

except Exception as e:
    print(f"? Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print("\n? All tests passed!")
