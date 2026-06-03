"""Circuit-defer placeholder rows in OrdersRepository."""

import pytest

from src.infrastructure.db.models import OrderStatus, Orders, Users
from src.infrastructure.persistence.orders_repository import (
    CIRCUIT_DEFER_ORIG_SOURCE,
    OrdersRepository,
)


@pytest.fixture
def test_user(db_session):
    user = Users(email="circuit_defer@example.com", password_hash="hash", role="user")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_upsert_list_and_clear_circuit_defer(db_session, test_user):
    repo = OrdersRepository(db_session)
    meta = {
        "circuit_defer": True,
        "upper_circuit": 1859.2,
        "ema9_target": 1860.4,
        "trade": {"symbol": "AXISCADES-EQ", "placed_symbol": "AXISCADES-EQ", "qty": 5},
    }

    row = repo.upsert_circuit_defer_sell(
        user_id=test_user.id,
        symbol="AXISCADES-EQ",
        quantity=5,
        price=1860.4,
        order_metadata=meta,
    )
    assert row is not None
    assert row.orig_source == CIRCUIT_DEFER_ORIG_SOURCE
    assert row.broker_order_id is None

    listed = repo.list_circuit_deferred_sells(test_user.id)
    assert len(listed) == 1

    row2 = repo.upsert_circuit_defer_sell(
        user_id=test_user.id,
        symbol="AXISCADES-EQ",
        quantity=5,
        price=1855.0,
        order_metadata={**meta, "ema9_target": 1855.0},
    )
    assert row2.id == row.id
    assert row2.price == 1855.0

    assert repo.clear_circuit_defer_sell(test_user.id, "AXISCADES-EQ") is True
    db_session.refresh(row)
    assert row.status == OrderStatus.CANCELLED
    assert repo.list_circuit_deferred_sells(test_user.id) == []
