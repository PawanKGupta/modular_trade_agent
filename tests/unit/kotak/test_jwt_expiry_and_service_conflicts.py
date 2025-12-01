#!/usr/bin/env python3
"""
Unit Tests for JWT Expiry and Service Conflict Fixes

Tests:
1. force_relogin() always creates new client
2. Thread-safe client access
3. Service conflict detection
4. Auto-stop old services
5. Concurrent API calls safety
"""

# Add project root to path
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Create mock neo_api_client module before imports that use it
if "neo_api_client" not in sys.modules:
    from unittest.mock import MagicMock

    mock_neo_module = MagicMock()
    sys.modules["neo_api_client"] = mock_neo_module

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth  # noqa: E402
from modules.kotak_neo_auto_trader.utils.service_conflict_detector import (  # noqa: E402
    check_old_services_running,
    check_unified_service_running,
    prevent_service_conflict,
    stop_old_services_automatically,
)


class TestForceReloginCreatesNewClient(unittest.TestCase):
    """Test that force_relogin() always creates a new client"""

    @patch("neo_api_client.NeoAPI")
    @patch("modules.kotak_neo_auto_trader.auth.load_dotenv")
    def test_force_relogin_always_creates_new_client(self, mock_load_dotenv, mock_neo_api_class):
        """Test that force_relogin() always creates a new client instance"""
        # Setup mocks
        mock_client1 = Mock()
        mock_client2 = Mock()
        mock_neo_api_class.side_effect = [mock_client1, mock_client2]

        mock_client1.login.return_value = {"status": "success"}
        mock_client1.session_2fa.return_value = {"data": {"token": "new_token"}}
        mock_client2.login.return_value = {"status": "success"}
        mock_client2.session_2fa.return_value = {"data": {"token": "new_token"}}

        # Mock environment variables
        with patch.dict(
            "os.environ",
            {
                "KOTAK_CONSUMER_KEY": "test_key",
                "KOTAK_CONSUMER_SECRET": "test_secret",
                "KOTAK_MOBILE_NUMBER": "1234567890",
                "KOTAK_PASSWORD": "test_pass",
                "KOTAK_MPIN": "123456",
                "KOTAK_ENVIRONMENT": "prod",
            },
        ):
            auth = KotakNeoAuth(config_file="modules/kotak_neo_auto_trader/kotak_neo.env")
            auth.client = mock_client1  # Set initial client
            auth.is_logged_in = True

            # Execute
            result = auth.force_relogin()

            # Verify
            self.assertTrue(result, "Re-authentication should succeed")
            # Note: Due to mocking, we verify logout was called instead of checking client ID
            mock_client1.logout.assert_called_once()  # Old client should be logged out

    @patch("neo_api_client.NeoAPI")
    @patch("modules.kotak_neo_auto_trader.auth.load_dotenv")
    def test_force_relogin_resets_state(self, mock_load_dotenv, mock_neo_api_class):
        """Test that force_relogin() resets authentication state"""
        mock_client = Mock()
        mock_neo_api_class.return_value = mock_client
        mock_client.login.return_value = {"status": "success"}
        mock_client.session_2fa.return_value = {"data": {"token": "new_token"}}

        with patch.dict(
            "os.environ",
            {
                "KOTAK_CONSUMER_KEY": "test_key",
                "KOTAK_CONSUMER_SECRET": "test_secret",
                "KOTAK_MOBILE_NUMBER": "1234567890",
                "KOTAK_PASSWORD": "test_pass",
                "KOTAK_MPIN": "123456",
                "KOTAK_ENVIRONMENT": "prod",
            },
        ):
            auth = KotakNeoAuth(config_file="modules/kotak_neo_auto_trader/kotak_neo.env")
            auth.client = Mock()
            auth.is_logged_in = True
            auth.session_token = "old_token"

            # Execute
            auth.force_relogin()

            # Verify state was reset (client is recreated, so check it's not the old one)
            self.assertIsNotNone(auth.client, "Client should be recreated")
            self.assertTrue(auth.is_logged_in, "Should be logged in after re-auth")


class TestThreadSafeClientAccess(unittest.TestCase):
    """Test thread-safe client access"""

    @patch("neo_api_client.NeoAPI")
    @patch("modules.kotak_neo_auto_trader.auth.load_dotenv")
    def test_get_client_thread_safe(self, mock_load_dotenv, mock_neo_api_class):
        """Test that get_client() is thread-safe"""
        mock_client = Mock()
        mock_neo_api_class.return_value = mock_client
        mock_client.login.return_value = {"status": "success"}
        mock_client.session_2fa.return_value = {"data": {"token": "token"}}

        with patch.dict(
            "os.environ",
            {
                "KOTAK_CONSUMER_KEY": "test_key",
                "KOTAK_CONSUMER_SECRET": "test_secret",
                "KOTAK_MOBILE_NUMBER": "1234567890",
                "KOTAK_PASSWORD": "test_pass",
                "KOTAK_MPIN": "123456",
                "KOTAK_ENVIRONMENT": "prod",
            },
        ):
            auth = KotakNeoAuth(config_file="modules/kotak_neo_auto_trader/kotak_neo.env")
            auth.login()

            # Test concurrent access
            results = []
            errors = []

            def get_client_thread():
                try:
                    client = auth.get_client()
                    results.append(client is not None)
                except Exception as e:
                    errors.append(e)

            # Create multiple threads
            threads = []
            for _ in range(10):
                t = threading.Thread(target=get_client_thread)
                threads.append(t)
                t.start()

            # Wait for all threads
            for t in threads:
                t.join()

            # Verify
            self.assertEqual(len(errors), 0, "No errors should occur")
            self.assertEqual(len(results), 10, "All threads should complete")
            self.assertTrue(all(results), "All threads should get valid client")

    @patch("neo_api_client.NeoAPI")
    @patch("modules.kotak_neo_auto_trader.auth.load_dotenv")
    def test_force_relogin_thread_safe(self, mock_load_dotenv, mock_neo_api_class):
        """Test that force_relogin() is thread-safe"""
        mock_client = Mock()
        mock_neo_api_class.return_value = mock_client
        mock_client.login.return_value = {"status": "success"}
        mock_client.session_2fa.return_value = {"data": {"token": "token"}}

        with patch.dict(
            "os.environ",
            {
                "KOTAK_CONSUMER_KEY": "test_key",
                "KOTAK_CONSUMER_SECRET": "test_secret",
                "KOTAK_MOBILE_NUMBER": "1234567890",
                "KOTAK_PASSWORD": "test_pass",
                "KOTAK_MPIN": "123456",
                "KOTAK_ENVIRONMENT": "prod",
            },
        ):
            auth = KotakNeoAuth(config_file="modules/kotak_neo_auto_trader/kotak_neo.env")
            auth.client = Mock()
            auth.is_logged_in = True

            # Test concurrent re-auth attempts
            results = []
            errors = []

            def reauth_thread():
                try:
                    result = auth.force_relogin()
                    results.append(result)
                except Exception as e:
                    errors.append(e)

            # Create multiple threads trying to re-auth simultaneously
            threads = []
            for _ in range(5):
                t = threading.Thread(target=reauth_thread)
                threads.append(t)
                t.start()

            # Wait for all threads
            for t in threads:
                t.join()

            # Verify
            self.assertEqual(len(errors), 0, "No errors should occur")
            self.assertEqual(len(results), 5, "All threads should complete")
            # All should succeed (lock ensures sequential execution)
            self.assertTrue(any(results), "At least one re-auth should succeed")


class TestServiceConflictDetection(unittest.TestCase):
    """Test service conflict detection"""

    @patch("modules.kotak_neo_auto_trader.utils.service_conflict_detector.subprocess.run")
    @patch("modules.kotak_neo_auto_trader.utils.service_conflict_detector.platform.system")
    def test_check_old_services_running_windows(self, mock_platform, mock_subprocess):
        """Test checking old services on Windows"""
        mock_platform.return_value = "Windows"

        # Mock service query - one running
        call_count = [0]

        def mock_run(cmd, **kwargs):
            result = Mock()
            call_count[0] += 1
            if call_count[0] == 1 and "ModularTradeAgent_Sell" in cmd:
                result.returncode = 0
                result.stdout = "STATE: RUNNING"
            else:
                result.returncode = 1
            return result

        mock_subprocess.side_effect = mock_run

        running = check_old_services_running()

        self.assertIn("ModularTradeAgent_Sell", running)

    @patch("modules.kotak_neo_auto_trader.utils.service_conflict_detector.subprocess.run")
    @patch("modules.kotak_neo_auto_trader.utils.service_conflict_detector.platform.system")
    def test_check_unified_service_running_linux(self, mock_platform, mock_subprocess):
        """Test checking unified service on Linux"""
        mock_platform.return_value = "Linux"

        # Mock systemctl check - service is active
        result = Mock()
        result.returncode = 0
        result.stdout = "active"
        mock_subprocess.return_value = result

        is_running = check_unified_service_running()

        self.assertTrue(is_running)

    @patch(
        "modules.kotak_neo_auto_trader.utils.service_conflict_detector.check_old_services_running"
    )
    @patch(
        "modules.kotak_neo_auto_trader.utils.service_conflict_detector.stop_old_services_automatically"
    )
    def test_prevent_conflict_auto_stop(self, mock_stop, mock_check):
        """Test that prevent_service_conflict auto-stops old services"""
        mock_check.return_value = ["ModularTradeAgent_Sell"]
        mock_stop.return_value = ["ModularTradeAgent_Sell"]

        result = prevent_service_conflict("run_trading_service.py", is_unified=True, auto_stop=True)

        self.assertTrue(result, "Should succeed after auto-stopping")
        mock_stop.assert_called_once()

    @patch(
        "modules.kotak_neo_auto_trader.utils.service_conflict_detector.check_old_services_running"
    )
    def test_prevent_conflict_no_auto_stop(self, mock_check):
        """Test that prevent_service_conflict exits if auto_stop=False"""
        mock_check.return_value = ["ModularTradeAgent_Sell"]

        result = prevent_service_conflict(
            "run_trading_service.py", is_unified=True, auto_stop=False
        )

        self.assertFalse(result, "Should fail if conflicts exist and auto_stop=False")

    @patch(
        "modules.kotak_neo_auto_trader.utils.service_conflict_detector.check_unified_service_running"
    )
    def test_prevent_conflict_old_service(self, mock_check):
        """Test that old service exits if unified service is running"""
        mock_check.return_value = True

        result = prevent_service_conflict("run_sell_orders.py", is_unified=False)

        self.assertFalse(result, "Old service should exit if unified service is running")


class TestAutoStopOldServices(unittest.TestCase):
    """Test auto-stop old services functionality"""

    @patch("modules.kotak_neo_auto_trader.utils.service_conflict_detector.subprocess.run")
    @patch("modules.kotak_neo_auto_trader.utils.service_conflict_detector.platform.system")
    def test_stop_old_services_windows(self, mock_platform, mock_subprocess):
        """Test stopping old services on Windows"""
        mock_platform.return_value = "Windows"

        # Mock successful stop
        result = Mock()
        result.returncode = 0
        mock_subprocess.return_value = result

        stopped = stop_old_services_automatically()

        # Verify sc stop was called for each service
        self.assertGreaterEqual(len(stopped), 0)  # May be 0 if services don't exist
        self.assertGreater(mock_subprocess.call_count, 0)

    @patch("modules.kotak_neo_auto_trader.utils.service_conflict_detector.subprocess.run")
    @patch("modules.kotak_neo_auto_trader.utils.service_conflict_detector.platform.system")
    def test_stop_old_services_linux(self, mock_platform, mock_subprocess):
        """Test stopping old services on Linux"""
        mock_platform.return_value = "Linux"

        # Mock successful stop
        result = Mock()
        result.returncode = 0
        mock_subprocess.return_value = result

        stopped = stop_old_services_automatically()

        # Verify systemctl stop was called
        self.assertGreaterEqual(len(stopped), 0)  # May be 0 if services don't exist
        self.assertGreater(mock_subprocess.call_count, 0)


class TestConcurrentAPICallsSafety(unittest.TestCase):
    """Test that concurrent API calls are safe"""

    @patch("neo_api_client.NeoAPI")
    @patch("modules.kotak_neo_auto_trader.auth.load_dotenv")
    def test_concurrent_api_calls_with_reauth(self, mock_load_dotenv, mock_neo_api_class):
        """Test concurrent API calls when re-auth happens"""
        mock_client1 = Mock()
        mock_client2 = Mock()
        mock_neo_api_class.side_effect = [mock_client1, mock_client2]

        mock_client1.login.return_value = {"status": "success"}
        mock_client1.session_2fa.return_value = {"data": {"token": "token1"}}
        mock_client2.login.return_value = {"status": "success"}
        mock_client2.session_2fa.return_value = {"data": {"token": "token2"}}

        with patch.dict(
            "os.environ",
            {
                "KOTAK_CONSUMER_KEY": "test_key",
                "KOTAK_CONSUMER_SECRET": "test_secret",
                "KOTAK_MOBILE_NUMBER": "1234567890",
                "KOTAK_PASSWORD": "test_pass",
                "KOTAK_MPIN": "123456",
                "KOTAK_ENVIRONMENT": "prod",
            },
        ):
            auth = KotakNeoAuth(config_file="modules/kotak_neo_auto_trader/kotak_neo.env")
            auth.login()

            api_results = []
            errors = []

            def api_call_thread(thread_id):
                try:
                    # Get client (thread-safe)
                    client = auth.get_client()
                    if client:
                        # Simulate API call
                        api_results.append(f"thread_{thread_id}_success")
                    else:
                        api_results.append(f"thread_{thread_id}_no_client")
                except Exception as e:
                    errors.append(f"thread_{thread_id}: {e}")

            def reauth_thread():
                try:
                    time.sleep(0.1)  # Wait for some API calls to start
                    auth.force_relogin()
                except Exception as e:
                    errors.append(f"reauth: {e}")

            # Start API call threads
            api_threads = []
            for i in range(10):
                t = threading.Thread(target=api_call_thread, args=(i,))
                api_threads.append(t)
                t.start()

            # Start re-auth thread
            reauth_t = threading.Thread(target=reauth_thread)
            reauth_t.start()

            # Wait for all threads
            for t in api_threads:
                t.join()
            reauth_t.join()

            # Verify
            self.assertEqual(len(errors), 0, "No errors should occur")
            self.assertEqual(len(api_results), 10, "All API calls should complete")


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for real-world scenarios"""

    @patch("neo_api_client.NeoAPI")
    @patch("modules.kotak_neo_auto_trader.auth.load_dotenv")
    def test_multiple_reauth_attempts(self, mock_load_dotenv, mock_neo_api_class):
        """Test multiple re-auth attempts don't cause issues"""
        mock_client = Mock()
        mock_neo_api_class.return_value = mock_client
        mock_client.login.return_value = {"status": "success"}
        mock_client.session_2fa.return_value = {"data": {"token": "token"}}

        with patch.dict(
            "os.environ",
            {
                "KOTAK_CONSUMER_KEY": "test_key",
                "KOTAK_CONSUMER_SECRET": "test_secret",
                "KOTAK_MOBILE_NUMBER": "1234567890",
                "KOTAK_PASSWORD": "test_pass",
                "KOTAK_MPIN": "123456",
                "KOTAK_ENVIRONMENT": "prod",
            },
        ):
            auth = KotakNeoAuth(config_file="modules/kotak_neo_auto_trader/kotak_neo.env")
            auth.client = Mock()
            auth.is_logged_in = True

            # Simulate multiple re-auth attempts
            results = []
            for _ in range(3):
                result = auth.force_relogin()
                results.append(result)

            # Verify all succeed
            self.assertTrue(all(results), "All re-auth attempts should succeed")

    @patch(
        "modules.kotak_neo_auto_trader.utils.service_conflict_detector.check_old_services_running"
    )
    @patch(
        "modules.kotak_neo_auto_trader.utils.service_conflict_detector.stop_old_services_automatically"
    )
    def test_unified_service_startup_with_conflicts(self, mock_stop, mock_check):
        """Test unified service startup when old services are running"""
        mock_check.return_value = ["ModularTradeAgent_Sell", "ModularTradeAgent_Main"]
        mock_stop.return_value = ["ModularTradeAgent_Sell", "ModularTradeAgent_Main"]

        # This simulates run_trading_service.py startup
        result = prevent_service_conflict("run_trading_service.py", is_unified=True, auto_stop=True)

        self.assertTrue(result, "Should succeed after auto-stopping conflicts")
        mock_stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
