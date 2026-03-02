#!/usr/bin/env python3
"""
REST re-auth loop-prevention smoke tests.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.auth_handler import (
    _check_reauth_failure_rate,
    _clear_reauth_failures,
    _record_reauth_failure,
)


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


def test_reauth_failure_rate_blocks_after_three_failures():
    env_path = _make_env()
    try:
        auth = KotakNeoAuth(config_file=str(env_path))
        _clear_reauth_failures(auth)
        assert not _check_reauth_failure_rate(auth)
        _record_reauth_failure(auth)
        _record_reauth_failure(auth)
        _record_reauth_failure(auth)
        assert _check_reauth_failure_rate(auth)
    finally:
        import shutil

        shutil.rmtree(env_path.parent, ignore_errors=True)


def test_force_relogin_rest_smoke():
    env_path = _make_env()
    try:
        auth = KotakNeoAuth(config_file=str(env_path))
        auth.is_logged_in = True
        with patch.object(auth, "_perform_rest_login", return_value=True):
            assert auth.force_relogin() is True
    finally:
        import shutil

        shutil.rmtree(env_path.parent, ignore_errors=True)

