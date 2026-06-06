"""Unit tests for admin cash payment recording on performance bills."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from src.application.services.performance_bill_payment_service import (
    PerformanceBillPaymentError,
    PerformanceBillPaymentService,
)
from src.infrastructure.db.models import (
    BillingAdminSettings,
    BillingTransactionStatus,
    MonthlyPerformanceBill,
    PerformanceBillStatus,
    UserRole,
    Users,
)
from src.infrastructure.persistence.billing_repository import BillingRepository
from src.infrastructure.persistence.performance_billing_repository import (
    PerformanceBillingRepository,
)


@pytest.fixture
def admin_user(db_session) -> Users:
    u = Users(
        email="cash-admin@test.local",
        name="Admin",
        password_hash="x",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def broker_user(db_session) -> Users:
    u = Users(
        email="cash-broker@test.local",
        name="Broker",
        password_hash="x",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _add_open_bill(db_session, *, user_id: int, payable: float = 22.81) -> int:
    db_session.add(BillingAdminSettings(id=1))
    gen = datetime(2026, 5, 31, 12, 0, 0)
    bill = PerformanceBillingRepository(db_session).create_bill(
        user_id=user_id,
        bill_month=date(2026, 5, 1),
        generated_at=gen,
        due_at=datetime(2026, 6, 15, 12, 0, 0),
        previous_carry_forward_loss=0.0,
        current_month_pnl=228.05,
        fee_percentage=10.0,
        chargeable_profit=228.05,
        fee_amount=22.805,
        new_carry_forward_loss=0.0,
        payable_amount=payable,
        status=PerformanceBillStatus.PENDING_PAYMENT,
    )
    db_session.commit()
    return bill.id


def test_record_cash_payment_marks_bill_paid(db_session, admin_user, broker_user):
    bill_id = _add_open_bill(db_session, user_id=broker_user.id)
    svc = PerformanceBillPaymentService(db_session)
    result = svc.record_cash_payment(bill_id, admin_user, note="Received at office")

    assert result["bill_id"] == bill_id
    assert result["user_id"] == broker_user.id
    assert result["amount_paise"] == 2281

    bill = db_session.get(MonthlyPerformanceBill, bill_id)
    assert bill.status == PerformanceBillStatus.PAID
    assert bill.paid_at is not None
    assert bill.razorpay_payment_id.startswith("cash-bill-")

    txs = BillingRepository(db_session).list_transactions(user_id=broker_user.id, limit=10)
    assert len(txs) == 1
    assert txs[0].status == BillingTransactionStatus.CAPTURED
    assert txs[0].amount_paise == 2281
    assert "Cash payment" in (txs[0].failure_reason or "")


def test_record_cash_payment_rejects_already_paid(db_session, admin_user, broker_user):
    bill_id = _add_open_bill(db_session, user_id=broker_user.id)
    svc = PerformanceBillPaymentService(db_session)
    svc.record_cash_payment(bill_id, admin_user)
    with pytest.raises(PerformanceBillPaymentError, match="already paid"):
        svc.record_cash_payment(bill_id, admin_user)
