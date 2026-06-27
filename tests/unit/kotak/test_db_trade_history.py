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
