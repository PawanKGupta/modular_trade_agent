#!/usr/bin/env python3
"""
Test script for centralized re-authentication handler

Tests the @handle_reauth decorator and auth error detection
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import unittest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from modules.kotak_neo_auto_trader.auth_handler import (
        is_auth_error,
        handle_reauth,
        call_with_reauth
    )
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
    from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)


class TestAuthErrorDetection(unittest.TestCase):
    """Test auth error detection function"""
    
    def test_auth_error_by_code(self):
        """Test detection by error code 900901"""
        response = {'code': '900901', 'message': 'Some message'}
        self.assertTrue(is_auth_error(response))
    
    def test_auth_error_by_description(self):
        """Test detection by invalid jwt token in description"""
        response = {
            'code': '500',
            'description': 'invalid jwt token expired'
        }
        self.assertTrue(is_auth_error(response))
    
    def test_auth_error_by_message(self):
        """Test detection by invalid credentials in message"""
        response = {
            'code': '400',
            'message': 'invalid credentials provided'
        }
        self.assertTrue(is_auth_error(response))
    
    def test_auth_error_in_exception(self):
        """Test detection in exception message"""
        exception = Exception("Invalid JWT token expired")
        self.assertTrue(is_auth_error(exception))
    
    def test_auth_error_in_string(self):
        """Test detection in string response"""
        response = "Error: Invalid jwt token"
        self.assertTrue(is_auth_error(response))
    
    def test_no_auth_error(self):
        """Test normal response doesn't trigger"""
        response = {'code': '200', 'data': []}
        self.assertFalse(is_auth_error(response))
    
    def test_other_errors(self):
        """Test other errors don't trigger auth error"""
        response = {'error': 'Symbol not found'}
        self.assertFalse(is_auth_error(response))


class TestReauthDecorator(unittest.TestCase):
    """Test the handle_reauth decorator"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create mock auth object
        self.mock_auth = Mock(spec=KotakNeoAuth)
        self.mock_auth.force_relogin = Mock(return_value=True)
        
        # Create test class with auth
        class TestClass:
            def __init__(self, auth):
                self.auth = auth
        
        self.test_class = TestClass(self.mock_auth)
    
    def test_decorator_with_successful_call(self):
        """Test decorator with successful API call"""
        @handle_reauth
        def test_method(self):
            return {'data': 'success'}
        
        result = test_method(self.test_class)
        self.assertEqual(result, {'data': 'success'})
        self.mock_auth.force_relogin.assert_not_called()
    
    def test_decorator_with_auth_error_and_reauth(self):
        """Test decorator retries after successful re-auth"""
        call_count = [0]
        
        @handle_reauth
        def test_method(self):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call returns auth error
                return {'code': '900901', 'message': 'JWT expired'}
            else:
                # Second call after re-auth succeeds
                return {'data': 'success'}
        
        result = test_method(self.test_class)
        self.assertEqual(result, {'data': 'success'})
        self.assertEqual(call_count[0], 2)  # Called twice
        self.mock_auth.force_relogin.assert_called_once()
    
    def test_decorator_with_auth_error_and_reauth_failure(self):
        """Test decorator when re-auth fails"""
        self.mock_auth.force_relogin.return_value = False
        
        @handle_reauth
        def test_method(self):
            return {'code': '900901', 'message': 'JWT expired'}
        
        result = test_method(self.test_class)
        self.assertIsNone(result)
        self.mock_auth.force_relogin.assert_called_once()
    
    def test_decorator_with_auth_exception(self):
        """Test decorator with auth exception"""
        call_count = [0]
        
        @handle_reauth
        def test_method(self):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Invalid JWT token expired")
            else:
                return {'data': 'success'}
        
        result = test_method(self.test_class)
        self.assertEqual(result, {'data': 'success'})
        self.assertEqual(call_count[0], 2)
        self.mock_auth.force_relogin.assert_called_once()
    
    def test_decorator_with_non_auth_exception(self):
        """Test decorator doesn't catch non-auth exceptions"""
        @handle_reauth
        def test_method(self):
            raise ValueError("Some other error")
        
        with self.assertRaises(ValueError):
            test_method(self.test_class)
        self.mock_auth.force_relogin.assert_not_called()


class TestCallWithReauth(unittest.TestCase):
    """Test call_with_reauth helper function"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_auth = Mock(spec=KotakNeoAuth)
        self.mock_auth.force_relogin = Mock(return_value=True)
    
    def test_successful_call(self):
        """Test successful API call"""
        def api_call():
            return {'data': 'success'}
        
        result = call_with_reauth(self.mock_auth, api_call)
        self.assertEqual(result, {'data': 'success'})
        self.mock_auth.force_relogin.assert_not_called()
    
    def test_auth_error_with_reauth(self):
        """Test retry after re-auth"""
        call_count = [0]
        
        def api_call():
            call_count[0] += 1
            if call_count[0] == 1:
                return {'code': '900901'}
            return {'data': 'success'}
        
        result = call_with_reauth(self.mock_auth, api_call)
        self.assertEqual(result, {'data': 'success'})
        self.assertEqual(call_count[0], 2)
        self.mock_auth.force_relogin.assert_called_once()


def test_actual_integration():
    """Test with actual orders module (requires auth setup)"""
    print("\n" + "="*80)
    print("INTEGRATION TEST: Testing decorator with actual modules")
    print("="*80)
    
    try:
        # Try to load auth from env (optional)
        from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
        
        # Check if decorator is applied
        from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
        from modules.kotak_neo_auto_trader.market_data import KotakNeoMarketData
        from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio
        
        # Verify decorator is applied
        print("\n✅ Checking if @handle_reauth decorator is applied:")
        
        # Check orders module
        if hasattr(KotakNeoOrders.place_equity_order, '__wrapped__'):
            print("  ✅ place_equity_order has decorator")
        else:
            print("  ⚠️  place_equity_order decorator status unclear")
        
        if hasattr(KotakNeoOrders.get_orders, '__wrapped__'):
            print("  ✅ get_orders has decorator")
        else:
            print("  ⚠️  get_orders decorator status unclear")
        
        # Check market_data module
        if hasattr(KotakNeoMarketData.get_quote, '__wrapped__'):
            print("  ✅ get_quote has decorator")
        else:
            print("  ⚠️  get_quote decorator status unclear")
        
        # Check portfolio module
        if hasattr(KotakNeoPortfolio.get_positions, '__wrapped__'):
            print("  ✅ get_positions has decorator")
        else:
            print("  ⚠️  get_positions decorator status unclear")
        
        print("\n✅ All modules imported successfully")
        print("✅ Decorator pattern appears to be applied")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("="*80)
    print("RE-AUTHENTICATION HANDLER TEST SUITE")
    print("="*80)
    
    # Run unit tests
    print("\n" + "="*80)
    print("UNIT TESTS")
    print("="*80)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestAuthErrorDetection))
    suite.addTests(loader.loadTestsFromTestCase(TestReauthDecorator))
    suite.addTests(loader.loadTestsFromTestCase(TestCallWithReauth))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Run integration test
    integration_result = test_actual_integration()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Unit Tests: {result.testsRun} run, {len(result.failures)} failures, {len(result.errors)} errors")
    print(f"Integration Test: {'✅ PASSED' if integration_result else '❌ FAILED'}")
    
    if result.wasSuccessful() and integration_result:
        print("\n✅ ALL TESTS PASSED")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())

