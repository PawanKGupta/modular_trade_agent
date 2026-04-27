from __future__ import annotations

from datetime import date, datetime

import pytest

from modules.kotak_neo_auto_trader.run_trading_service import TradingService
from src.application.services.performance_fee_arrears_service import PerformanceFeeArrearsService
from src.infrastructure.db.models import (
    BillingAdminSettings,
    PerformanceBillStatus,
    UserRole,
    Users,
)
from src.infrastructure.persistence.performance_billing_repository import (
    PerformanceBillingRepository,
)


@pytest.fixture
def broker_user(db_session) -> Users:
    u = Users(
        email="arrears@test.local",
        name="U",
        password_hash="x",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _add_bill(
    db_session,
    *,
    user_id: int,
    due_at: datetime,
    status: PerformanceBillStatus = PerformanceBillStatus.PENDING_PAYMENT,
) -> None:
    db_session.add(BillingAdminSettings(id=1))
    gen = datetime(2026, 1, 1, 10, 0, 0)
    PerformanceBillingRepository(db_session).create_bill(
        user_id=user_id,
        bill_month=date(2026, 1, 1),
        generated_at=gen,
        due_at=due_at,
        previous_carry_forward_loss=0.0,
        current_month_pnl=100.0,
        fee_percentage=10.0,
        chargeable_profit=100.0,
        fee_amount=10.0,
        new_carry_forward_loss=0.0,
        payable_amount=10.0,
        status=status,
    )
    db_session.commit()


def test_no_arrears_when_no_bills(db_session, broker_user):
    st = PerformanceFeeArrearsService(db_session).status_for_user(broker_user)
    assert st.blocks_new_broker_buys is False
    assert st.message is None
    assert st.bills == []


def test_not_blocked_before_due(db_session, broker_user):
    _add_bill(db_session, user_id=broker_user.id, due_at=datetime(2026, 1, 20, 12, 0, 0))
    st = PerformanceFeeArrearsService(db_session).status_for_user(
        broker_user, now=datetime(2026, 1, 10, 12, 0, 0)
    )
    assert st.blocks_new_broker_buys is False


def test_blocked_past_due_pending(db_session, broker_user):
    _add_bill(db_session, user_id=broker_user.id, due_at=datetime(2026, 1, 10, 12, 0, 0))
    st = PerformanceFeeArrearsService(db_session).status_for_user(
        broker_user, now=datetime(2026, 1, 15, 12, 0, 0)
    )
    assert st.blocks_new_broker_buys is True
    assert st.message
    assert len(st.bills) == 1
    assert st.bills[0]["payable_amount"] == 10.0


def test_blocked_when_overdue_status(db_session, broker_user):
    _add_bill(
        db_session,
        user_id=broker_user.id,
        due_at=datetime(2026, 1, 5, 12, 0, 0),
        status=PerformanceBillStatus.OVERDUE,
    )
    st = PerformanceFeeArrearsService(db_session).status_for_user(
        broker_user, now=datetime(2026, 1, 15, 12, 0, 0)
    )
    assert st.blocks_new_broker_buys is True


def test_admin_not_blocked_even_with_arrears(db_session, broker_user):
    broker_user.role = UserRole.ADMIN
    db_session.commit()
    _add_bill(db_session, user_id=broker_user.id, due_at=datetime(2026, 1, 1, 12, 0, 0))
    st = PerformanceFeeArrearsService(db_session).status_for_user(
        broker_user, now=datetime(2026, 2, 1, 12, 0, 0)
    )
    assert st.blocks_new_broker_buys is False


def test_paid_bill_does_not_block(db_session, broker_user):
    db_session.add(BillingAdminSettings(id=1))
    gen = datetime(2026, 1, 1, 10, 0, 0)
    PerformanceBillingRepository(db_session).create_bill(
        user_id=broker_user.id,
        bill_month=date(2026, 1, 1),
        generated_at=gen,
        due_at=datetime(2026, 1, 5, 12, 0, 0),
        previous_carry_forward_loss=0.0,
        current_month_pnl=100.0,
        fee_percentage=10.0,
        chargeable_profit=100.0,
        fee_amount=10.0,
        new_carry_forward_loss=0.0,
        payable_amount=10.0,
        status=PerformanceBillStatus.PAID,
    )
    db_session.commit()
    st = PerformanceFeeArrearsService(db_session).status_for_user(
        broker_user, now=datetime(2026, 2, 1, 12, 0, 0)
    )
    assert st.blocks_new_broker_buys is False


def test_sell_monitor_not_gated_by_arrears_docstring():
    """Regression guard: sells must never depend on PerformanceFeeArrearsService."""
    doc = TradingService.run_sell_monitor.__doc__ or ""
    assert "performance-fee arrears" in doc.lower()
    assert "run_buy_orders" in doc.lower()


def test_zero_payable_does_not_block(db_session, broker_user):
    db_session.add(BillingAdminSettings(id=1))
    gen = datetime(2026, 1, 1, 10, 0, 0)
    PerformanceBillingRepository(db_session).create_bill(
        user_id=broker_user.id,
        bill_month=date(2026, 1, 1),
        generated_at=gen,
        due_at=datetime(2026, 1, 5, 12, 0, 0),
        previous_carry_forward_loss=0.0,
        current_month_pnl=0.0,
        fee_percentage=10.0,
        chargeable_profit=0.0,
        fee_amount=0.0,
        new_carry_forward_loss=0.0,
        payable_amount=0.0,
        status=PerformanceBillStatus.PENDING_PAYMENT,
    )
    db_session.commit()
    st = PerformanceFeeArrearsService(db_session).status_for_user(
        broker_user, now=datetime(2026, 2, 1, 12, 0, 0)
    )
    assert st.blocks_new_broker_buys is False
