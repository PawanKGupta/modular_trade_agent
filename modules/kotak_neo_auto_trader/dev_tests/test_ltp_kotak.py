#!/usr/bin/env python3
"""
Test getting Last Traded Price (LTP) using instrument token
Based on pkgupta-orderapi implementation
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster

print("Testing LTP Retrieval using Instrument Token")
print("=" * 80)

# Login
auth = KotakNeoAuth("modules/kotak_neo_auto_trader/kotak_neo.env")
if not auth.login():
    print("? Login failed")
    sys.exit(1)

print("? Logged in successfully\n")

# Load scrip master
scrip_master = KotakNeoScripMaster(auth_client=auth.client, exchanges=["NSE"])
if not scrip_master.load_scrip_master(force_download=False):
    print("? Failed to load scrip master")
    sys.exit(1)

print("? Scrip master loaded\n")

# Test symbols
test_symbols = ["RELIANCE", "TCS", "HCLTECH", "INFY", "DREAMFOLKS"]

print("Testing LTP fetch for stocks...")
print("-" * 80)

for symbol in test_symbols:
    print(f"\n{symbol}:")

    # Get instrument data
    instrument = scrip_master.get_instrument(symbol)

    if not instrument:
        print(f"  ? Not found in scrip master")
        continue

    # Get token
    token = instrument.get("token")
    trading_symbol = instrument.get("symbol")

    print(f"  Trading Symbol: {trading_symbol}")
    print(f"  Token: {token}")

    if not token:
        print(f"  ? No instrument token available")
        continue

    # Try to fetch LTP
    try:
        # Check available methods on client
        if hasattr(auth.client, "quote"):
            print(f"  ? Trying quote() method...")

            try:
                # Try with instrument_token parameter
                result = auth.client.quote(instrument_token=token, quote_type="LTP")
                print(f"  Response type: {type(result)}")
                print(f"  Response: {result}")

                # Try to extract LTP
                if isinstance(result, dict):
                    ltp = (
                        result.get("ltp")
                        or result.get("LTP")
                        or result.get("lastPrice")
                        or result.get("last_price")
                        or result.get("lastTradedPrice")
                    )
                    if ltp:
                        print(f"  ? LTP: Rs {ltp}")
                    else:
                        print(f"  Keys in response: {list(result.keys())}")

            except TypeError as e:
                print(f"  [WARN]?  TypeError: {e}")
                print(f"  Trying with different parameters...")

                # Try alternative parameter names
                for param_name in ["instrumentToken", "inst_token", "symbol", "trading_symbol"]:
                    try:
                        result = auth.client.quote(**{param_name: token, "quote_type": "LTP"})
                        print(f"  ? Success with {param_name}: {result}")
                        break
                    except Exception:
                        continue

            except Exception as e:
                print(f"  ? Error: {e}")

        else:
            print(f"  ? quote() method not available on client")
            print(
                f"  Available methods: {[m for m in dir(auth.client) if 'quote' in m.lower() or 'price' in m.lower()]}"
            )

    except Exception as e:
        print(f"  ? Error: {e}")
        import traceback

        traceback.print_exc()

print("\n" + "=" * 80)
print("\nClient Method Analysis:")
print("-" * 80)

# List all relevant methods
quote_related = [
    m
    for m in dir(auth.client)
    if not m.startswith("_")
    and ("quote" in m.lower() or "price" in m.lower() or "ltp" in m.lower())
]
if quote_related:
    print("Quote/Price related methods:")
    for method in quote_related:
        print(f"  - {method}")
        # Try to get signature
        try:
            import inspect

            sig = inspect.signature(getattr(auth.client, method))
            print(f"    Signature: {sig}")
        except Exception:
            pass
else:
    print("No quote/price related methods found")

# Logout
print("\nLogging out...")
auth.logout()
print("? Done")
