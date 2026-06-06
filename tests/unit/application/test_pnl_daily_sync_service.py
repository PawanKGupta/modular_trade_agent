"""Tests for pnldaily sync from closed broker positions."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from src.application.services.pnl_daily_sync_service import PnlDailySyncService
from src.infrastructure.db.models import (
    PnlDaily,
    Positions,
    TradeMode,
    UserRole,
    Users,
    UserSettings,
)
from src.infrastructure.persistence.positions_repository import PositionsRepository


@pytest.fixture
def broker_user(db_session):
    u = Users(email="sync@test.local", password_hash="x", role=UserRole.USER)
    db_session.add(u)
    db_session.flush()
    db_session.add(
        UserSettings(
            user_id=u.id,
            trade_mode=TradeMode.BROKER,
            broker="kotak-neo",
            broker_creds_encrypted=b"x",
        )
    )
    db_session.commit()
    db_session.refresh(u)
    return u


def test_materialize_calendar_month_from_closed_positions(db_session, broker_user):
    """Month total comes from positions, not pre-existing pnldaily rows."""
    closed_may_21 = datetime(2026, 5, 21, 15, 0, 0)
    closed_may_27 = datetime(2026, 5, 27, 15, 0, 0)
    db_session.add_all(
        [
            Positions(
                user_id=broker_user.id,
                symbol="POWERGRID-EQ",
                quantity=0,
                avg_price=100.0,
                realized_pnl=219.45,
                closed_at=closed_may_21,
            ),
            Positions(
                user_id=broker_user.id,
                symbol="DMART-EQ",
                quantity=0,
                avg_price=200.0,
                realized_pnl=8.60,
                closed_at=closed_may_27,
            ),
        ]
    )
    db_session.commit()

    total = PnlDailySyncService(db_session).materialize_calendar_month(broker_user.id, 2026, 5)
    assert total == pytest.approx(228.05)

    rows = db_session.query(PnlDaily).filter(PnlDaily.user_id == broker_user.id).all()
    assert len(rows) == 2
    assert {r.date for r in rows} == {date(2026, 5, 21), date(2026, 5, 27)}


def test_mark_closed_syncs_pnldaily(db_session, broker_user):
    repo = PositionsRepository(db_session)
    db_session.add(
        Positions(
            user_id=broker_user.id,
            symbol="TEST-EQ",
            quantity=10,
            avg_price=50.0,
            opened_at=datetime(2026, 5, 10, 10, 0, 0),
        )
    )
    db_session.commit()

    repo.mark_closed(
        broker_user.id,
        "TEST-EQ",
        closed_at=datetime(2026, 5, 12, 11, 0, 0),
        exit_price=55.0,
        exit_reason="TARGET_HIT",
    )

    row = (
        db_session.query(PnlDaily)
        .filter(PnlDaily.user_id == broker_user.id, PnlDaily.date == date(2026, 5, 12))
        .one()
    )
    assert row.realized_pnl == pytest.approx(50.0)  # (55-50)*10


def test_reduce_quantity_full_close_syncs_pnldaily(db_session, broker_user):
    """Full close via reduce_quantity with exit_price updates pnldaily."""
    repo = PositionsRepository(db_session)
    db_session.add(
        Positions(
            user_id=broker_user.id,
            symbol="PARTIAL-EQ",
            quantity=5,
            avg_price=100.0,
            opened_at=datetime(2026, 5, 10, 10, 0, 0),
        )
    )
    db_session.commit()

    repo.reduce_quantity(
        broker_user.id,
        "PARTIAL-EQ",
        sold_quantity=5.0,
        exit_price=110.0,
    )

    row = db_session.query(PnlDaily).filter(PnlDaily.user_id == broker_user.id).one()
    assert row.realized_pnl == pytest.approx(50.0)  # (110-100)*5


def test_materialize_clears_stale_pnldaily_without_positions(db_session, broker_user):
    """Month materialize zeros orphan realized rows not backed by closed positions."""
    db_session.add(
        Positions(
            user_id=broker_user.id,
            symbol="REAL-EQ",
            quantity=0,
            avg_price=100.0,
            realized_pnl=100.0,
            closed_at=datetime(2026, 5, 21, 15, 0, 0),
        )
    )
    db_session.add(
        PnlDaily(
            user_id=broker_user.id,
            date=date(2026, 5, 15),
            realized_pnl=999.0,
            unrealized_pnl=0.0,
            fees=0.0,
        )
    )
    db_session.commit()

    total = PnlDailySyncService(db_session).materialize_calendar_month(broker_user.id, 2026, 5)
    assert total == pytest.approx(100.0)

    stale = (
        db_session.query(PnlDaily)
        .filter(
            PnlDaily.user_id == broker_user.id,
            PnlDaily.date == date(2026, 5, 15),
        )
        .one()
    )
    assert stale.realized_pnl == pytest.approx(0.0)
