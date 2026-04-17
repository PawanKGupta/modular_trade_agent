#!/usr/bin/env python3
"""
REST login scenario tests used by developers.
"""

import sys
import tempfile
import threading
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
        "KOTAK_CONSUMER_SECRET=ucc123\n"
        "KOTAK_MOBILE_NUMBER=9999999999\n"
        "KOTAK_TOTP_SECRET=BASE32SECRET3232\n"
        "KOTAK_MPIN=123456\n"
        "KOTAK_ENVIRONMENT=sandbox\n",
        encoding="utf-8",
    )
    return env_path


def test_happy_path_login():
    env_path = _make_env()
    try:
        auth = KotakNeoAuth(config_file=str(env_path))
        with patch.object(auth, "_perform_rest_login", return_value=True):
            assert auth.login() is True
            assert auth.is_logged_in is True
    finally:
        import shutil

        shutil.rmtree(env_path.parent, ignore_errors=True)


def test_concurrent_get_client_thread_safety():
    env_path = _make_env()
    try:
        auth = KotakNeoAuth(config_file=str(env_path))
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
            threads = [threading.Thread(target=worker) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert not errors
        assert len(results) == 8
        assert all(results)
    finally:
        import shutil

        shutil.rmtree(env_path.parent, ignore_errors=True)


def test_expired_session_reauth_via_get_client():
    env_path = _make_env()
    try:
        auth = KotakNeoAuth(config_file=str(env_path))
        auth.is_logged_in = True
        auth.session_created_at = time.time() - 3600
        with (
            patch.object(auth, "_perform_rest_login", return_value=True) as mock_reauth,
            patch.object(auth, "get_rest_client", return_value=object()),
        ):
            assert auth.get_client() is not None
            assert mock_reauth.called
    finally:
        import shutil

        shutil.rmtree(env_path.parent, ignore_errors=True)

