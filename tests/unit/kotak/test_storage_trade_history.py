"""Characterization tests for the trade-history JSON store (modules/kotak_neo_auto_trader/storage.py).

These pin the CURRENT behavior of the file-based trade-history / failed-order I/O so the
planned TradeHistoryStore extraction (C1 decomposition) can be proven behavior-preserving.
Time-dependent functions are driven by monkeypatching the module's ist_now / ist_now_naive.
"""

import json
from datetime import datetime

import pytest

from modules.kotak_neo_auto_trader import storage


def _read(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _seed(path: str, *, trades=None, failed_orders=None, last_run=None) -> None:
    storage.save_history(
        path,
        {
            "trades": trades or [],
            "failed_orders": failed_orders or [],
            "last_run": last_run,
        },
    )


# --------------------------------------------------------------------------- load / save


def test_load_history_creates_default_when_missing(tmp_path):
    p = str(tmp_path / "trades.json")
    data = storage.load_history(p)
    assert data == {"trades": [], "failed_orders": [], "last_run": None}
    # The default template is also written to disk.
    assert _read(p) == {"trades": [], "failed_orders": [], "last_run": None}


def test_save_and_load_round_trip(tmp_path):
    p = str(tmp_path / "trades.json")
    payload = {
        "trades": [{"symbol": "ABC"}],
        "failed_orders": [],
        "last_run": "2026-06-11T09:30:00",
    }
    storage.save_history(p, payload)
    assert storage.load_history(p) == payload


def test_load_history_returns_independent_defaults(tmp_path):
    """Regression: defaults must not share mutable list state across calls.

    A shallow copy of the module template previously let one caller's append to
    ``failed_orders``/``trades`` leak into every later default load in the process.
    """
    d1 = storage.load_history(str(tmp_path / "a.json"))
    d1["failed_orders"].append({"symbol": "LEAK"})
    d1["trades"].append({"symbol": "LEAK"})

    d2 = storage.load_history(str(tmp_path / "b.json"))
    assert d2["failed_orders"] == []
    assert d2["trades"] == []


# --------------------------------------------------------------------------- append_trade


def test_append_trade_accumulates_and_sets_last_run(tmp_path, monkeypatch):
    p = str(tmp_path / "trades.json")
    monkeypatch.setattr(storage, "ist_now", lambda: datetime(2026, 6, 11, 9, 30, 0))

    storage.append_trade(p, {"symbol": "ABC"})
    storage.append_trade(p, {"symbol": "XYZ"})

    data = _read(p)
    assert [t["symbol"] for t in data["trades"]] == ["ABC", "XYZ"]
    assert data["last_run"] == "2026-06-11T09:30:00"


# --------------------------------------------------------------------------- failed orders: add


def test_add_failed_order_new_sets_metadata(tmp_path, monkeypatch):
    p = str(tmp_path / "trades.json")
    monkeypatch.setattr(storage, "ist_now", lambda: datetime(2026, 6, 11, 9, 0, 0))

    storage.add_failed_order(p, {"symbol": "ABC", "qty": 10})

    fos = _read(p)["failed_orders"]
    assert len(fos) == 1
    assert fos[0]["symbol"] == "ABC"
    assert fos[0]["first_failed_at"] == "2026-06-11T09:00:00"
    assert fos[0]["retry_count"] == 0


def test_add_failed_order_dedups_and_updates_existing(tmp_path, monkeypatch):
    p = str(tmp_path / "trades.json")
    monkeypatch.setattr(storage, "ist_now", lambda: datetime(2026, 6, 11, 9, 0, 0))
    storage.add_failed_order(p, {"symbol": "ABC", "qty": 10})

    monkeypatch.setattr(storage, "ist_now", lambda: datetime(2026, 6, 11, 9, 5, 0))
    storage.add_failed_order(p, {"symbol": "ABC", "qty": 20})

    fos = _read(p)["failed_orders"]
    assert len(fos) == 1  # no duplicate symbol
    assert fos[0]["qty"] == 20  # latest info merged in
    assert fos[0]["last_retry_attempt"] == "2026-06-11T09:05:00"
    assert fos[0]["first_failed_at"] == "2026-06-11T09:00:00"  # original timestamp preserved


# --------------------------------------------------------------------------- failed orders: remove


def test_remove_failed_order_removes_only_matching_symbol(tmp_path):
    p = str(tmp_path / "trades.json")
    _seed(p, failed_orders=[{"symbol": "ABC"}, {"symbol": "XYZ"}])

    storage.remove_failed_order(p, "ABC")

    assert [fo["symbol"] for fo in _read(p)["failed_orders"]] == ["XYZ"]


# --------------------------------------------------------------------------- failed orders: get (date logic)


def test_get_failed_orders_returns_all_when_flag_false(tmp_path):
    p = str(tmp_path / "trades.json")
    _seed(p, failed_orders=[{"symbol": "OLD", "first_failed_at": "2020-01-01T00:00:00"}])
    out = storage.get_failed_orders(p, include_previous_day_before_market=False)
    assert [o["symbol"] for o in out] == ["OLD"]


def test_get_failed_orders_today_is_included(tmp_path, monkeypatch):
    p = str(tmp_path / "trades.json")
    monkeypatch.setattr(storage, "ist_now_naive", lambda: datetime(2026, 6, 11, 10, 0, 0))
    _seed(p, failed_orders=[{"symbol": "A", "first_failed_at": "2026-06-11T08:00:00"}])
    assert [o["symbol"] for o in storage.get_failed_orders(p)] == ["A"]


def test_get_failed_orders_yesterday_before_open_included(tmp_path, monkeypatch):
    p = str(tmp_path / "trades.json")
    monkeypatch.setattr(storage, "ist_now_naive", lambda: datetime(2026, 6, 11, 9, 0, 0))  # < 09:15
    _seed(p, failed_orders=[{"symbol": "A", "first_failed_at": "2026-06-10T15:00:00"}])
    assert [o["symbol"] for o in storage.get_failed_orders(p)] == ["A"]


def test_get_failed_orders_yesterday_after_open_excluded(tmp_path, monkeypatch):
    p = str(tmp_path / "trades.json")
    monkeypatch.setattr(
        storage, "ist_now_naive", lambda: datetime(2026, 6, 11, 9, 30, 0)
    )  # > 09:15
    _seed(p, failed_orders=[{"symbol": "A", "first_failed_at": "2026-06-10T15:00:00"}])
    assert storage.get_failed_orders(p) == []


def test_get_failed_orders_older_than_yesterday_excluded(tmp_path, monkeypatch):
    p = str(tmp_path / "trades.json")
    monkeypatch.setattr(storage, "ist_now_naive", lambda: datetime(2026, 6, 11, 9, 0, 0))
    _seed(p, failed_orders=[{"symbol": "A", "first_failed_at": "2026-06-01T10:00:00"}])
    assert storage.get_failed_orders(p) == []


def test_get_failed_orders_missing_timestamp_skipped(tmp_path, monkeypatch):
    p = str(tmp_path / "trades.json")
    monkeypatch.setattr(storage, "ist_now_naive", lambda: datetime(2026, 6, 11, 9, 0, 0))
    _seed(p, failed_orders=[{"symbol": "A"}])  # no first_failed_at
    assert storage.get_failed_orders(p) == []


# --------------------------------------------------------------------------- cleanup_expired_failed_orders


def test_cleanup_expired_failed_orders_keeps_today_removes_rest(tmp_path, monkeypatch):
    p = str(tmp_path / "trades.json")
    monkeypatch.setattr(
        storage, "ist_now_naive", lambda: datetime(2026, 6, 11, 9, 30, 0)
    )  # after open
    _seed(
        p,
        failed_orders=[
            {"symbol": "TODAY", "first_failed_at": "2026-06-11T08:00:00"},
            {"symbol": "YDAY_AFTER_OPEN", "first_failed_at": "2026-06-10T15:00:00"},
            {"symbol": "OLD", "first_failed_at": "2026-06-01T10:00:00"},
            {"symbol": "NO_TS"},  # missing first_failed_at
        ],
    )

    removed = storage.cleanup_expired_failed_orders(p)

    assert removed == 3
    assert [o["symbol"] for o in _read(p)["failed_orders"]] == ["TODAY"]


def test_cleanup_expired_failed_orders_noop_returns_zero(tmp_path, monkeypatch):
    p = str(tmp_path / "trades.json")
    monkeypatch.setattr(storage, "ist_now_naive", lambda: datetime(2026, 6, 11, 9, 30, 0))
    _seed(p, failed_orders=[{"symbol": "TODAY", "first_failed_at": "2026-06-11T08:00:00"}])

    removed = storage.cleanup_expired_failed_orders(p)

    assert removed == 0
    assert [o["symbol"] for o in _read(p)["failed_orders"]] == ["TODAY"]


# --------------------------------------------------------------------------- mark_position_closed


def test_mark_position_closed_marks_open_trade_and_computes_pnl(tmp_path, monkeypatch):
    p = str(tmp_path / "trades.json")
    monkeypatch.setattr(storage, "ist_now", lambda: datetime(2026, 6, 11, 15, 0, 0))
    _seed(p, trades=[{"symbol": "ABC", "status": "open", "entry_price": 100.0, "qty": 10}])

    ok = storage.mark_position_closed(p, "abc", 110.0, "ORD1")  # case-insensitive match

    assert ok is True
    t = _read(p)["trades"][0]
    assert t["status"] == "closed"
    assert t["exit_price"] == 110.0
    assert t["exit_reason"] == "EMA9_TARGET"
    assert t["sell_order_id"] == "ORD1"
    assert t["pnl"] == pytest.approx(100.0)  # (110 - 100) * 10
    assert t["pnl_pct"] == pytest.approx(10.0)


def test_mark_position_closed_returns_false_when_no_open_position(tmp_path):
    p = str(tmp_path / "trades.json")
    _seed(p, trades=[{"symbol": "ABC", "status": "closed"}])
    assert storage.mark_position_closed(p, "ABC", 110.0, "ORD1") is False
