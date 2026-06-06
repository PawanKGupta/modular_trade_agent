"""Branch coverage for ``broker._get_or_create_auth_session``."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import modules.kotak_neo_auto_trader.shared_session_manager as kotak_ssm
from server.app.routers import broker as broker_router


def test_get_or_create_auth_session_raises_when_auth_none(monkeypatch):
    class _Mgr:
        def get_or_create_session(self, user_id, temp_env_file, force_new=False):
            return None

    monkeypatch.setattr(kotak_ssm, "get_shared_session_manager", lambda: _Mgr())

    with pytest.raises(HTTPException) as ei:
        broker_router._get_or_create_auth_session(1, "/tmp/x.env", MagicMock(), force_new=False)
    assert ei.value.status_code == 503


def test_get_or_create_auth_session_logs_when_auth_present(monkeypatch, caplog):
    class _Auth:
        def is_authenticated(self):
            return False

        def get_client(self):
            return None

    class _Mgr:
        def get_or_create_session(self, user_id, temp_env_file, force_new=False):
            return _Auth()

    monkeypatch.setattr(kotak_ssm, "get_shared_session_manager", lambda: _Mgr())

    with caplog.at_level("INFO"):
        out = broker_router._get_or_create_auth_session(
            2, "/tmp/y.env", MagicMock(), force_new=True
        )
    assert out is not None
    assert any("SHARED_SESSION" in r.message for r in caplog.records)
