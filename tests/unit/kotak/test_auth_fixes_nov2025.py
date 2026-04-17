#!/usr/bin/env python3
"""
Unit tests for REST auth fixes (Nov 2025+).
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.auth_handler import (
    _check_reauth_failure_rate,
    _clear_reauth_failures,
    _record_reauth_failure,
)
from modules.kotak_neo_auto_trader.eod_cleanup import EODCleanup


class TestRestAuthFlow(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.env_path = self.tmp_dir / "kotak_neo.env"
        self.env_path.write_text(
            "KOTAK_CONSUMER_KEY=test_key\n"
            "KOTAK_CONSUMER_SECRET=ucc123\n"
            "KOTAK_MOBILE_NUMBER=9999999999\n"
            "KOTAK_TOTP_SECRET=BASE32SECRET3232\n"
            "KOTAK_MPIN=123456\n"
            "KOTAK_ENVIRONMENT=sandbox\n",
            encoding="utf-8",
        )
        self.auth = KotakNeoAuth(config_file=str(self.env_path))

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_login_uses_rest(self):
        with patch.object(self.auth, "_perform_rest_login", return_value=True) as mock_rest:
            self.assertTrue(self.auth.login())
            mock_rest.assert_called_once()

    def test_force_relogin_uses_rest(self):
        self.auth.is_logged_in = True
        with patch.object(self.auth, "_perform_rest_login", return_value=True) as mock_rest:
            self.assertTrue(self.auth.force_relogin())
            mock_rest.assert_called_once()


class TestReauthLoopPrevention(unittest.TestCase):
    def setUp(self):
        self.auth = Mock(spec=KotakNeoAuth)
        _clear_reauth_failures(self.auth)

    def tearDown(self):
        _clear_reauth_failures(self.auth)

    def test_rate_limiting_after_three_failures(self):
        self.assertFalse(_check_reauth_failure_rate(self.auth))
        _record_reauth_failure(self.auth)
        _record_reauth_failure(self.auth)
        _record_reauth_failure(self.auth)
        self.assertTrue(_check_reauth_failure_rate(self.auth))


class TestEODCleanupFix(unittest.TestCase):
    def test_eod_cleanup_method_name(self):
        cleanup = EODCleanup(broker_client=Mock())
        self.assertTrue(hasattr(cleanup, "run_eod_cleanup"))
        self.assertFalse(hasattr(cleanup, "run"))


if __name__ == "__main__":
    unittest.main()

