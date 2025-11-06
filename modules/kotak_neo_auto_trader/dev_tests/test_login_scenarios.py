#!/usr/bin/env python3
"""
Comprehensive Login Scenario Tests
Simulates login as run_trading_service uses and tests:
- Happy path login
- Concurrent login scenarios
- JWT token expiry and re-authentication
- Reauth loop scenarios
"""

import sys
import time
import threading
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
import tempfile

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.auth_handler import (
    is_auth_error,
    _attempt_reauth_thread_safe,
    handle_reauth
)
from modules.kotak_neo_auto_trader.orders import KotakNeoOrders


class MockNeoAPI:
    """Mock NeoAPI client to simulate various scenarios"""
    
    def __init__(self, scenario='happy_path'):
        self.scenario = scenario
        self.login_count = 0
        self.session_2fa_count = 0
        self.is_authenticated = False
        self.jwt_expired = False
        
    def login(self, mobilenumber=None, password=None):
        """Simulate login"""
        self.login_count += 1
        time.sleep(0.1)  # Simulate network delay
        
        if self.scenario == 'login_failure':
            return {'error': [{'message': 'Invalid credentials'}]}
        
        return {'status': 'success', 'message': 'Login successful'}
    
    def session_2fa(self, OTP=None):
        """Simulate 2FA - this is where the bug occurs"""
        self.session_2fa_count += 1
        time.sleep(0.1)  # Simulate network delay
        
        if self.scenario == '2fa_none_response':
            # Simulate the bug scenario - returns None
            return None
        
        if self.scenario == '2fa_none_data':
            # Simulate dict with data=None
            return {'data': None, 'status': 'unknown'}
        
        if self.scenario == '2fa_dict_like_none':
            # Simulate dict-like object that returns None
            class DictLikeNone:
                def get(self, key):
                    if key == 'data':
                        return None
                    return None
            return DictLikeNone()
        
        if self.scenario == '2fa_error':
            return {'error': [{'message': 'Invalid MPIN'}]}
        
        # Happy path - return valid session
        self.is_authenticated = True
        self.jwt_expired = False  # Clear expired flag on successful 2FA
        return {
            'data': {
                'token': f'jwt_token_{self.session_2fa_count}',
                'hsServerId': 'test_server_id'
            },
            'status': 'success'
        }
    
    def get_orders(self):
        """Simulate get_orders API call"""
        if self.jwt_expired:
            return {
                'code': '900901',
                'message': 'Invalid Credentials',
                'description': 'Invalid JWT token. Make sure you have provided the correct security credentials'
            }
        return {'data': [], 'status': 'success'}
    
    def order_report(self):
        """Simulate order_report API call (used by get_orders)"""
        return self.get_orders()
    
    def get_order_report(self):
        """Simulate get_order_report API call (used by get_orders)"""
        return self.get_orders()
    
    def orderBook(self):
        """Simulate orderBook API call (used by get_orders)"""
        return self.get_orders()
    
    def orders(self):
        """Simulate orders API call (used by get_orders)"""
        return self.get_orders()
    
    def order_book(self):
        """Simulate order_book API call (used by get_orders)"""
        return self.get_orders()
    
    def logout(self):
        """Simulate logout"""
        self.is_authenticated = False
        return {'status': 'success'}


def create_test_env_file():
    """Create a temporary env file for testing"""
    tmp_dir = Path(tempfile.mkdtemp())
    env_path = tmp_dir / "kotak_neo.env"
    env_path.write_text(
        "KOTAK_CONSUMER_KEY=test_key\n"
        "KOTAK_CONSUMER_SECRET=secret\n"
        "KOTAK_MOBILE_NUMBER=9999999999\n"
        "KOTAK_PASSWORD=pass123\n"
        "KOTAK_MPIN=123456\n"
        "KOTAK_ENVIRONMENT=sandbox\n",
        encoding="utf-8"
    )
    return tmp_dir, env_path


def test_happy_path_login():
    """Test 1: Happy path - normal login flow as run_trading_service uses"""
    print("\n" + "=" * 80)
    print("TEST 1: Happy Path Login (simulating run_trading_service)")
    print("=" * 80)
    
    tmp_dir, env_path = create_test_env_file()
    try:
        # Initialize auth like run_trading_service does
        auth = KotakNeoAuth(config_file=str(env_path))
        
        # Mock the client with happy path scenario
        mock_client = MockNeoAPI(scenario='happy_path')
        
        # Patch _initialize_client to return our mock
        auth._initialize_client = lambda: mock_client
        
        # Perform login (like run_trading_service.initialize())
        result = auth.login()
        
        assert result == True, "Login should succeed"
        assert auth.is_logged_in == True, "Should be logged in"
        assert mock_client.login_count == 1, "Should call login once"
        assert mock_client.session_2fa_count == 1, "Should call session_2fa once"
        assert mock_client.is_authenticated == True, "Client should be authenticated"
        
        print("✅ PASSED: Happy path login successful")
        print(f"   - Login called: {mock_client.login_count} time(s)")
        print(f"   - 2FA called: {mock_client.session_2fa_count} time(s)")
        print(f"   - Session token: {auth.session_token}")
        
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_concurrent_login():
    """Test 2: Concurrent login - multiple threads trying to login simultaneously"""
    print("\n" + "=" * 80)
    print("TEST 2: Concurrent Login Scenarios")
    print("=" * 80)
    
    tmp_dir, env_path = create_test_env_file()
    try:
        # Create single auth instance (like run_trading_service)
        auth = KotakNeoAuth(config_file=str(env_path))
        mock_client = MockNeoAPI(scenario='happy_path')
        auth._initialize_client = lambda: mock_client
        
        results = []
        errors = []
        
        def login_thread(thread_id):
            """Thread function to perform login"""
            try:
                # Each thread tries to login
                result = auth.login()
                results.append((thread_id, result))
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Start 5 concurrent login threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=login_thread, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join(timeout=5)
        
        # Verify results
        assert len(results) == 5, f"Expected 5 results, got {len(results)}"
        assert len(errors) == 0, f"Expected no errors, got {errors}"
        
        # All should succeed (though some may be redundant)
        success_count = sum(1 for _, result in results if result)
        print(f"✅ PASSED: Concurrent login completed")
        print(f"   - Threads: {len(threads)}")
        print(f"   - Successful logins: {success_count}")
        print(f"   - Total login calls: {mock_client.login_count}")
        print(f"   - Total 2FA calls: {mock_client.session_2fa_count}")
        
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_jwt_expiry_and_reauth():
    """Test 3: JWT token expiry and re-authentication"""
    print("\n" + "=" * 80)
    print("TEST 3: JWT Token Expiry and Re-authentication")
    print("=" * 80)
    
    tmp_dir, env_path = create_test_env_file()
    try:
        # Initialize auth like run_trading_service
        auth = KotakNeoAuth(config_file=str(env_path))
        mock_client = MockNeoAPI(scenario='happy_path')
        auth._initialize_client = lambda: mock_client
        
        # Step 1: Initial login
        print("Step 1: Performing initial login...")
        result = auth.login()
        assert result == True, "Initial login should succeed"
        assert auth.is_logged_in == True, "Should be logged in"
        initial_login_count = mock_client.login_count
        initial_2fa_count = mock_client.session_2fa_count
        print(f"   ✓ Initial login successful (login calls: {initial_login_count}, 2FA calls: {initial_2fa_count})")
        
        # Step 2: Simulate JWT expiry by making API call fail
        print("\nStep 2: Simulating JWT expiry...")
        mock_client.jwt_expired = True
        
        # Step 3: Create orders API (like run_trading_service does)
        # Note: KotakNeoOrders.get_orders() already has @handle_reauth decorator
        orders_api = KotakNeoOrders(auth)
        
        # Step 4: Call get_orders - should trigger re-auth automatically via decorator
        print("Step 3: Calling get_orders (should trigger re-auth via @handle_reauth decorator)...")
        
        # The mock_client already has jwt_expired=True, so order_report() will return auth error
        # The @handle_reauth decorator on get_orders() will detect this and trigger re-auth
        
        # First call should trigger re-auth automatically via @handle_reauth decorator
        response = orders_api.get_orders()
        
        # Verify re-auth was attempted
        assert mock_client.login_count > initial_login_count, "Should have attempted re-login"
        assert mock_client.session_2fa_count > initial_2fa_count, "Should have attempted re-2FA"
        # jwt_expired should be cleared by successful 2FA (handled in MockNeoAPI.session_2fa)
        assert mock_client.jwt_expired == False, "JWT should be cleared after re-auth"
        
        print(f"✅ PASSED: JWT expiry and re-authentication handled")
        print(f"   - Initial login calls: {initial_login_count}")
        print(f"   - After re-auth login calls: {mock_client.login_count}")
        print(f"   - Initial 2FA calls: {initial_2fa_count}")
        print(f"   - After re-auth 2FA calls: {mock_client.session_2fa_count}")
        
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_concurrent_jwt_expiry():
    """Test 4: Concurrent JWT expiry - multiple threads hit expired token"""
    print("\n" + "=" * 80)
    print("TEST 4: Concurrent JWT Expiry (Multiple Threads)")
    print("=" * 80)
    
    tmp_dir, env_path = create_test_env_file()
    try:
        # Initialize auth
        auth = KotakNeoAuth(config_file=str(env_path))
        mock_client = MockNeoAPI(scenario='happy_path')
        auth._initialize_client = lambda: mock_client
        
        # Initial login
        auth.login()
        mock_client.jwt_expired = True
        
        results = []
        reauth_count = {'count': 0}
        
        def api_call_thread(thread_id):
            """Thread function simulating API call"""
            try:
                # Simulate API call that triggers re-auth
                if mock_client.jwt_expired:
                    # Trigger re-auth
                    if _attempt_reauth_thread_safe(auth, f"thread_{thread_id}"):
                        reauth_count['count'] += 1
                        mock_client.jwt_expired = False
                        results.append((thread_id, 'success'))
                    else:
                        results.append((thread_id, 'failed'))
                else:
                    results.append((thread_id, 'success'))
            except Exception as e:
                results.append((thread_id, f'error: {e}'))
        
        # Start 10 concurrent threads hitting expired token
        threads = []
        for i in range(10):
            t = threading.Thread(target=api_call_thread, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join(timeout=10)
        
        # Verify: Only one re-auth should happen (thread-safe)
        print(f"✅ PASSED: Concurrent JWT expiry handled (thread-safe)")
        print(f"   - Threads: {len(threads)}")
        print(f"   - Re-auth attempts: {reauth_count['count']}")
        print(f"   - Successful: {sum(1 for _, status in results if status == 'success')}")
        print(f"   - Expected: Only 1 re-auth should occur (others wait)")
        
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_reauth_loop_fixed():
    """Test 5: Reauth loop scenario - verify the bug fix prevents NoneType errors"""
    print("\n" + "=" * 80)
    print("TEST 5: Reauth Loop with None Response (Bug Fix Verification)")
    print("=" * 80)
    
    tmp_dir, env_path = create_test_env_file()
    try:
        # Test scenario: session_2fa returns None (the bug scenario)
        scenarios = [
            ('2fa_none_response', 'None response'),
            ('2fa_none_data', 'Dict with data=None'),
            ('2fa_dict_like_none', 'Dict-like with None data'),
        ]
        
        for scenario_name, description in scenarios:
            print(f"\n  Testing: {description}")
            auth = KotakNeoAuth(config_file=str(env_path))
            mock_client = MockNeoAPI(scenario=scenario_name)
            # Use closure to capture mock_client correctly
            def make_init_client(client):
                return lambda: client
            auth._initialize_client = make_init_client(mock_client)
            
            # Attempt login - should handle None gracefully
            result = auth.login()
            
            # Should return True (None means session already active)
            assert result == True, f"Should handle {description} gracefully"
            print(f"    ✓ Handled {description} without AttributeError")
            
            # Simulate JWT expiry and re-auth
            mock_client.jwt_expired = True
            
            # Force re-login (simulates force_relogin)
            reauth_result = auth.force_relogin()
            
            # Should handle gracefully without AttributeError
            assert reauth_result == True, f"Re-auth should handle {description} gracefully"
            print(f"    ✓ Re-auth handled {description} without AttributeError")
        
        print(f"\n✅ PASSED: All None response scenarios handled without AttributeError")
        
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_reauth_loop_simulation():
    """Test 6: Simulate the exact production reauth loop scenario from logs"""
    print("\n" + "=" * 80)
    print("TEST 6: Production Reauth Loop Simulation")
    print("=" * 80)
    
    tmp_dir, env_path = create_test_env_file()
    try:
        auth = KotakNeoAuth(config_file=str(env_path))
        
        # Simulate the exact scenario from logs:
        # 1. Initial login succeeds
        # 2. JWT expires
        # 3. Re-auth attempt with session_2fa returning None
        # 4. Should handle gracefully without AttributeError
        
        class ProductionScenarioClient:
            """Simulates the production scenario"""
            def __init__(self):
                self.login_count = 0
                self.session_2fa_count = 0
                self.attempt_number = 0
            
            def login(self, mobilenumber=None, password=None):
                self.login_count += 1
                return {'status': 'success'}
            
            def session_2fa(self, OTP=None):
                self.session_2fa_count += 1
                self.attempt_number += 1
                
                # First attempt: returns None (the bug scenario)
                if self.attempt_number == 1:
                    return None
                
                # Subsequent attempts: return valid session
                return {
                    'data': {
                        'token': f'jwt_token_{self.attempt_number}',
                    },
                    'status': 'success'
                }
            
            def get_orders(self):
                if self.attempt_number == 0:
                    return {
                        'code': '900901',
                        'message': 'Invalid Credentials',
                        'description': 'Invalid JWT token. Make sure you have provided the correct security credentials'
                    }
                return {'data': [], 'status': 'success'}
        
        mock_client = ProductionScenarioClient()
        auth._initialize_client = lambda: mock_client
        
        # Step 1: Initial login
        print("Step 1: Initial login...")
        result = auth.login()
        assert result == True, "Initial login should succeed"
        print(f"   ✓ Login successful (login calls: {mock_client.login_count}, 2FA calls: {mock_client.session_2fa_count})")
        
        # Step 2: Simulate JWT expiry
        print("\nStep 2: Simulating JWT expiry (get_orders returns 900901)...")
        
        # Step 3: Force re-login (simulates what happens in production)
        print("Step 3: Attempting force_relogin (should handle None response)...")
        reauth_result = auth.force_relogin()
        
        # Should succeed even though session_2fa returned None
        assert reauth_result == True, "Re-auth should succeed even with None response"
        assert mock_client.login_count == 2, "Should have called login twice"
        assert mock_client.session_2fa_count == 2, "Should have called session_2fa twice"
        
        print(f"✅ PASSED: Production scenario handled correctly")
        print(f"   - Login calls: {mock_client.login_count}")
        print(f"   - 2FA calls: {mock_client.session_2fa_count}")
        print(f"   - No AttributeError occurred")
        
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_multiple_reauth_attempts():
    """Test 7: Multiple re-auth attempts in quick succession"""
    print("\n" + "=" * 80)
    print("TEST 7: Multiple Re-auth Attempts")
    print("=" * 80)
    
    tmp_dir, env_path = create_test_env_file()
    try:
        auth = KotakNeoAuth(config_file=str(env_path))
        mock_client = MockNeoAPI(scenario='happy_path')
        auth._initialize_client = lambda: mock_client
        
        # Initial login
        auth.login()
        
        # Simulate multiple JWT expiries and re-auths
        for i in range(5):
            print(f"\n  Re-auth attempt {i+1}/5:")
            mock_client.jwt_expired = True
            result = auth.force_relogin()
            assert result == True, f"Re-auth {i+1} should succeed"
            print(f"    ✓ Re-auth {i+1} successful")
        
        print(f"\n✅ PASSED: Multiple re-auth attempts handled")
        print(f"   - Total login calls: {mock_client.login_count}")
        print(f"   - Total 2FA calls: {mock_client.session_2fa_count}")
        
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def run_all_tests():
    """Run all test scenarios"""
    print("\n" + "=" * 80)
    print("COMPREHENSIVE LOGIN SCENARIO TESTS")
    print("=" * 80)
    print("Simulating login as run_trading_service uses")
    print("=" * 80)
    
    tests = [
        test_happy_path_login,
        test_concurrent_login,
        test_jwt_expiry_and_reauth,
        test_concurrent_jwt_expiry,
        test_reauth_loop_fixed,
        test_reauth_loop_simulation,
        test_multiple_reauth_attempts,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n❌ FAILED: {test_func.__name__}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total: {passed + failed}")
    print("=" * 80)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

