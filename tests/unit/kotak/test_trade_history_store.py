"""Tests for the extracted TradeHistoryStore (C1 decomposition, step 1).

Covers the store wrapper's delegation to storage.py and the engine's file-mode
delegation to the store, proving the extraction is behavior-preserving. The
underlying storage behavior itself is pinned by test_storage_trade_history.py.
"""

import json
from datetime import datetime
from unittest.mock import patch

import pytest

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
from modules.kotak_neo_auto_trader.services import DatabaseTradeHistoryStore, TradeHistoryStore
from src.domain.interfaces.trade_history_store import ITradeHistoryStore
from src.infrastructure.db.models import Users


def _read(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_store_implements_interface(tmp_path):
    store = TradeHistoryStore(str(tmp_path / "t.json"))
    assert isinstance(store, ITradeHistoryStore)


def test_store_load_creates_default_and_round_trips(tmp_path):
    store = TradeHistoryStore(str(tmp_path / "t.json"))
    assert store.load_history() == {"trades": [], "failed_orders": [], "last_run": None}

    payload = {"trades": [{"symbol": "ABC"}], "failed_orders": [], "last_run": "x"}
    store.save_history(payload)
    assert store.load_history() == payload


def test_store_append_and_failed_order_crud(tmp_path, monkeypatch):
    import modules.kotak_neo_auto_trader.storage as storage_mod

    monkeypatch.setattr(storage_mod, "ist_now", lambda: datetime(2026, 6, 11, 9, 0, 0))
    store = TradeHistoryStore(str(tmp_path / "t.json"))

    store.append_trade({"symbol": "ABC"})
    assert [t["symbol"] for t in store.load_history()["trades"]] == ["ABC"]

    store.add_failed_order({"symbol": "XYZ", "qty": 5})
    fos = store.load_history()["failed_orders"]
    assert fos[0]["symbol"] == "XYZ"
    assert fos[0]["first_failed_at"] == "2026-06-11T09:00:00"

    store.remove_failed_order("XYZ")
    assert store.load_history()["failed_orders"] == []


def test_store_get_failed_orders_passes_flag_through(tmp_path, monkeypatch):
    import modules.kotak_neo_auto_trader.storage as storage_mod

    monkeypatch.setattr(storage_mod, "ist_now_naive", lambda: datetime(2026, 6, 11, 9, 30, 0))
    store = TradeHistoryStore(str(tmp_path / "t.json"))
    store.save_history(
        {
            "trades": [],
            "failed_orders": [{"symbol": "OLD", "first_failed_at": "2026-06-10T15:00:00"}],
            "last_run": None,
        }
    )

    # Yesterday + after open -> filtered out when the window is applied.
    assert store.get_failed_orders() == []
    # Flag off -> returned unfiltered.
    assert [
        o["symbol"] for o in store.get_failed_orders(include_previous_day_before_market=False)
    ] == ["OLD"]


def test_store_mark_position_closed(tmp_path, monkeypatch):
    import modules.kotak_neo_auto_trader.storage as storage_mod

    monkeypatch.setattr(storage_mod, "ist_now", lambda: datetime(2026, 6, 11, 15, 0, 0))
    store = TradeHistoryStore(str(tmp_path / "t.json"))
    store.save_history(
        {
            "trades": [{"symbol": "ABC", "status": "open", "entry_price": 100.0, "qty": 10}],
            "failed_orders": [],
            "last_run": None,
        }
    )

    assert store.mark_position_closed("ABC", 110.0, "ORD1") is True
    t = store.load_history()["trades"][0]
    assert t["status"] == "closed"
    assert t["pnl"] == 100.0


@patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
def test_engine_file_mode_delegates_to_store(_mock_auth, tmp_path):
    """No db_session -> file mode -> engine wires a TradeHistoryStore and uses it."""
    engine = AutoTradeEngine(env_file="test.env")

    assert isinstance(engine.history_store, TradeHistoryStore)

    # Repoint the store at a temp file and round-trip through the engine's methods.
    p = str(tmp_path / "engine_trades.json")
    engine.history_path = p
    engine.history_store = TradeHistoryStore(p)

    engine._append_trade({"symbol": "ABC", "qty": 1})
    loaded = engine._load_trades_history()
    assert any(t.get("symbol") == "ABC" for t in loaded.get("trades", []))
    # The store wrote to the expected file.
    assert any(t.get("symbol") == "ABC" for t in _read(p).get("trades", []))


@pytest.fixture
def db_user_id(db_session):
    user = Users(
        email="dbstoretest@example.com", password_hash="x", created_at=datetime(2026, 6, 1)
    )
    db_session.add(user)
    db_session.commit()
    return user.id


def test_db_store_implements_interface(db_session, db_user_id):
    store = DatabaseTradeHistoryStore(db_session=db_session, user_id=db_user_id)
    assert isinstance(store, ITradeHistoryStore)
    history = store.load_history()
    assert history["trades"] == []
    assert history["failed_orders"] == []
    assert isinstance(history["last_run"], str)
