#!/usr/bin/env python3
"""
REST session-expiry behavior tests for KotakNeoAuth.

These tests validate TTL-triggered re-login without any SDK-era methods.
"""

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth


def _make_env() -> Path:
    tmp_dir = Path(tempfile.mkdtemp())
    env_path = tmp_dir / "kotak_neo.env"
    env_path.write_text(
        "KOTAK_CONSUMER_KEY=test_key\n"
        "KOTAK_CONSUMER_SECRET=secret\n"
        "KOTAK_MOBILE_NUMBER=9999999999\n"
        "KOTAK_TOTP_SECRET=BASE32SECRET3232\n"
        "KOTAK_MPIN=123456\n"
        "KOTAK_ENVIRONMENT=sandbox\n",
        encoding="utf-8",
    )
    return env_path


def test_expired_session_triggers_force_relogin_from_get_client():
    env_path = _make_env()
    try:
        auth = KotakNeoAuth(config_file=str(env_path))
        auth.is_logged_in = True
        auth.session_created_at = time.time() - 3600
        with (
            patch.object(auth, "_perform_rest_login", return_value=True) as mock_rest,
            patch.object(auth, "get_rest_client", return_value=object()),
        ):
            result = auth.get_client()
            assert result is not None
            assert mock_rest.called
    finally:
        import shutil

        shutil.rmtree(env_path.parent, ignore_errors=True)


def test_relogin_failure_returns_none_client():
    env_path = _make_env()
    try:
        auth = KotakNeoAuth(config_file=str(env_path))
        auth.is_logged_in = True
        auth.session_created_at = time.time() - 3600
        with patch.object(auth, "_perform_rest_login", return_value=False):
            assert auth.get_client() is None
    finally:
        import shutil

        shutil.rmtree(env_path.parent, ignore_errors=True)

