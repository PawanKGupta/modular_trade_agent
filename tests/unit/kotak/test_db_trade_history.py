"""Characterization tests for AutoTradeEngine's DB-mode trade-history reads (C1, DB increment).

Pins the current behaviour of the repository-backed branches of
``_load_trades_history`` and ``_get_failed_orders`` (the production path, previously
uncovered) so the planned DB-backed TradeHistoryStore extraction can be proven
behavior-preserving. Write-path methods are characterized in a follow-up sub-step.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
from src.infrastructure.db.models import Orders, OrderStatus, Positions, Users


@pytest.fixture
def user_id(db_session):
    user = Users(email="dbhist@example.com", password_hash="x", created_at=datetime(2026, 6, 1))
    db_session.add(user)
    db_session.commit()
    return user.id


@pytest.fixture
def engine(db_session, user_id):
    with patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"):
        auth = Mock()
        auth.is_authenticated.return_value = True
        return AutoTradeEngine(auth=auth, user_id=user_id, db_session=db_session)


def _order(user_id, **kwargs):
    defaults = {
        "user_id": user_id,
        "side": "buy",
        "order_type": "market",
        "quantity": 1,
        "placed_at": datetime(2026, 6, 11, 9, 0, 0),
        "updated_at": datetime(2026, 6, 11, 9, 0, 0),
    }
    defaults.update(kwargs)
    return Orders(**defaults)


def test_db_get_failed_orders_returns_only_failed_as_dicts(engine, db_session, user_id):
    db_session.add_all(
        [
            _order(
                user_id,
                symbol="ABC",
                quantity=10,
                price=100.0,
                status=OrderStatus.FAILED,
                first_failed_at=datetime(2026, 6, 11, 9, 0, 0),
                retry_count=2,
                reason="insufficient funds",
            ),
            _order(user_id, symbol="XYZ", quantity=5, price=50.0, status=OrderStatus.CLOSED),
        ]
    )
    db_session.commit()

    out = engine._get_failed_orders()

    assert len(out) == 1
    fo = out[0]
    assert fo["symbol"] == "ABC"
    assert fo["close"] == 100.0
    assert fo["qty"] == 10
    assert fo["reason"] == "insufficient funds"
    assert fo["first_failed_at"] == "2026-06-11T09:00:00"
    assert fo["retry_count"] == 2
    assert fo["status"] == "failed"


def test_db_load_trades_history_reconstructs_open_closed_and_failed(engine, db_session, user_id):
    # Open position + its buy order metadata -> an "open" trade.
    db_session.add(
        Positions(
            user_id=user_id,
            symbol="REL",
            quantity=10,
            avg_price=100.0,
            opened_at=datetime(2026, 6, 11, 9, 15, 0),
            closed_at=None,
        )
    )
    db_session.add(
        _order(
            user_id,
            symbol="REL",
            quantity=10,
            price=100.0,
            status=OrderStatus.CLOSED,
            order_metadata={"ticker": "REL.NS", "rsi10": 5, "entry_type": "system_recommended"},
        )
    )
    # Closed position -> a "closed" trade.
    db_session.add(
        Positions(
            user_id=user_id,
            symbol="OLD",
            quantity=5,
            avg_price=200.0,
            opened_at=datetime(2026, 6, 10, 9, 15, 0),
            closed_at=datetime(2026, 6, 10, 15, 0, 0),
        )
    )
    # A buy order flagged as a stored failed order via metadata.
    db_session.add(
        _order(
            user_id,
            symbol="FAILSYM",
            quantity=1,
            price=10.0,
            status=OrderStatus.FAILED,
            order_metadata={
                "failed_order": True,
                "failed_order_data": {"symbol": "FAILSYM", "qty": 1},
            },
        )
    )
    db_session.commit()

    data = engine._load_trades_history()

    by_symbol = {t["symbol"]: t for t in data["trades"]}
    assert set(by_symbol) == {"REL", "OLD"}

    open_trade = by_symbol["REL"]
    assert open_trade["status"] == "open"
    assert open_trade["entry_price"] == 100.0
    assert open_trade["qty"] == 10
    assert open_trade["ticker"] == "REL.NS"  # pulled from order metadata

    closed_trade = by_symbol["OLD"]
    assert closed_trade["status"] == "closed"
    assert closed_trade["qty"] == 5

    assert data["failed_orders"] == [{"symbol": "FAILSYM", "qty": 1}]


# --------------------------------------------------------------------------- write path
# Note on the test DB: tests run against in-memory SQLite (forced by tests/conftest.py),
# separate from the Postgres runtime. The positions upsert and mark_failed/mark_cancelled
# paths are written to be dialect-agnostic, so they're characterized faithfully here. The
# new-failed-order create path uses orders_repo.create_amo() (Postgres-only
# INSERT ... ON CONFLICT) and is NOT faithfully testable on SQLite — see the skipped test.


def test_db_append_trade_creates_open_position(engine, db_session, user_id):
    engine._append_trade(
        {
            "symbol": "REL",
            "status": "open",
            "qty": 10,
            "entry_price": 100.0,
            "entry_time": "2026-06-11T09:15:00",
        }
    )

    open_pos = [p for p in engine.positions_repo.list(user_id) if p.closed_at is None]
    assert [(p.symbol.upper(), p.quantity, p.avg_price) for p in open_pos] == [("REL", 10, 100.0)]


def test_db_append_trade_upserts_existing_position(engine, db_session, user_id):
    db_session.add(
        Positions(
            user_id=user_id,
            symbol="REL",
            quantity=10,
            avg_price=100.0,
            opened_at=datetime(2026, 6, 11, 9, 15, 0),
            closed_at=None,
        )
    )
    db_session.commit()

    engine._append_trade(
        {
            "symbol": "REL",
            "status": "open",
            "qty": 20,
            "entry_price": 105.0,
            "entry_time": "2026-06-11T09:20:00",
        }
    )

    open_pos = [p for p in engine.positions_repo.list(user_id) if p.closed_at is None]
    # Upsert, not a duplicate.
    assert len(open_pos) == 1
    assert open_pos[0].quantity == 20
    assert open_pos[0].avg_price == 105.0


def test_db_remove_failed_order_marks_cancelled(engine, db_session, user_id):
    db_session.add(
        _order(
            user_id,
            symbol="ABC",
            quantity=5,
            price=50.0,
            status=OrderStatus.FAILED,
            first_failed_at=datetime(2026, 6, 11, 9, 0, 0),
        )
    )
    db_session.commit()
    assert len(engine._get_failed_orders()) == 1

    engine._remove_failed_order("ABC")

    # No longer FAILED (marked CANCELLED), so it drops out of the failed-order list.
    assert engine._get_failed_orders() == []


def test_db_add_failed_order_updates_existing(engine, db_session, user_id):
    db_session.add(
        _order(
            user_id,
            symbol="ABC",
            quantity=5,
            price=50.0,
            status=OrderStatus.FAILED,
            reason="old reason",
            retry_count=0,
            first_failed_at=datetime(2026, 6, 11, 9, 0, 0),
        )
    )
    db_session.commit()

    engine._add_failed_order(
        {"symbol": "ABC", "qty": 5, "close": 50.0, "reason": "insufficient_balance"}
    )

    failed = engine._get_failed_orders()
    assert len(failed) == 1  # de-duplicated: updated, not appended
    assert "insufficient_balance" in failed[0]["reason"]


# The new-failed-order CREATE path (orders_repo.create_amo -> Postgres INSERT ... ON CONFLICT)
# is Postgres-only and cannot run on in-memory SQLite; it is covered by
# tests/integration/kotak/test_db_trade_history_postgres.py (runs in the Postgres CI job).
