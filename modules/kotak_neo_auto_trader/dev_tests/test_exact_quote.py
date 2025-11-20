#!/usr/bin/env python3
"""
Test exact method: client.quote(instrument_token=token, quote_type="LTP")
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster

print("Testing EXACT syntax: client.quote(instrument_token=token, quote_type='LTP')")
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

# Get RELIANCE token
instrument = scrip_master.get_instrument("RELIANCE")
instrument_token = instrument.get("token")

print(f"RELIANCE Token: {instrument_token}\n")

# Try EXACT syntax as user specified
print("Attempting: self.client.quote(instrument_token={instrument_token}, quote_type='LTP')")
print("-" * 80)

try:
    # Check if quote() method exists
    if hasattr(auth.client, "quote"):
        print("[OK] quote() method exists on client")

        # Try exact syntax
        last_traded_price = auth.client.quote(instrument_token=instrument_token, quote_type="LTP")

        print(f"\n? SUCCESS!")
        print(f"Response type: {type(last_traded_price)}")
        print(f"Response: {last_traded_price}")

    else:
        print("[FAIL] quote() method does NOT exist on client")
        print("\nAvailable methods with 'quote' in name:")
        for method in dir(auth.client):
            if "quote" in method.lower() and not method.startswith("_"):
                print(f"  - {method}")

                # Show signature
                try:
                    import inspect

                    sig = inspect.signature(getattr(auth.client, method))
                    print(f"    Signature: {sig}")
                except Exception:
                    pass

except Exception as e:
    print(f"\n? FAILED with error: {e}")
    print(f"Error type: {type(e).__name__}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 80)

# Logout
auth.logout()
print("? Test complete")
