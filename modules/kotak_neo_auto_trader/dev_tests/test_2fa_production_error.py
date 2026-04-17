#!/usr/bin/env python3
"""
REST-auth smoke tests for KotakNeoAuth.

These dev tests intentionally avoid deprecated private SDK-era methods.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

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


def test_login_uses_rest_flow_only():
    env_path = _make_env()
    try:
        auth = KotakNeoAuth(config_file=str(env_path))
        with patch.object(auth, "_perform_rest_login", return_value=True) as mock_rest:
            assert auth.login() is True
            mock_rest.assert_called_once()
    finally:
        import shutil

        shutil.rmtree(env_path.parent, ignore_errors=True)


def test_force_relogin_uses_rest_flow_only():
    env_path = _make_env()
    try:
        auth = KotakNeoAuth(config_file=str(env_path))
        auth.is_logged_in = True
        auth.session_created_at = 0.0
        with patch.object(auth, "_perform_rest_login", return_value=True) as mock_rest:
            assert auth.force_relogin() is True
            mock_rest.assert_called_once()
    finally:
        import shutil

        shutil.rmtree(env_path.parent, ignore_errors=True)


def test_get_client_returns_rest_client_instance():
    env_path = _make_env()
    try:
        auth = KotakNeoAuth(config_file=str(env_path))
        auth.is_logged_in = True
        auth.base_url = "https://example.invalid"
        auth.session_token = "trade_token"
        auth.trade_sid = "trade_sid"
        dummy = Mock()
        with patch.object(auth, "get_rest_client", return_value=dummy) as mock_get_rest:
            assert auth.get_client() is dummy
            mock_get_rest.assert_called_once()
    finally:
        import shutil

        shutil.rmtree(env_path.parent, ignore_errors=True)

