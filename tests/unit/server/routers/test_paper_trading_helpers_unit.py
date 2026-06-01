"""Unit tests for small ``paper_trading`` router helpers."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from server.app.routers.paper_trading import (
    ClosedPosition,
    _parse_iso_date,
    _upsert_pnl_from_closed_positions,
)


def test_parse_iso_date_none_and_invalid():
    assert _parse_iso_date(None) is None
    assert _parse_iso_date("") is None
    assert _parse_iso_date("not-a-date") is None


def test_parse_iso_date_accepts_z_suffix():
    assert _parse_iso_date("2026-03-15T10:00:00Z") == date(2026, 3, 15)


def test_upsert_pnl_from_closed_positions_swallows_repo_errors(monkeypatch):
    class BoomRepo:
        def upsert(self, record):
            raise RuntimeError("db")

    monkeypatch.setattr(
        "server.app.routers.paper_trading.PnlRepository",
        lambda db: BoomRepo(),
    )

    pos = ClosedPosition(
        symbol="X",
        entry_price=1.0,
        exit_price=2.0,
        quantity=1,
        buy_date="2026-01-01",
        sell_date="2026-01-02",
        holding_days=1,
        realized_pnl=5.0,
        pnl_percentage=1.0,
        charges=0.1,
    )
    # Should not raise
    _upsert_pnl_from_closed_positions(1, [pos], MagicMock())
