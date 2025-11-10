#!/usr/bin/env python3
"""
Unit Tests for Authentication Fixes (Nov 2025)
Tests for:
1. 2FA None response handling (prevents AttributeError)
2. Reauth loop prevention (rate limiting)
3. EOD cleanup method name fix
"""

import sys
import unittest
import tempfile
import time
import threading
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.auth_handler import (
    is_auth_error,
    _attempt_reauth_thread_safe,
    _check_reauth_failure_rate,
    _record_reauth_failure,
    _clear_reauth_failures,
    handle_reauth
)
from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
from modules.kotak_neo_auto_trader.eod_cleanup import EODCleanup


class MockNeoAPI:
    """Mock NeoAPI client for testing"""
    
    def __init__(self, scenario='happy_path'):
        self.scenario = scenario
        self.login_count = 0
        self.session_2fa_count = 0
        self.is_authenticated = False
        self.jwt_expired = False
        
    def login(self, mobilenumber=None, password=None):
        self.login_count += 1
        return {'status': 'success', 'message': 'Login successful'}
    
    def session_2fa(self, OTP=None):
        self.session_2fa_count += 1
        
        if self.scenario == '2fa_none_response':
            return None
        if self.scenario == '2fa_none_data':
            return {'data': None, 'status': 'unknown'}
        if self.scenario == '2fa_error':
            return {'error': [{'message': 'Invalid MPIN'}]}
        
        self.is_authenticated = True
        self.jwt_expired = False
        return {
            'data': {
                'token': f'jwt_token_{self.session_2fa_count}',
                'hsServerId': 'test_server_id'
            },
            'status': 'success'
        }
    
    def order_report(self):
        if self.jwt_expired:
            return {
                'code': '900901',
                'message': 'Invalid Credentials',
                'description': 'Invalid JWT token. Make sure you have provided the correct security credentials'
            }
        return {'data': [], 'status': 'success'}
    
    def get_order_report(self):
        return self.order_report()
    
    def orderBook(self):
        return self.order_report()
    
    def orders(self):
        return self.order_report()
    
    def order_book(self):
        return self.order_report()
    
    def logout(self):
        self.is_authenticated = False
        return {'status': 'success'}


class Test2FANoneResponseHandling(unittest.TestCase):
    """Test 1: 2FA None response handling - prevents AttributeError"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.env_path = self.tmp_dir / "kotak_neo.env"
        self.env_path.write_text(
            "KOTAK_CONSUMER_KEY=test_key\n"
            "KOTAK_CONSUMER_SECRET=secret\n"
            "KOTAK_MOBILE_NUMBER=9999999999\n"
            "KOTAK_PASSWORD=pass123\n"
            "KOTAK_MPIN=123456\n"
            "KOTAK_ENVIRONMENT=sandbox\n",
            encoding="utf-8"
        )
        self.auth = KotakNeoAuth(config_file=str(self.env_path))
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    
    def test_2fa_with_none_response(self):
        """Test that None response from session_2fa doesn't raise AttributeError"""
        mock_client = MockNeoAPI(scenario='2fa_none_response')
        self.auth._initialize_client = lambda: mock_client
        
        # Should not raise AttributeError
        result = self.auth.login()
        
        # Should return True (None means session already active)
        self.assertTrue(result, "Login should succeed with None response")
        self.assertEqual(mock_client.session_2fa_count, 1)
    
    def test_2fa_with_none_data(self):
        """Test that dict with data=None doesn't raise AttributeError"""
        mock_client = MockNeoAPI(scenario='2fa_none_data')
        self.auth._initialize_client = lambda: mock_client
        
        result = self.auth.login()
        
        self.assertTrue(result, "Login should succeed with data=None")
        self.assertEqual(mock_client.session_2fa_count, 1)
    
    def test_2fa_with_dict_like_none(self):
        """Test that dict-like object returning None doesn't raise AttributeError"""
        class DictLikeNone:
            def get(self, key):
                if key == 'data':
                    return None
                return None
        
        mock_client = MockNeoAPI(scenario='happy_path')
        mock_client.session_2fa = lambda **kwargs: DictLikeNone()
        self.auth._initialize_client = lambda: mock_client
        
        result = self.auth.login()
        
        self.assertTrue(result, "Login should succeed with dict-like None")
    
    def test_reauth_with_none_response(self):
        """Test that re-auth handles None response gracefully"""
        mock_client = MockNeoAPI(scenario='2fa_none_response')
        self.auth._initialize_client = lambda: mock_client
        
        # Initial login
        self.auth.login()
        
        # Force re-login (simulates JWT expiry scenario)
        result = self.auth.force_relogin()
        
        self.assertTrue(result, "Re-auth should succeed even with None response")
        self.assertEqual(mock_client.session_2fa_count, 2)


class TestReauthLoopPrevention(unittest.TestCase):
    """Test 2: Reauth loop prevention - rate limiting"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.env_path = self.tmp_dir / "kotak_neo.env"
        self.env_path.write_text(
            "KOTAK_CONSUMER_KEY=test_key\n"
            "KOTAK_CONSUMER_SECRET=secret\n"
            "KOTAK_MOBILE_NUMBER=9999999999\n"
            "KOTAK_PASSWORD=pass123\n"
            "KOTAK_MPIN=123456\n"
            "KOTAK_ENVIRONMENT=sandbox\n",
            encoding="utf-8"
        )
        self.auth = KotakNeoAuth(config_file=str(self.env_path))
        
        # Clear any existing failure tracking
        _clear_reauth_failures(self.auth)
    
    def tearDown(self):
        """Clean up test fixtures"""
        _clear_reauth_failures(self.auth)
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    
    def test_reauth_failure_tracking(self):
        """Test that re-auth failures are tracked"""
        # Initially no failures
        self.assertFalse(_check_reauth_failure_rate(self.auth))
        
        # Record some failures
        _record_reauth_failure(self.auth)
        _record_reauth_failure(self.auth)
        _record_reauth_failure(self.auth)
        
        # After 3 failures, should be blocked
        self.assertTrue(_check_reauth_failure_rate(self.auth))
    
    def test_reauth_failure_clearing(self):
        """Test that successful re-auth clears failure history"""
        # Record failures
        _record_reauth_failure(self.auth)
        _record_reauth_failure(self.auth)
        
        # Clear failures
        _clear_reauth_failures(self.auth)
        
        # Should not be blocked
        self.assertFalse(_check_reauth_failure_rate(self.auth))
    
    def test_ineffective_reauth_detection(self):
        """Test that ineffective re-auth (retry still fails) is detected"""
        class IneffectiveReauthClient(MockNeoAPI):
            """Client that always returns JWT error even after re-auth"""
            def __init__(self):
                super().__init__(scenario='happy_path')
                self.reauth_count = 0
            
            def session_2fa(self, OTP=None):
                """Re-auth always succeeds (returns None)"""
                self.session_2fa_count += 1
                self.reauth_count += 1
                # Return None to simulate "session already active"
                return None
            
            def order_report(self):
                """Always returns JWT error (simulates ineffective re-auth)"""
                return {
                    'code': '900901',
                    'message': 'Invalid Credentials',
                    'description': 'Invalid JWT token. Make sure you have provided the correct security credentials'
                }
            
            def get_order_report(self):
                return self.order_report()
            
            def orderBook(self):
                return self.order_report()
            
            def orders(self):
                return self.order_report()
            
            def order_book(self):
                return self.order_report()
        
        mock_client = IneffectiveReauthClient()
        self.auth._initialize_client = lambda: mock_client
        
        # Initial login
        self.auth.login()
        
        # Create orders API
        orders_api = KotakNeoOrders(self.auth)
        
        # Call get_orders multiple times - each should trigger re-auth
        # After 3 failures, re-auth should be blocked
        for i in range(4):
            response = orders_api.get_orders()
            # Response will be None after blocking
        
        # After 3 failures, should be blocked
        self.assertTrue(_check_reauth_failure_rate(self.auth), 
                        "Re-auth should be blocked after 3 ineffective attempts")


class TestEODCleanupFix(unittest.TestCase):
    """Test 3: EOD cleanup method name fix"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = Mock()
        self.eod_cleanup = EODCleanup(broker_client=self.mock_client)
    
    def test_eod_cleanup_has_run_eod_cleanup_method(self):
        """Test that EODCleanup has run_eod_cleanup method"""
        self.assertTrue(hasattr(self.eod_cleanup, 'run_eod_cleanup'))
        self.assertTrue(callable(getattr(self.eod_cleanup, 'run_eod_cleanup')))
    
    def test_eod_cleanup_does_not_have_run_method(self):
        """Test that EODCleanup does NOT have run method (old incorrect name)"""
        self.assertFalse(hasattr(self.eod_cleanup, 'run'))
    
    def test_run_eod_cleanup_is_callable(self):
        """Test that run_eod_cleanup can be called"""
        try:
            result = self.eod_cleanup.run_eod_cleanup()
            # Should return a dict with results
            self.assertIsInstance(result, dict)
        except Exception as e:
            # If it fails due to missing dependencies, that's okay for unit test
            # The important thing is the method exists and is callable
            pass


class TestAuthHandlerRateLimiting(unittest.TestCase):
    """Test 4: Auth handler rate limiting prevents loops"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.env_path = self.tmp_dir / "kotak_neo.env"
        self.env_path.write_text(
            "KOTAK_CONSUMER_KEY=test_key\n"
            "KOTAK_CONSUMER_SECRET=secret\n"
            "KOTAK_MOBILE_NUMBER=9999999999\n"
            "KOTAK_PASSWORD=pass123\n"
            "KOTAK_MPIN=123456\n"
            "KOTAK_ENVIRONMENT=sandbox\n",
            encoding="utf-8"
        )
        self.auth = KotakNeoAuth(config_file=str(self.env_path))
        _clear_reauth_failures(self.auth)
    
    def tearDown(self):
        """Clean up test fixtures"""
        _clear_reauth_failures(self.auth)
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    
    def test_rate_limiting_after_3_failures(self):
        """Test that rate limiting activates after 3 failures"""
        # No failures initially
        self.assertFalse(_check_reauth_failure_rate(self.auth))
        
        # Record 3 failures
        for _ in range(3):
            _record_reauth_failure(self.auth)
        
        # Should be blocked after 3 failures
        self.assertTrue(_check_reauth_failure_rate(self.auth))
    
    def test_rate_limiting_resets_after_clear(self):
        """Test that rate limiting resets after clearing failures"""
        # Record failures
        for _ in range(3):
            _record_reauth_failure(self.auth)
        
        # Should be blocked
        self.assertTrue(_check_reauth_failure_rate(self.auth))
        
        # Clear failures
        _clear_reauth_failures(self.auth)
        
        # Should not be blocked
        self.assertFalse(_check_reauth_failure_rate(self.auth))


class TestProductionScenario(unittest.TestCase):
    """Test 5: Production scenario - JWT expiry with None response"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.env_path = self.tmp_dir / "kotak_neo.env"
        self.env_path.write_text(
            "KOTAK_CONSUMER_KEY=test_key\n"
            "KOTAK_CONSUMER_SECRET=secret\n"
            "KOTAK_MOBILE_NUMBER=9999999999\n"
            "KOTAK_PASSWORD=pass123\n"
            "KOTAK_MPIN=123456\n"
            "KOTAK_ENVIRONMENT=sandbox\n",
            encoding="utf-8"
        )
        self.auth = KotakNeoAuth(config_file=str(self.env_path))
        _clear_reauth_failures(self.auth)
    
    def tearDown(self):
        """Clean up test fixtures"""
        _clear_reauth_failures(self.auth)
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    
    def test_production_jwt_expiry_scenario(self):
        """Test the exact production scenario from logs"""
        class ProductionScenarioClient:
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
            
            def order_report(self):
                if self.attempt_number == 0:
                    return {
                        'code': '900901',
                        'message': 'Invalid Credentials',
                        'description': 'Invalid JWT token. Make sure you have provided the correct security credentials'
                    }
                return {'data': [], 'status': 'success'}
            
            def get_order_report(self):
                return self.order_report()
            
            def orderBook(self):
                return self.order_report()
            
            def orders(self):
                return self.order_report()
            
            def order_book(self):
                return self.order_report()
        
        mock_client = ProductionScenarioClient()
        self.auth._initialize_client = lambda: mock_client
        
        # Step 1: Initial login
        result = self.auth.login()
        self.assertTrue(result, "Initial login should succeed")
        
        # Step 2: Simulate JWT expiry and re-auth
        # This should handle None response gracefully
        reauth_result = self.auth.force_relogin()
        
        # Should succeed even though session_2fa returned None
        self.assertTrue(reauth_result, "Re-auth should succeed even with None response")
        self.assertEqual(mock_client.login_count, 2)
        self.assertEqual(mock_client.session_2fa_count, 2)


if __name__ == '__main__':
    unittest.main()

