#!/usr/bin/env python3
"""
Test for inactivity-based session expiry scenario
When session expires due to inactivity, session_2fa might return problematic responses
"""

import sys
from pathlib import Path
from unittest.mock import Mock

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import tempfile

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth


def test_inactivity_expiry_with_none_data():
    """Test 2FA when session expires due to inactivity and returns dict with data=None"""
    print("Test 1: Inactivity expiry - dict with data=None")
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
            encoding="utf-8",
        )

        auth = KotakNeoAuth(config_file=str(env_path))

        # Simulate inactivity expiry: session_2fa returns dict with data=None
        mock_client = Mock()
        mock_client.session_2fa.return_value = {"data": None, "status": "unknown"}
        mock_client.login.return_value = {"status": "success"}

        auth.client = mock_client

        # This should not raise AttributeError and should handle gracefully
        result = auth._complete_2fa()
        print(f"Result: {result}")
        assert result == True, "Should return True when data=None (session may be active)"
        print("✅ PASSED\n")

    finally:
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_inactivity_expiry_with_dict_like_object():
    """Test 2FA when session expires and returns dict-like object with None data"""
    print("Test 2: Inactivity expiry - dict-like object with data=None")
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
            encoding="utf-8",
        )

        auth = KotakNeoAuth(config_file=str(env_path))

        # Simulate dict-like object (not actual dict) with get() that returns None
        class DictLikeResponse:
            def get(self, key):
                if key == "error":
                    return None
                if key == "data":
                    return None  # Returns None - this was causing the issue
                return None

        mock_client = Mock()
        mock_client.session_2fa.return_value = DictLikeResponse()
        mock_client.login.return_value = {"status": "success"}

        auth.client = mock_client

        # This should not raise AttributeError
        result = auth._complete_2fa()
        print(f"Result: {result}")
        assert result == True, "Should handle dict-like object with None data"
        print("✅ PASSED\n")

    finally:
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_inactivity_expiry_force_relogin_full_flow():
    """Test full force_relogin flow when session expires due to inactivity"""
    print("Test 3: Full force_relogin flow after inactivity expiry")
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
            encoding="utf-8",
        )

        auth = KotakNeoAuth(config_file=str(env_path))

        # Simulate full re-authentication flow after inactivity expiry
        mock_client = Mock()

        # Login succeeds (first step of re-auth)
        mock_client.login.return_value = {"status": "success"}

        # session_2fa returns problematic response (dict-like with None data)
        class ExpiredSessionResponse:
            def get(self, key):
                if key == "error":
                    return None
                if key == "data":
                    return None  # Session expired, data is None
                return None

        mock_client.session_2fa.return_value = ExpiredSessionResponse()
        auth.client = mock_client

        # Mock _perform_login to succeed
        auth._perform_login = Mock(return_value=True)

        # Test full force_relogin flow
        result = auth.force_relogin()
        print(f"Result: {result}")
        assert result == True, "Should complete re-authentication even with None data"
        print("✅ PASSED\n")

    finally:
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_inactivity_expiry_with_error_response():
    """Test 2FA when session expires and returns error response"""
    print("Test 4: Inactivity expiry - error response")
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
            encoding="utf-8",
        )

        auth = KotakNeoAuth(config_file=str(env_path))

        # Simulate error response when session expired
        mock_client = Mock()
        mock_client.session_2fa.return_value = {
            "error": [{"message": "Session expired"}],
            "data": None,
        }
        mock_client.login.return_value = {"status": "success"}

        auth.client = mock_client

        # Should detect error and return False
        result = auth._complete_2fa()
        print(f"Result: {result}")
        assert result == False, "Should return False when error is present"
        print("✅ PASSED\n")

    finally:
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 80)
    print("Testing 2FA Inactivity Expiry Scenarios")
    print("=" * 80)
    print()

    try:
        test_inactivity_expiry_with_none_data()
        test_inactivity_expiry_with_dict_like_object()
        test_inactivity_expiry_force_relogin_full_flow()
        test_inactivity_expiry_with_error_response()

        print("=" * 80)
        print("✅ All inactivity expiry tests passed!")
        print("=" * 80)

    except Exception as e:
        print("=" * 80)
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        print("=" * 80)
        sys.exit(1)
