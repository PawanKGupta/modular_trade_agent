#!/usr/bin/env python3
"""
Test WebSocket subscribe() for live LTP streaming from Kotak Neo
"""

import sys
import time
import threading
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster

print("Testing WebSocket subscribe() for live LTP")
print("=" * 80)

# Login
auth = KotakNeoAuth("modules/kotak_neo_auto_trader/kotak_neo.env")
if not auth.login():
    print("? Login failed")
    sys.exit(1)

print("? Logged in\n")

# Load scrip master
scrip_master = KotakNeoScripMaster(auth_client=auth.client, exchanges=["NSE"])
scrip_master.load_scrip_master(force_download=False)
print("? Scrip master loaded\n")

# Get instrument tokens
test_symbols = ["RELIANCE", "TCS", "HCLTECH"]
instruments = {}
tokens = []  # Format: [{"instrument_token": 123, "exchange_segment": "nse_cm"}, ...]

for symbol in test_symbols:
    instrument = scrip_master.get_instrument(symbol)
    if instrument:
        token = instrument.get("token")
        trading_symbol = instrument.get("symbol")
        exchange = instrument.get("exchange", "NSE").lower()

        # Determine exchange segment
        if exchange == "nse":
            exchange_segment = "nse_cm"  # NSE Capital Market
        elif exchange == "bse":
            exchange_segment = "bse_cm"  # BSE Capital Market
        else:
            exchange_segment = "nse_cm"  # Default

        instruments[token] = {
            "symbol": symbol,
            "trading_symbol": trading_symbol,
            "exchange_segment": exchange_segment,
        }

        # WebSocket expects this format
        tokens.append({"instrument_token": token, "exchange_segment": exchange_segment})

        print(f"{symbol:12s} -> {trading_symbol:15s} (token: {token}, segment: {exchange_segment})")

print("\n" + "=" * 80)

# Track received messages
received_data = []
connection_opened = threading.Event()
first_data_received = threading.Event()


# Define callbacks
def on_message(message):
    """Called when live data arrives"""
    received_data.append(message)
    print(f"\n[LIVE DATA] {message}")
    first_data_received.set()


def on_error(error):
    """Called on WebSocket error"""
    print(f"\n[ERROR] {error}")


def on_open(message):
    """Called when WebSocket connection opens"""
    print(f"\n[CONNECTED] {message}")
    connection_opened.set()


def on_close(message):
    """Called when WebSocket connection closes"""
    print(f"\n[DISCONNECTED] {message}")


# Set callbacks
auth.client.on_message = on_message
auth.client.on_error = on_error
auth.client.on_open = on_open
auth.client.on_close = on_close

print("\nSetting up WebSocket callbacks...")
print("Callbacks configured:")
print("  - on_message: Receives live price updates")
print("  - on_error: Handles errors")
print("  - on_open: Connection established")
print("  - on_close: Connection closed")

print("\n" + "=" * 80)
print(f"\nSubscribing to {len(tokens)} instruments...")
print("This will stream live market data continuously.")
print("Press Ctrl+C to stop.\n")

try:
    # Subscribe to live feed
    auth.client.subscribe(
        instrument_tokens=tokens,
        isIndex=False,
        isDepth=False,  # Set True if you want order book depth
    )

    print("? Subscription request sent")
    print("\nWaiting for WebSocket connection to open...")

    # Wait for connection (with timeout)
    if connection_opened.wait(timeout=10):
        print("? WebSocket connected!")
        print("\nWaiting for first data message...")

        # Wait for first data (with timeout)
        if first_data_received.wait(timeout=10):
            print("\n? Receiving live data!")
            print("\nLet it stream for 15 seconds...")

            # Let it run for 15 seconds to collect data
            time.sleep(15)

            print(f"\n{'=' * 80}")
            print(f"\nReceived {len(received_data)} messages in 15 seconds")

            if received_data:
                print("\nSample of received data:")
                for i, msg in enumerate(received_data[:5]):  # Show first 5
                    print(f"\nMessage {i+1}:")
                    print(f"  {msg}")
        else:
            print("\n[WARN]?  Timeout waiting for data")
            print("   This might mean:")
            print("   - Market is closed")
            print("   - Invalid instrument tokens")
            print("   - WebSocket connection issue")
    else:
        print("\n[WARN]?  Timeout waiting for connection")
        print("   Check if serverId is required for WebSocket too")

except KeyboardInterrupt:
    print("\n\n[Interrupted by user]")
except Exception as e:
    print(f"\n? Error: {e}")
    import traceback

    traceback.print_exc()

finally:
    print("\n" + "=" * 80)
    print("\nUnsubscribing and closing connection...")

    try:
        # Unsubscribe
        if hasattr(auth.client, "un_subscribe"):
            auth.client.un_subscribe(instrument_tokens=tokens, isIndex=False, isDepth=False)
            print("? Unsubscribed")
    except Exception as e:
        print(f"[WARN]?  Unsubscribe failed: {e}")

    # Logout
    auth.logout()
    print("? Logged out")

    print("\n" + "=" * 80)
    print("\nSummary:")
    print(f"  Total messages received: {len(received_data)}")
    if received_data:
        print(f"  First message: {received_data[0]}")
        print(f"  Last message: {received_data[-1]}")
    else:
        print("  No data received - likely market closed or serverId issue")

    print("\n? Done")
