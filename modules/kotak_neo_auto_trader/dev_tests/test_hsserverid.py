#!/usr/bin/env python3
"""
Quick test to check hsServerId after login
"""

import sys
import json
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth

print("Testing hsServerId after login")
print("=" * 80)

# Login
auth = KotakNeoAuth("modules/kotak_neo_auto_trader/kotak_neo.env")

# Clear cache to force fresh login
cache_path = Path(__file__).parent / "modules" / "kotak_neo_auto_trader" / "session_cache.json"
if cache_path.exists():
    cache_path.unlink()
    print("? Cleared session cache\n")

if not auth.login():
    print("? Login failed")
    sys.exit(1)

print("? Logged in\n")

# Check configuration
print("Configuration values:")
print("-" * 80)
print(f"edit_sid     : {auth.client.configuration.edit_sid}")
print(f"sid          : {auth.client.configuration.sid}")
print(f"serverId     : '{auth.client.configuration.serverId}'")
print(f"edit_rid     : {auth.client.configuration.edit_rid}")
print(f"userId       : {auth.client.configuration.userId}")

print("\n" + "=" * 80)

# Try quotes() with empty serverId
from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster

scrip_master = KotakNeoScripMaster(auth_client=auth.client, exchanges=["NSE"])
scrip_master.load_scrip_master(force_download=False)

instrument = scrip_master.get_instrument("RELIANCE")
token = instrument.get("token")

print(f"\nTrying quotes() for RELIANCE (token={token})")
print(f"  Passing sid='{auth.client.configuration.edit_sid}'")
print(f"  Passing server_id='{auth.client.configuration.serverId}'")

try:
    result = auth.client.quotes(
        instrument_tokens=[token],
        quote_type="LTP",
        isIndex=False,
        sid=auth.client.configuration.edit_sid,
        server_id=auth.client.configuration.serverId if auth.client.configuration.serverId else "",
    )
    print(f"? Success! Result: {json.dumps(result, indent=2, default=str)[:500]}")
except Exception as e:
    print(f"? Error: {e}")

auth.logout()
print("\n? Done")
