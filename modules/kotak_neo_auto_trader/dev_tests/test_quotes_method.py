#!/usr/bin/env python3
"""
Test getting LTP using quotes() method (plural)
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster

print("Testing quotes() method to get LTP")
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

# Test stocks
test_symbols = ["RELIANCE", "TCS", "HCLTECH", "DREAMFOLKS", "GALLANTT"]

print("Fetching LTP using quotes() method...")
print("-" * 80)

for symbol in test_symbols:
    print(f"\n{symbol}:")

    instrument = scrip_master.get_instrument(symbol)
    if not instrument:
        print(f"  ? Not found")
        continue

    token = instrument.get("token")
    trading_symbol = instrument.get("symbol")

    print(f"  Trading Symbol: {trading_symbol}")
    print(f"  Token: {token}")

    if not token:
        print(f"  ? No token")
        continue

    try:
        # Get sid from configuration
        sid = getattr(auth.client.configuration, "sid", None)

        # Use quotes() method with array of tokens and sid
        result = auth.client.quotes(
            instrument_tokens=[token],  # Must be a list
            quote_type="LTP",
            isIndex=False,
            sid=sid,  # Pass the sid from configuration
        )

        print(f"  Response type: {type(result)}")

        # Try to extract LTP
        if isinstance(result, dict):
            # Pretty print first to see structure
            import json

            print(f"  Response: {json.dumps(result, indent=2, default=str)[:500]}...")

            # Try to find LTP
            ltp = None

            # Check common response structures
            if "data" in result:
                data = result["data"]
                if isinstance(data, list) and len(data) > 0:
                    ltp_data = data[0]
                    ltp = (
                        ltp_data.get("ltp")
                        or ltp_data.get("LTP")
                        or ltp_data.get("lastPrice")
                        or ltp_data.get("last_price")
                        or ltp_data.get("pClose")
                    )
                elif isinstance(data, dict):
                    ltp = data.get("ltp") or data.get("LTP") or data.get("lastPrice")
            else:
                # Direct access
                ltp = result.get("ltp") or result.get("LTP") or result.get("lastPrice")

            if ltp:
                print(f"  ? LTP: Rs {ltp}")
            else:
                print(f"  [WARN]?  Could not find LTP in response")
        else:
            print(f"  Response: {result}")

    except Exception as e:
        print(f"  ? Error: {e}")
        import traceback

        traceback.print_exc()

print("\n" + "=" * 80)

# Logout
auth.logout()
print("? Done")
