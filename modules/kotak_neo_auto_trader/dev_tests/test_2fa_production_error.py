#!/usr/bin/env python3
"""
Test that simulates production 2FA error scenario
Tests the exact error: 'NoneType' object has no attribute 'get'
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
import tempfile

def test_2fa_with_none_response():
    """Test 2FA when session_2fa returns None"""
    print("Test 1: session_2fa returns None")
    print("-" * 80)
    
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
            encoding="utf-8"
        )
        
        auth = KotakNeoAuth(config_file=str(env_path))
        
        # Mock client to return None from session_2fa
        mock_client = Mock()
        mock_client.session_2fa.return_value = None
        mock_client.login.return_value = {"status": "success"}
        
        auth.client = mock_client
        
        # This should not raise AttributeError
        result = auth._complete_2fa()
        print(f"Result: {result}")
        print(f"Expected: True (None response means session already active)")
        assert result == True, "Should return True when session_2fa returns None"
        print("✅ PASSED\n")
        
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_2fa_with_object_without_get():
    """Test 2FA when session_2fa returns object without .get() method"""
    print("Test 2: session_2fa returns object without .get()")
    print("-" * 80)
    
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
            encoding="utf-8"
        )
        
        auth = KotakNeoAuth(config_file=str(env_path))
        
        # Mock client to return object without .get() method
        class CustomObject:
            def __init__(self):
                self.data = Mock()
                self.data.token = "test_token"
        
        mock_client = Mock()
        mock_client.session_2fa.return_value = CustomObject()
        mock_client.login.return_value = {"status": "success"}
        
        auth.client = mock_client
        
        # This should not raise AttributeError
        result = auth._complete_2fa()
        print(f"Result: {result}")
        print("✅ PASSED\n")
        
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_2fa_with_get_that_returns_none():
    """Test 2FA when session_2fa returns object where .get() returns None"""
    print("Test 3: session_2fa returns object where .get() returns None")
    print("-" * 80)
    
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
            encoding="utf-8"
        )
        
        auth = KotakNeoAuth(config_file=str(env_path))
        
        # Mock client to return object where .get('data') returns None
        class MockResponse:
            def get(self, key):
                if key == 'error':
                    return None
                if key == 'data':
                    return None  # This returns None!
                return None
        
        mock_client = Mock()
        mock_client.session_2fa.return_value = MockResponse()
        mock_client.login.return_value = {"status": "success"}
        
        auth.client = mock_client
        
        # This should not raise AttributeError
        result = auth._complete_2fa()
        print(f"Result: {result}")
        print("✅ PASSED\n")
        
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_2fa_with_get_on_none():
    """Test 2FA when session_2fa.get() itself is called on None"""
    print("Test 4: session_2fa returns None but we try to call .get()")
    print("-" * 80)
    
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
            encoding="utf-8"
        )
        
        auth = KotakNeoAuth(config_file=str(env_path))
        
        # Create a mock that has .get() but returns None
        # Then when we call .get('data'), it returns None
        # And then we try to call .get() on that None
        class MockResponseWithGet:
            def get(self, key):
                if key == 'error':
                    return None
                if key == 'data':
                    return None  # Returns None
                return None
        
        mock_client = Mock()
        mock_client.session_2fa.return_value = MockResponseWithGet()
        mock_client.login.return_value = {"status": "success"}
        
        auth.client = mock_client
        
        # This should not raise AttributeError
        result = auth._complete_2fa()
        print(f"Result: {result}")
        print("✅ PASSED\n")
        
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_2fa_production_scenario():
    """Test the exact production scenario from logs"""
    print("Test 5: Production scenario - force_relogin during JWT expiry")
    print("-" * 80)
    
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
            encoding="utf-8"
        )
        
        auth = KotakNeoAuth(config_file=str(env_path))
        
        # Simulate production: client exists, login succeeds, but session_2fa returns problematic response
        mock_client = Mock()
        
        # Login succeeds
        mock_client.login.return_value = {"status": "success"}
        
        # session_2fa returns something that causes the error
        # The error says "'NoneType' object has no attribute 'get'"
        # This suggests we're calling .get() on None somewhere
        
        # Scenario: session_2fa returns an object that has .get() method
        # but when we call .get('data'), it returns None
        # and then we try to call .get() on that None
        class ProblematicResponse:
            def get(self, key):
                if key == 'error':
                    return None
                if key == 'data':
                    # Return None - this causes the issue
                    return None
                return None
        
        mock_client.session_2fa.return_value = ProblematicResponse()
        auth.client = mock_client
        
        # Simulate _perform_login success
        auth._perform_login = Mock(return_value=True)
        
        # Now test _complete_2fa - this should not raise AttributeError
        try:
            result = auth._complete_2fa()
            print(f"Result: {result}")
            print("✅ No AttributeError raised")
        except AttributeError as e:
            if "'NoneType' object has no attribute 'get'" in str(e):
                print(f"❌ FAILED: Caught the exact production error: {e}")
                raise
            else:
                print(f"Different AttributeError: {e}")
                raise
        
        print("✅ PASSED\n")
        
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 80)
    print("Testing 2FA Error Scenarios")
    print("=" * 80)
    print()
    
    try:
        test_2fa_with_none_response()
        test_2fa_with_object_without_get()
        test_2fa_with_get_that_returns_none()
        test_2fa_with_get_on_none()
        test_2fa_production_scenario()
        
        print("=" * 80)
        print("✅ All tests passed!")
        print("=" * 80)
        
    except Exception as e:
        print("=" * 80)
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        sys.exit(1)





