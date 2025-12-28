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
