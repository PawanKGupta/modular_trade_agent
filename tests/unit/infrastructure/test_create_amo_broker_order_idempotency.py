"""create_amo must not insert a second row when broker_order_id already exists."""

import pytest

from src.infrastructure.db.models import Orders, OrderStatus, TradeMode, Users
from src.infrastructure.persistence.orders_repository import OrdersRepository


@pytest.fixture
def test_user(db_session):
    user = Users(email="idempotent@example.com", password_hash="hash", role="user")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_create_amo_returns_existing_row_for_duplicate_broker_order_id(db_session, test_user):
    repo = OrdersRepository(db_session)
    broker_id = "PT20260505U10001"

    first = repo.create_amo(
        user_id=test_user.id,
        symbol="INDIANB",
        side="buy",
        order_type="market",
        quantity=10,
        price=831.65,
        broker_order_id=broker_id,
        order_id=broker_id,
        trade_mode=TradeMode.PAPER,
    )
    db_session.commit()

    second = repo.create_amo(
        user_id=test_user.id,
        symbol="INDIANB",
        side="buy",
        order_type="market",
        quantity=10,
        price=831.65,
        broker_order_id=broker_id,
        order_id=broker_id,
        trade_mode=TradeMode.PAPER,
    )

    assert second.id == first.id
    rows = (
        db_session.query(Orders)
        .filter(Orders.user_id == test_user.id, Orders.broker_order_id == broker_id)
        .all()
    )
    assert len(rows) == 1


def test_create_amo_allows_second_row_after_first_buy_is_closed(db_session, test_user):
    """Active-buy dedupe still applies; broker id dedupe prevents ghost pending rows."""
    repo = OrdersRepository(db_session)
    broker_id = "PT20260505U10002"

    closed = repo.create_amo(
        user_id=test_user.id,
        symbol="INDIANB",
        side="buy",
        order_type="market",
        quantity=10,
        price=831.65,
        broker_order_id=broker_id,
        trade_mode=TradeMode.PAPER,
    )
    closed.status = OrderStatus.CLOSED
    db_session.commit()

    dup = repo.create_amo(
        user_id=test_user.id,
        symbol="INDIANB",
        side="buy",
        order_type="market",
        quantity=10,
        price=831.65,
        broker_order_id=broker_id,
        trade_mode=TradeMode.PAPER,
    )

    assert dup.id == closed.id
    assert (
        db_session.query(Orders)
        .filter(Orders.user_id == test_user.id, Orders.broker_order_id == broker_id)
        .count()
        == 1
    )
