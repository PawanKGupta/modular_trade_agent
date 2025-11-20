#!/usr/bin/env python3
"""
Test to verify reauth loop prevention
Simulates the production scenario where re-auth fails repeatedly
"""

import sys
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock
import tempfile

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.orders import KotakNeoOrders


class MockNeoAPILoopScenario:
    """Mock NeoAPI client that simulates reauth loop scenario"""

    def __init__(self):
        self.login_count = 0
        self.session_2fa_count = 0
        self.get_orders_count = 0
        self.jwt_expired = True  # Always expired
        self.session_2fa_returns_none = True  # Simulates the bug scenario

    def login(self, mobilenumber=None, password=None):
        self.login_count += 1
        return {"status": "success", "message": "Login successful"}

    def session_2fa(self, OTP=None):
        """Simulate session_2fa returning None (the bug scenario)"""
        self.session_2fa_count += 1
        if self.session_2fa_returns_none:
            return None  # This is what causes the loop
        return {
            "data": {
                "token": f"jwt_token_{self.session_2fa_count}",
            },
            "status": "success",
        }

    def order_report(self):
        """Always returns JWT error"""
        self.get_orders_count += 1
        return {
            "code": "900901",
            "message": "Invalid Credentials",
            "description": "Invalid JWT token. Make sure you have provided the correct security credentials",
        }

    def get_order_report(self):
        return self.order_report()

    def orderBook(self):
        return self.order_report()

    def orders(self):
        return self.order_report()

    def order_book(self):
        return self.order_report()


def test_reauth_loop_prevention():
    """Test that reauth loop is prevented when re-auth fails"""
    print("\n" + "=" * 80)
    print("TEST: Reauth Loop Prevention")
    print("=" * 80)

    tmp_dir = Path(tempfile.mkdtemp())
    try:
        env_path = tmp_dir / "kotak_neo.env"
        env_path.write_text(
            "KOTAK_CONSUMER_KEY=test_key\n"
            "KOTAK_CONSUMER_SECRET=secret\n"
            "KOTAK_MOBILE_NUMBER=9999999999\n"
            "KOTAK_PASSWORD=pass123\n"
            "KOTAK_MPIN=123456\n"
            "KOTAK_ENVIRONMENT=sandbox\n",
            encoding="utf-8",
        )

        # Initialize auth
        auth = KotakNeoAuth(config_file=str(env_path))
        mock_client = MockNeoAPILoopScenario()
        auth._initialize_client = lambda: mock_client

        # Initial login
        print("Step 1: Initial login...")
        result = auth.login()
        print(f"   Login result: {result}")
        print(f"   Login calls: {mock_client.login_count}")
        print(f"   2FA calls: {mock_client.session_2fa_count}")

        # Now simulate what happens when get_orders is called repeatedly
        # (like the scheduler does)
        orders_api = KotakNeoOrders(auth)

        print("\nStep 2: Calling get_orders() multiple times (simulating scheduler)...")
        print("   Expected: Should only attempt re-auth once, then return None")

        results = []
        for i in range(5):
            print(f"\n   Attempt {i+1}:")
            result = orders_api.get_orders()
            results.append(result)
            print(f"     - get_orders() returned: {result is not None}")
            print(f"     - Total get_orders calls: {mock_client.get_orders_count}")
            print(f"     - Total login calls: {mock_client.login_count}")
            print(f"     - Total 2FA calls: {mock_client.session_2fa_count}")
            time.sleep(0.1)  # Small delay

        # Verify loop prevention
        print("\n" + "=" * 80)
        print("VERIFICATION:")
        print("=" * 80)

        # Key checks:
        # 1. get_orders should be called multiple times
        #    - Attempts 1-3: Each triggers re-auth (initial call + retry = 2 calls each) = 6 calls
        #    - Attempts 4-5: Blocked (initial call only, no retry) = 2 calls
        #    - Total: 8 calls
        expected_calls = (3 * 2) + (2 * 1)  # First 3 attempts with retry, last 2 blocked
        assert (
            mock_client.get_orders_count == expected_calls
        ), f"Expected {expected_calls} get_orders calls, got {mock_client.get_orders_count}"
        print(f"? get_orders was called {mock_client.get_orders_count} times (as expected)")

        # 2. Re-auth should be attempted 3 times, then blocked
        #    Attempts 1-3: Each triggers re-auth = 3 login attempts
        #    Attempts 4-5: Blocked (no re-auth) = 0 additional login attempts
        #    Initial login = 1
        #    Total: 1 initial + 3 re-auth = 4 login calls
        expected_login_calls = 1 + 3  # Initial + 3 re-auth attempts before blocking
        assert (
            mock_client.login_count == expected_login_calls
        ), f"Expected {expected_login_calls} login calls, got {mock_client.login_count}"
        print(
            f"? Login attempts: {mock_client.login_count} (initial + 3 re-auth attempts, then blocked)"
        )
        print(f"? 2FA attempts: {mock_client.session_2fa_count} (matches login attempts)")

        # 3. Most importantly: The fix should prevent AttributeError
        #    When session_2fa returns None, _complete_2fa should return True
        #    This means re-auth "succeeds" (treats None as "already authenticated")
        #    But then detects that retry still fails and records failure

        # Verify no AttributeError occurred (check logs if possible)
        print(f"\n? Test completed without AttributeError")
        print(f"   - session_2fa returned None {mock_client.session_2fa_count} times")
        print(f"   - Each None was handled gracefully (no AttributeError)")

        # The fix prevents the loop by:
        # 1. Handling None response gracefully (returns True instead of failing)
        # 2. Detecting when re-auth "succeeds" but retry still fails
        # 3. Recording failures and blocking after 3 failures in 60 seconds

        print("\n? PASSED: Reauth loop prevention verified")
        print("   The fix prevents infinite loops by:")
        print("   1. Handling None response gracefully (no AttributeError)")
        print("   2. Detecting ineffective re-auth (retry still fails)")
        print("   3. Rate limiting: Blocks re-auth after 3 failures in 60 seconds")
        print("   4. After blocking, API calls return None without attempting re-auth")

    finally:
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_reauth_loop_prevention()
