from datetime import date, datetime

import pytest

from server.app.services.pnl_calculation_service import PnlCalculationService
from src.infrastructure.db.models import Orders, PnlDaily, Positions, TradeMode, Users


@pytest.fixture
def user(db_session):
    record = Users(email="test@example.com", password_hash="secret")
    db_session.add(record)
    db_session.commit()
    return record


def test_calculate_daily_pnl_aggregates_components(db_session, user):
    target_date = date(2024, 1, 2)

    order = Orders(
        user_id=user.id,
        symbol="TCS",
        side="buy",
        order_type="market",
        quantity=10,
        price=100.0,
        avg_price=100.0,
        placed_at=datetime(2024, 1, 2, 10, 0, 0),
        trade_mode=TradeMode.BROKER,
    )
    closed_position = Positions(
        user_id=user.id,
        symbol="TCS",
        quantity=10,
        avg_price=90.0,
        closed_at=datetime(2024, 1, 2, 12, 0, 0),
        realized_pnl=50.0,
        exit_price=95.0,
    )
    open_position = Positions(
        user_id=user.id,
        symbol="INFY",
        quantity=5,
        avg_price=20.0,
        unrealized_pnl=25.0,
    )

    db_session.add_all([order, closed_position, open_position])
    db_session.commit()

    service = PnlCalculationService(db_session)

    record = service.calculate_daily_pnl(user.id, target_date)

    assert isinstance(record, PnlDaily)
    assert record.date == target_date
    assert record.realized_pnl == pytest.approx(50.0)
    assert record.unrealized_pnl == pytest.approx(25.0)
    expected_fee = (order.avg_price or order.price or 0) * order.quantity * service.DEFAULT_FEE_RATE
    assert record.fees == pytest.approx(expected_fee)

    stored = db_session.query(PnlDaily).filter_by(user_id=user.id, date=target_date).one()
    assert stored.realized_pnl == pytest.approx(50.0)
    assert stored.unrealized_pnl == pytest.approx(25.0)
    assert stored.fees == pytest.approx(expected_fee)
