import sys
from types import SimpleNamespace

import pytest

from server.app.services import mtm_updater


class DummySession:
    def __init__(self, positions):
        self._positions = positions
        self.committed = 0
        self.rolled_back = 0

    def query(self, _model):
        return self

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._positions)

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1

    def close(self):
        pass


class DummyPosition(SimpleNamespace):
    def __init__(self, symbol: str, quantity: float, avg_price: float):
        super().__init__(
            symbol=symbol,
            quantity=quantity,
            avg_price=avg_price,
            unrealized_pnl=0.0,
            closed_at=None,
        )


def test_update_unrealized_pnl_for_position_updates_value():
    db = DummySession([])
    position = DummyPosition("ABC", quantity=10, avg_price=100.0)

    updated = mtm_updater.update_unrealized_pnl_for_position(db, position, live_price=120.0)

    assert updated is True
    assert position.unrealized_pnl == pytest.approx(200.0)
    assert db.committed == 1


def test_update_mtm_for_user_counts_updates_and_skips(monkeypatch):
    positions = [
        DummyPosition("ABC", quantity=5, avg_price=50.0),
        DummyPosition("NO_PRICE", quantity=3, avg_price=30.0),
        DummyPosition("ZERO_QTY", quantity=0, avg_price=10.0),
    ]
    db = DummySession(positions)

    def fake_get_live_price(symbol: str):
        if symbol == "NO_PRICE":
            return None
        return 75.0

    monkeypatch.setattr(mtm_updater, "get_live_price", fake_get_live_price)

    stats = mtm_updater.update_mtm_for_user(user_id=1, db=db)

    assert stats["total"] == 3
    assert stats["updated"] == 1  # Only ABC gets updated
    assert stats["skipped"] == 1  # NO_PRICE has no live price
    assert stats["failed"] == 1  # ZERO_QTY cannot be updated


def test_get_live_price_prefers_current_price(monkeypatch):
    class _CurrentPriceTicker:
        def __init__(self, ticker: str):
            self.info = {"currentPrice": 123.45}
            self.fast_info = {"lastPrice": 0.0}

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=_CurrentPriceTicker))

    assert mtm_updater.get_live_price("RANDOM") == 123.45


def test_get_live_price_falls_back_to_fast_info(monkeypatch):
    class _FastInfoTicker:
        def __init__(self, ticker: str):
            self.info = {}
            self.fast_info = {"lastPrice": 77.0}

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=_FastInfoTicker))

    assert mtm_updater.get_live_price("RANDOM") == 77.0


def test_get_live_price_handles_import_errors(monkeypatch):
    class _FailingTicker:
        def __init__(self, ticker: str):
            raise RuntimeError("boom")

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=_FailingTicker))

    assert mtm_updater.get_live_price("RANDOM") is None


def test_update_unrealized_pnl_rolls_back_on_commit_error():
    class _FailingSession(DummySession):
        def commit(self):
            raise RuntimeError("cannot commit")

    db = _FailingSession([])
    position = DummyPosition("ERR", quantity=2, avg_price=5.0)

    updated = mtm_updater.update_unrealized_pnl_for_position(db, position, live_price=7.0)

    assert updated is False
    assert db.rolled_back == 1


def test_update_mtm_for_all_users_passes_session_to_user_updater(monkeypatch):
    class _UserQuery:
        def __init__(self, ids):
            self._ids = ids

        def filter(self, *args, **kwargs):
            return self

        def distinct(self):
            return self

        def all(self):
            return [(uid,) for uid in self._ids]

    class _UserSession:
        def __init__(self, ids):
            self.closed = False
            self._ids = ids

        def query(self, _):
            return _UserQuery(self._ids)

        def close(self):
            self.closed = True

    db = _UserSession([11, 22])
    stats_returned = {
        11: {
            "total": 0,
            "updated": 1,
            "failed": 0,
            "skipped": 0,
        },
        22: {
            "total": 0,
            "updated": 0,
            "failed": 1,
            "skipped": 0,
        },
    }

    called = {}

    def _fake_update(user_id: int, session):
        called[user_id] = session
        return stats_returned[user_id]

    monkeypatch.setattr(mtm_updater, "SessionLocal", lambda: db)
    monkeypatch.setattr(mtm_updater, "update_mtm_for_user", _fake_update)

    result = mtm_updater.update_mtm_for_all_users()

    assert result == stats_returned
    assert called == {11: db, 22: db}
    assert db.closed is True
