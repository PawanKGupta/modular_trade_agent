"""Exception paths on user UI preference endpoints."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from server.app.routers import user as user_router


def test_save_filter_preset_propagates_errors(monkeypatch):
    class _Boom:
        def get_ui_preferences(self, user_id):
            return {"filter_presets": {}}

        def update_ui_preferences(self, user_id, data):
            raise RuntimeError("write failed")

    monkeypatch.setattr(user_router, "SettingsRepository", lambda db: _Boom())

    payload = MagicMock()
    payload.page = "orders"
    payload.preset_name = "p1"
    payload.filters = {"x": 1}

    with pytest.raises(RuntimeError, match="write failed"):
        user_router.save_filter_preset(
            payload=payload,
            db=MagicMock(),
            current=MagicMock(id=1),
        )


def test_delete_filter_preset_propagates_errors(monkeypatch):
    class _Boom:
        def get_ui_preferences(self, user_id):
            return {"filter_presets": {"orders": {"p1": {}}}}

        def update_ui_preferences(self, user_id, data):
            raise OSError("disk full")

    monkeypatch.setattr(user_router, "SettingsRepository", lambda db: _Boom())

    with pytest.raises(OSError, match="disk full"):
        user_router.delete_filter_preset(
            page="orders",
            preset_name="p1",
            db=MagicMock(),
            current=MagicMock(id=1),
        )


def test_get_filter_presets_returns_page_bucket(monkeypatch):
    class _Repo:
        def get_ui_preferences(self, user_id):
            return {"filter_presets": {"orders": {"mine": {"x": 1}}}}

    monkeypatch.setattr(user_router, "SettingsRepository", lambda db: _Repo())
    out = user_router.get_filter_presets(
        page="orders",
        db=MagicMock(),
        current=SimpleNamespace(id=42),
    )
    assert out.presets == {"mine": {"x": 1}}
