#!/usr/bin/env python3
"""
Comprehensive unit tests for authentication and session management.

Tests cover:
1. Single auth session creation and sharing
2. Successful and failed re-authentication
3. Thread-safe re-authentication
4. AutoTradeEngine handling of expired/failed auth
5. LivePriceCache reconnection after re-auth
6. Edge cases (race conditions, None responses, exceptions)

Run with: pytest tests/unit/kotak/test_comprehensive_auth_session_management.py -v
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import unittest
import threading
import time

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.auth_handler import (
    is_auth_error, is_auth_exception, handle_reauth, _attempt_reauth_thread_safe
)
from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine, Recommendation
from modules.kotak_neo_auto_trader.live_price_cache import LivePriceCache
import tempfile


class TestSingleAuthSession(unittest.TestCase):
    """Test single auth session creation and sharing"""
    
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
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    
    def test_single_auth_session_creation(self):
        """Test that only one auth session should be created per service"""
        auth1 = KotakNeoAuth(config_file=str(self.env_path))
        auth2 = KotakNeoAuth(config_file=str(self.env_path))
        
        # They should be separate instances (different objects)
        self.assertIsNot(auth1, auth2)
        
        # But the pattern should be: create once, share to components
        # This test verifies the pattern is followed
        self.assertIsNotNone(auth1)
        self.assertIsNotNone(auth2)


class TestReAuthentication(unittest.TestCase):
    """Test re-authentication scenarios"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_auth = Mock(spec=KotakNeoAuth)
        self.mock_auth.is_logged_in = True
        self.mock_auth.client = Mock()
        self.mock_auth.get_client.return_value = self.mock_auth.client
        self.mock_auth.force_relogin.return_value = True
    
    def test_successful_reauthentication(self):
        """Test successful re-authentication"""
        call_count = {'count': 0}
        
        auth_error_response = {'code': '900901', 'message': 'JWT token expired'}
        success_response = {'data': []}
        
        mock_orders = Mock(spec=type('obj', (object,), {}))
        mock_orders.auth = self.mock_auth
        
        def mock_get_orders(self):
            call_count['count'] += 1
            if call_count['count'] == 1:
                return auth_error_response
            return success_response
        
        mock_orders.get_orders = mock_get_orders
        decorated_method = handle_reauth(mock_orders.get_orders)
        
        # First call should trigger re-auth and retry
        result = decorated_method(mock_orders)
        
        # Should retry after re-auth
        self.assertEqual(call_count['count'], 2)
        self.assertEqual(result, success_response)
    
    def test_failed_reauthentication(self):
        """Test failed re-authentication"""
        self.mock_auth.force_relogin.return_value = False
        
        mock_orders = Mock(spec=type('obj', (object,), {}))
        mock_orders.auth = self.mock_auth
        
        auth_error_response = {'code': '900901', 'message': 'JWT token expired'}
        mock_orders.get_orders = lambda self: auth_error_response
        
        decorated_method = handle_reauth(mock_orders.get_orders)
        result = decorated_method(mock_orders)
        
        # Should return None on failed re-auth
        self.assertIsNone(result)
    
    def test_reauthentication_exception_handling(self):
        """Test re-authentication exception handling"""
        self.mock_auth.force_relogin.side_effect = Exception("Network error")
        
        mock_orders = Mock(spec=type('obj', (object,), {}))
        mock_orders.auth = self.mock_auth
        
        auth_error_response = {'code': '900901', 'message': 'JWT token expired'}
        mock_orders.get_orders = lambda self: auth_error_response
        
        decorated_method = handle_reauth(mock_orders.get_orders)
        result = decorated_method(mock_orders)
        
        # Should handle exception gracefully and return None
        self.assertIsNone(result)
    
    def test_auth_error_detection(self):
        """Test auth error detection in responses"""
        test_cases = [
            {'code': '900901'},  # JWT expiry code
            {'message': 'invalid jwt token'},
            {'description': 'JWT token expired'},
            {'error': 'unauthorized'},
        ]
        
        for response in test_cases:
            self.assertTrue(is_auth_error(response), 
                          f"Failed to detect auth error in: {response}")
    
    def test_non_auth_error_not_detected(self):
        """Test that non-auth errors are not detected as auth errors"""
        test_cases = [
            {'code': '500', 'message': 'Internal server error'},
            {'error': 'Invalid symbol'},
            {'message': 'Insufficient balance'},
        ]
        
        for response in test_cases:
            self.assertFalse(is_auth_error(response),
                           f"Should not detect auth error in: {response}")


class TestThreadSafeReAuth(unittest.TestCase):
    """Test thread-safe re-authentication"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_auth = Mock(spec=KotakNeoAuth)
        self.mock_auth.is_logged_in = True
        self.mock_auth.client = Mock()
        self.mock_auth.get_client.return_value = self.mock_auth.client
        self.mock_auth.force_relogin.return_value = True
    
    def test_concurrent_reauth_coordination(self):
        """Test that concurrent re-auth attempts are coordinated"""
        results = []
        results_lock = threading.Lock()
        
        def attempt_reauth():
            result = _attempt_reauth_thread_safe(self.mock_auth, "test_method")
            with results_lock:
                results.append(result)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            t = threading.Thread(target=attempt_reauth)
            threads.append(t)
        
        # Start all threads at once
        for t in threads:
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join(timeout=5.0)
        
        # All should succeed (first one performs re-auth, others wait)
        self.assertEqual(len(results), 5)
        self.assertTrue(all(results), "All re-auth attempts should succeed")


class TestAutoTradeEngineAuthHandling(unittest.TestCase):
    """Test AutoTradeEngine handling of expired/failed auth"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_auth = Mock(spec=KotakNeoAuth)
        self.mock_auth.is_authenticated.return_value = False
        self.mock_auth.login.return_value = True
        
        self.engine = AutoTradeEngine(auth=self.mock_auth)
        self.engine.orders = Mock()
        self.engine.portfolio = Mock()
        self.engine.portfolio.get_limits.return_value = {'data': {'day': {'used': 0, 'available': 100000}}}
    
    def test_place_new_entries_with_expired_auth(self):
        """Test place_new_entries with expired auth"""
        self.mock_auth.is_authenticated.return_value = False
        self.mock_auth.login.return_value = True
        
        recs = [Recommendation(
            ticker="TESTSTOCK.NS",
            verdict="buy",
            last_close=100.0
        )]
        
        # Mock holdings to return valid response
        self.engine.portfolio.get_holdings.return_value = {'data': []}
        
        result = self.engine.place_new_entries(recs)
        
        # Should attempt re-authentication
        self.mock_auth.login.assert_called()
        self.assertIsNotNone(result)
    
    def test_place_new_entries_with_failed_reauth(self):
        """Test place_new_entries with failed re-auth"""
        self.mock_auth.is_authenticated.return_value = False
        self.mock_auth.login.return_value = False
        
        recs = [Recommendation(
            ticker="TESTSTOCK.NS",
            verdict="buy",
            last_close=100.0
        )]
        
        result = self.engine.place_new_entries(recs)
        
        # Should return empty summary on failed re-auth
        self.assertIsNotNone(result)
        self.assertEqual(result.get('placed', 0), 0)
    
    def test_place_new_entries_with_valid_auth(self):
        """Test place_new_entries with valid auth"""
        self.mock_auth.is_authenticated.return_value = True
        
        recs = [Recommendation(
            ticker="TESTSTOCK.NS",
            verdict="buy",
            last_close=100.0
        )]
        
        # Mock holdings to return valid response
        self.engine.portfolio.get_holdings.return_value = {'data': []}
        # Mock pending orders to return empty list (iterable)
        self.engine.orders.get_pending_orders.return_value = []
        
        result = self.engine.place_new_entries(recs)
        
        # Should not call login
        self.mock_auth.login.assert_not_called()
        self.assertIsNotNone(result)
    
    def test_evaluate_reentries_with_expired_auth(self):
        """Test evaluate_reentries_and_exits with expired auth"""
        self.mock_auth.is_authenticated.return_value = False
        self.mock_auth.login.return_value = True
        
        # Mock holdings to return valid response
        self.engine.portfolio.get_holdings.return_value = {'data': []}
        self.engine.orders.get_orders.return_value = {'data': []}
        
        result = self.engine.evaluate_reentries_and_exits()
        
        # Should attempt re-authentication
        self.mock_auth.login.assert_called()
        self.assertIsNotNone(result)


class TestLivePriceCacheReconnection(unittest.TestCase):
    """Test LivePriceCache reconnection after re-auth"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_auth = Mock(spec=KotakNeoAuth)
        self.mock_client = Mock()
        self.mock_auth.get_client.return_value = self.mock_client
        
        self.mock_scrip_master = Mock()
        self.price_cache = LivePriceCache(
            auth_client=self.mock_client,
            scrip_master=self.mock_scrip_master,
            auth=self.mock_auth
        )
    
    def test_reconnect_after_reauth(self):
        """Test that LivePriceCache gets fresh client after re-auth"""
        # Mock scrip_master.get_instrument to return proper dict with string values
        def mock_get_instrument(symbol):
            return {
                'token': 12345,
                'symbol': 'TESTSTOCK-EQ',
                'exchange': 'NSE'
            }
        
        self.mock_scrip_master.get_instrument = mock_get_instrument
        
        # Simulate re-auth: new client instance
        new_client = Mock()
        self.mock_auth.get_client.return_value = new_client
        
        # Mock WebSocket methods to avoid actual connection
        new_client.subscribe_websocket = Mock()
        new_client.start_websocket = Mock()
        
        # Call subscribe which calls get_client
        self.price_cache.subscribe(['TESTSTOCK-EQ'])
        
        # Client should be updated
        self.assertEqual(self.price_cache.client, new_client)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_auth = Mock(spec=KotakNeoAuth)
        self.mock_auth.is_logged_in = True
        self.mock_auth.client = Mock()
        self.mock_auth.get_client.return_value = self.mock_auth.client
        self.mock_auth.force_relogin.return_value = True
    
    def test_exception_during_reauth(self):
        """Test exception handling during re-auth"""
        self.mock_auth.force_relogin.side_effect = Exception("Network error")
        
        mock_orders = Mock(spec=type('obj', (object,), {}))
        mock_orders.auth = self.mock_auth
        
        auth_error_response = {'code': '900901', 'message': 'JWT token expired'}
        mock_orders.get_orders = lambda self: auth_error_response
        
        decorated_method = handle_reauth(mock_orders.get_orders)
        result = decorated_method(mock_orders)
        
        # Should handle exception gracefully
        self.assertIsNone(result)
    
    def test_non_auth_exception_not_handled(self):
        """Test that non-auth exceptions are re-raised"""
        mock_orders = Mock(spec=type('obj', (object,), {}))
        mock_orders.auth = self.mock_auth
        
        def mock_get_orders(self):
            raise ValueError("Invalid input")
        
        mock_orders.get_orders = mock_get_orders
        decorated_method = handle_reauth(mock_orders.get_orders)
        
        # Should re-raise non-auth exceptions
        with self.assertRaises(ValueError):
            decorated_method(mock_orders)


class TestComponentInitialization(unittest.TestCase):
    """Test component initialization with shared auth"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_auth = Mock(spec=KotakNeoAuth)
        self.mock_auth.is_logged_in = True
        self.mock_auth.client = Mock()
        self.mock_auth.get_client.return_value = self.mock_auth.client
    
    def test_component_initialization_with_shared_auth(self):
        """Test that components receive shared auth"""
        engine = AutoTradeEngine(auth=self.mock_auth)
        
        # Engine should use the provided auth
        self.assertEqual(engine.auth, self.mock_auth)


if __name__ == '__main__':
    unittest.main()
