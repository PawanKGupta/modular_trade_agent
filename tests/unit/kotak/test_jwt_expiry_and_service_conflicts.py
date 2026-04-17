#!/usr/bin/env python3
"""
Unit tests for REST re-authentication and service conflict handling.
"""

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth  # noqa: E402
from modules.kotak_neo_auto_trader.utils.service_conflict_detector import (  # noqa: E402
    check_old_services_running,
    check_unified_service_running,
    prevent_service_conflict,
    stop_old_services_automatically,
)


class TestRestReloginAndThreadSafety(unittest.TestCase):
    @patch("modules.kotak_neo_auto_trader.auth.load_dotenv")
    def test_force_relogin_rest_success(self, _):
        with patch.dict(
            "os.environ",
            {
                "KOTAK_CONSUMER_KEY": "test_key",
                "KOTAK_CONSUMER_SECRET": "test_ucc",
                "KOTAK_MOBILE_NUMBER": "1234567890",
                "KOTAK_TOTP_SECRET": "BASE32SECRET3232",
                "KOTAK_MPIN": "123456",
                "KOTAK_ENVIRONMENT": "prod",
            },
        ):
            auth = KotakNeoAuth(config_file="modules/kotak_neo_auto_trader/kotak_neo.env")
            auth.is_logged_in = True
            with patch.object(auth, "_perform_rest_login", return_value=True):
                self.assertTrue(auth.force_relogin())
                self.assertTrue(auth.is_logged_in)

    @patch("modules.kotak_neo_auto_trader.auth.load_dotenv")
    def test_get_client_thread_safe(self, _):
        with patch.dict(
            "os.environ",
            {
                "KOTAK_CONSUMER_KEY": "test_key",
                "KOTAK_CONSUMER_SECRET": "test_ucc",
                "KOTAK_MOBILE_NUMBER": "1234567890",
                "KOTAK_TOTP_SECRET": "BASE32SECRET3232",
                "KOTAK_MPIN": "123456",
                "KOTAK_ENVIRONMENT": "prod",
            },
        ):
            auth = KotakNeoAuth(config_file="modules/kotak_neo_auto_trader/kotak_neo.env")
            auth.is_logged_in = True
            auth.session_created_at = time.time()
            auth.base_url = "https://example.invalid"
            auth.session_token = "token"
            auth.trade_sid = "sid"
            sentinel = object()
            results: list[bool] = []
            errors: list[Exception] = []

            def worker():
                try:
                    results.append(auth.get_client() is sentinel)
                except Exception as e:  # noqa: BLE001
                    errors.append(e)

            with patch.object(auth, "get_rest_client", return_value=sentinel):
                threads = [threading.Thread(target=worker) for _ in range(10)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

            self.assertEqual(len(errors), 0)
            self.assertEqual(len(results), 10)
            self.assertTrue(all(results))


class TestServiceConflictDetection(unittest.TestCase):
    @patch("modules.kotak_neo_auto_trader.utils.service_conflict_detector.subprocess.run")
    @patch("modules.kotak_neo_auto_trader.utils.service_conflict_detector.platform.system")
    def test_check_old_services_running_windows(self, mock_platform, mock_subprocess):
        mock_platform.return_value = "Windows"

        def mock_run(cmd, **kwargs):  # noqa: ARG001
            result = unittest.mock.Mock()
            if "ModularTradeAgent_Sell" in cmd:
                result.returncode = 0
                result.stdout = "STATE: RUNNING"
            else:
                result.returncode = 1
                result.stdout = ""
            return result

        mock_subprocess.side_effect = mock_run
        running = check_old_services_running()
        self.assertIn("ModularTradeAgent_Sell", running)

    @patch("modules.kotak_neo_auto_trader.utils.service_conflict_detector.subprocess.run")
    @patch("modules.kotak_neo_auto_trader.utils.service_conflict_detector.platform.system")
    def test_check_unified_service_running_linux(self, mock_platform, mock_subprocess):
        mock_platform.return_value = "Linux"
        result = unittest.mock.Mock()
        result.returncode = 0
        result.stdout = "active"
        mock_subprocess.return_value = result
        self.assertTrue(check_unified_service_running())

    @patch(
        "modules.kotak_neo_auto_trader.utils.service_conflict_detector.check_old_services_running"
    )
    @patch(
        "modules.kotak_neo_auto_trader.utils.service_conflict_detector.stop_old_services_automatically"
    )
    def test_prevent_conflict_auto_stop(self, mock_stop, mock_check):
        mock_check.return_value = ["ModularTradeAgent_Sell"]
        mock_stop.return_value = ["ModularTradeAgent_Sell"]
        self.assertTrue(prevent_service_conflict("run_trading_service.py", is_unified=True, auto_stop=True))

    @patch("modules.kotak_neo_auto_trader.utils.service_conflict_detector.subprocess.run")
    @patch("modules.kotak_neo_auto_trader.utils.service_conflict_detector.platform.system")
    def test_stop_old_services_linux(self, mock_platform, mock_subprocess):
        mock_platform.return_value = "Linux"
        result = unittest.mock.Mock()
        result.returncode = 0
        mock_subprocess.return_value = result
        stopped = stop_old_services_automatically()
        self.assertGreaterEqual(len(stopped), 0)


if __name__ == "__main__":
    unittest.main()

