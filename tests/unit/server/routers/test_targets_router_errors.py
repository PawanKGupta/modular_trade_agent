"""Error path for ``targets`` list endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from server.app.routers import targets as targets_router


def test_list_targets_wraps_repository_errors(monkeypatch):
    class _BoomRepo:
        def get_active_by_user(self, user_id):
            raise RuntimeError("db")

    monkeypatch.setattr(targets_router, "TargetsRepository", lambda db: _BoomRepo())

    with pytest.raises(HTTPException) as ei:
        targets_router.list_targets(db=MagicMock(), current=MagicMock(id=1))

    assert ei.value.status_code == 500
    assert "Failed to fetch targets" in str(ei.value.detail)
