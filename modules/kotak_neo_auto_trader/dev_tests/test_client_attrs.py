#!/usr/bin/env python3
"""
Test to inspect client attributes for server_id/sid
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth

print("Inspecting client attributes after login")
print("=" * 80)

# Login
auth = KotakNeoAuth("modules/kotak_neo_auto_trader/kotak_neo.env")
if not auth.login():
    print("❌ Login failed")
    sys.exit(1)

print("✅ Logged in\n")

# Inspect all attributes
print("Client attributes (non-callable):")
print("-" * 80)
for attr in sorted(dir(auth.client)):
    if not attr.startswith('_'):
        try:
            val = getattr(auth.client, attr)
            if not callable(val):
                print(f"{attr:30s} = {val}")
        except Exception as e:
            print(f"{attr:30s} = <error: {e}>")

print("\n" + "=" * 80)
print("\nChecking specific attributes:")
print("-" * 80)

# Check for sid/server_id specifically
for attr in ['sid', 'server_id', 'serverId', 'session_token', 'access_token', 'bearer_token', 'auth_token']:
    if hasattr(auth.client, attr):
        val = getattr(auth.client, attr, None)
        print(f"✅ {attr}: {val}")
    else:
        print(f"❌ {attr}: not found")

# Check if there's a session or config object
print("\n" + "=" * 80)
print("\nChecking session/config objects:")
print("-" * 80)

if hasattr(auth.client, 'session'):
    print("✅ Found session object")
    session = auth.client.session
    for attr in sorted(dir(session)):
        if not attr.startswith('_'):
            try:
                val = getattr(session, attr)
                if not callable(val):
                    print(f"  session.{attr:25s} = {val}")
            except:
                pass

if hasattr(auth.client, 'configuration'):
    print("✅ Found configuration object")
    config = auth.client.configuration
    for attr in sorted(dir(config)):
        if not attr.startswith('_'):
            try:
                val = getattr(config, attr)
                if not callable(val):
                    print(f"  config.{attr:25s} = {val}")
            except:
                pass

print("\n" + "=" * 80)
auth.logout()
print("✅ Done")
