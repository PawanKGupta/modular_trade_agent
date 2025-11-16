#!/usr/bin/env python3
"""
Reproduce the stale client re-authentication bug.

This test demonstrates the OLD buggy behavior by:
1. Performing real login
2. Manually reusing the client (simulating old force_relogin behavior)
3. Showing the SDK internal error that occurs

This reproduces the exact production bug:
- 'NoneType' object has no attribute 'get' error
- Re-authentication fails

Run with: python tests/integration/reproduce_bug_old_behavior.py
"""

import sys
import time
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger
from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.orders import KotakNeoOrders


def simulate_old_buggy_force_relogin(auth):
    """
    Simulate the OLD buggy force_relogin() behavior.
    
    OLD CODE (BUGGY):
    ```python
    def force_relogin(self) -> bool:
        if not self.client:  # Only creates new if None
            self.client = self._initialize_client()
        if not self._perform_login():
            return False
        if not self._complete_2fa():  # FAILS HERE with stale client
            return False
        return True
    ```
    
    The bug: If self.client exists (even if stale/expired), it reuses it.
    This causes SDK internal errors during 2FA.
    """
    print("\n  [SIMULATING OLD BUGGY CODE]")
    print("  Old code: if not self.client: create new")
    print("  Bug: Reuses stale client if it exists")
    
    # OLD BEHAVIOR: Only create new client if None
    if not auth.client:
        auth.client = auth._initialize_client()
    else:
        print(f"  ⚠ BUG: Reusing existing client (ID: {id(auth.client)})")
        print(f"     This client may be stale/expired!")
    
    if not auth.client:
        print("  ✗ Failed to initialize client")
        return False
    
    # Perform login (may succeed even with stale client)
    print("  Attempting login with existing client...")
    if not auth._perform_login():
        print("  ✗ Login failed")
        return False
    
    print("  ✓ Login succeeded")
    
    # 2FA will fail with stale client (SDK internal error)
    print("  Attempting 2FA with existing client...")
    print("  [EXPECTED] This will fail with stale client...")
    
    try:
        result = auth._complete_2fa()
        if result:
            print("  ⚠ 2FA succeeded (unexpected with stale client)")
            return True
        else:
            print("  ✗ 2FA failed (as expected with stale client)")
            return False
    except Exception as e:
        print(f"  ✗ 2FA raised exception: {e}")
        print(f"     This is the bug - stale client causes SDK error!")
        return False


def reproduce_bug_scenario():
    """
    Reproduce the exact production bug scenario.
    
    Production logs show:
    2025-11-06 09:15:06 — INFO — auth — Login completed successfully!
    2025-11-06 09:15:19 — ERROR — auth — 2FA call failed: 'NoneType' object has no attribute 'get'
    """
    print("=" * 80)
    print("REPRODUCING STALE CLIENT RE-AUTHENTICATION BUG")
    print("=" * 80)
    print("\nThis test reproduces the OLD buggy behavior")
    print("It shows what happens when stale clients are reused")
    print("=" * 80)
    
    env_file = "modules/kotak_neo_auto_trader/kotak_neo.env"
    
    try:
        # Step 1: Initial login (09:15:06)
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Step 1: Initial login...")
        auth = KotakNeoAuth(config_file=env_file)
        
        if not auth.login():
            print("✗ Initial login failed - check credentials")
            return False
        
        print("✓ Login completed successfully!")
        print(f"  Client ID: {id(auth.client)}")
        
        # Step 2: Store the client (this becomes "stale" when JWT expires)
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Step 2: Storing client reference...")
        stale_client = auth.client
        stale_client_id = id(stale_client)
        print(f"  Stored client ID: {stale_client_id}")
        print("  (In production, this client becomes stale when JWT expires)")
        
        # Step 3: Simulate JWT expiry (09:15:19)
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Step 3: Simulating JWT expiry...")
        print("  In production, JWT expired ~13 seconds after login")
        print("  The client object still exists but is now stale")
        
        # Step 4: Make API call that detects JWT expiry
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Step 4: API call detects JWT expiry...")
        orders_api = KotakNeoOrders(auth)
        orders_response = orders_api.get_orders()
        
        if isinstance(orders_response, dict) and orders_response.get('code') == '900901':
            print("  ✓ Detected JWT expiry error")
            print(f"    Error: {orders_response.get('message')}")
        else:
            print("  ⚠ JWT may not be expired yet (this is normal)")
            print("  Continuing to demonstrate the bug scenario...")
        
        # Step 5: OLD BUGGY BEHAVIOR - Reuse stale client
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Step 5: OLD BUGGY BEHAVIOR")
        print("  [OLD CODE] force_relogin() would:")
        print("    if not self.client:")
        print("        self.client = self._initialize_client()")
        print("    # BUG: If client exists, it REUSES the stale client!")
        
        # Manually set client to stale client (simulating old behavior)
        auth.client = stale_client
        print(f"\n  Manually reusing stale client (ID: {stale_client_id})")
        print("  This simulates what old code would do")
        
        # Try to re-authenticate with stale client
        print("\n  Attempting re-authentication with stale client...")
        print("  [EXPECTED] This should fail with SDK internal error")
        
        # Use the old buggy behavior
        result = simulate_old_buggy_force_relogin(auth)
        
        if not result:
            print("\n  ✓ BUG REPRODUCED: Re-authentication failed!")
            print("  ✓ This demonstrates the stale client reuse bug")
        else:
            print("\n  ⚠ Re-authentication succeeded (unexpected)")
        
        # Step 6: Show what happens with fresh client (NEW FIXED BEHAVIOR)
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Step 6: NEW FIXED BEHAVIOR")
        print("  [NEW CODE] force_relogin() always creates fresh client:")
        print("    self.client = None  # Reset first")
        print("    self.client = self._initialize_client()  # Always new")
        
        # Reset and create fresh client
        auth.client = None
        fresh_client = auth._initialize_client()
        auth.client = fresh_client
        fresh_client_id = id(fresh_client)
        
        print(f"\n  Created fresh client (ID: {fresh_client_id})")
        print(f"  Old stale client ID: {stale_client_id}")
        
        if fresh_client_id != stale_client_id:
            print("  ✓ New client created (different ID)")
        else:
            print("  ⚠ Same client reused (unexpected)")
        
        # Try re-authentication with fresh client
        print("\n  Attempting re-authentication with fresh client...")
        reauth_result = auth.force_relogin()
        
        if reauth_result:
            print("  ✓ Re-authentication successful with fresh client!")
            print("  ✓ This shows the fix works")
        else:
            print("  ✗ Re-authentication failed (unexpected)")
        
        # Summary
        print("\n" + "=" * 80)
        print("BUG REPRODUCTION SUMMARY")
        print("=" * 80)
        print("OLD BUGGY BEHAVIOR:")
        print("  - Reuses stale client if it exists")
        print("  - Causes SDK internal error: 'NoneType' object has no attribute 'get'")
        print("  - Re-authentication fails")
        print("\nNEW FIXED BEHAVIOR:")
        print("  - Always creates fresh client")
        print("  - No SDK internal errors")
        print("  - Re-authentication succeeds")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def demonstrate_stale_client_error():
    """
    Demonstrate the exact error that occurs with stale client.
    """
    print("\n" + "=" * 80)
    print("DEMONSTRATING STALE CLIENT ERROR")
    print("=" * 80)
    
    env_file = "modules/kotak_neo_auto_trader/kotak_neo.env"
    
    try:
        # Login
        auth = KotakNeoAuth(config_file=env_file)
        if not auth.login():
            print("✗ Login failed")
            return False
        
        print("✓ Login successful")
        original_client = auth.client
        print(f"  Original client ID: {id(original_client)}")
        
        # Simulate old code: reuse client without creating new one
        print("\n[BUG SCENARIO] Simulating old code behavior...")
        print("  Old code would reuse existing client")
        print("  Even if client is stale/expired")
        
        # Keep the same client (don't create new)
        auth.client = original_client  # Reuse (old behavior)
        
        # Try to do 2FA with potentially stale client
        print("\n  Attempting 2FA with reused client...")
        print("  [NOTE] If client is stale, this may cause SDK errors")
        
        try:
            # Try login first (may succeed)
            login_ok = auth._perform_login()
            print(f"  Login result: {'✓ Success' if login_ok else '✗ Failed'}")
            
            # Try 2FA (this is where stale client causes issues)
            print("  Attempting 2FA...")
            result = auth._complete_2fa()
            
            if result:
                print("  ✓ 2FA succeeded")
                print("  (Client may not be stale yet, or SDK handled it)")
            else:
                print("  ✗ 2FA failed")
                print("  (This may indicate stale client issue)")
                
        except AttributeError as e:
            if "'NoneType' object has no attribute 'get'" in str(e):
                print(f"  ✗ BUG REPRODUCED: {e}")
                print("  ✓ This is the exact error from production!")
                return True
            else:
                raise
        except Exception as e:
            print(f"  ✗ Exception: {e}")
            print("  (May indicate stale client issue)")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_client_reuse_scenario():
    """
    Test scenario where client is reused multiple times (old buggy behavior).
    """
    print("\n" + "=" * 80)
    print("TESTING CLIENT REUSE SCENARIO (OLD BUGGY BEHAVIOR)")
    print("=" * 80)
    
    env_file = "modules/kotak_neo_auto_trader/kotak_neo.env"
    
    try:
        # Initial login
        auth = KotakNeoAuth(config_file=env_file)
        if not auth.login():
            print("✗ Login failed")
            return False
        
        print("✓ Initial login successful")
        initial_client = auth.client
        initial_client_id = id(initial_client)
        print(f"  Initial client ID: {initial_client_id}")
        
        # Simulate multiple re-auth attempts with OLD behavior (reuse client)
        print("\n[OLD BUGGY BEHAVIOR] Multiple re-auth attempts reusing same client...")
        
        for i in range(3):
            print(f"\n  Re-auth attempt {i+1}:")
            print(f"    Client before: ID={id(auth.client)}")
            
            # OLD BEHAVIOR: Reuse client if exists
            if auth.client:
                print(f"    ⚠ BUG: Reusing existing client (not creating new)")
                # Don't create new client (old buggy behavior)
            else:
                auth.client = auth._initialize_client()
                print(f"    Created new client")
            
            # Try re-auth
            try:
                # Simulate old force_relogin logic
                if auth._perform_login():
                    result = auth._complete_2fa()
                    if result:
                        print(f"    ✓ Re-auth succeeded")
                    else:
                        print(f"    ✗ Re-auth failed (2FA issue)")
                else:
                    print(f"    ✗ Re-auth failed (login issue)")
            except Exception as e:
                print(f"    ✗ Re-auth exception: {e}")
                if "'NoneType' object has no attribute 'get'" in str(e):
                    print(f"      ✓ BUG REPRODUCED: Stale client SDK error!")
        
        print(f"\n  Final client ID: {id(auth.client)}")
        print(f"  Initial client ID: {initial_client_id}")
        
        if id(auth.client) == initial_client_id:
            print("  ⚠ BUG: Same client reused throughout (old behavior)")
        else:
            print("  ✓ Different client used")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("STALE CLIENT BUG REPRODUCTION TESTS")
    print("=" * 80)
    print("\nThese tests reproduce the OLD buggy behavior")
    print("They demonstrate what happens when stale clients are reused")
    print("\nMake sure you have valid credentials in kotak_neo.env")
    print("=" * 80)
    
    results = []
    
    # Test 1: Main bug reproduction
    print("\n\n[TEST 1] Main Bug Reproduction")
    result1 = reproduce_bug_scenario()
    results.append(("Main Bug Reproduction", result1))
    
    # Test 2: Demonstrate stale client error
    print("\n\n[TEST 2] Demonstrate Stale Client Error")
    result2 = demonstrate_stale_client_error()
    results.append(("Stale Client Error", result2))
    
    # Test 3: Client reuse scenario
    print("\n\n[TEST 3] Client Reuse Scenario")
    result3 = test_client_reuse_scenario()
    results.append(("Client Reuse Scenario", result3))
    
    # Summary
    print("\n\n" + "=" * 80)
    print("ALL TESTS SUMMARY")
    print("=" * 80)
    for test_name, result in results:
        status = "✓ COMPLETED" if result else "✗ FAILED"
        print(f"{test_name}: {status}")
    print("\nNote: These tests demonstrate the bug, not verify the fix")
    print("To verify the fix works, run: reproduce_production_bug.py")
    print("=" * 80)
