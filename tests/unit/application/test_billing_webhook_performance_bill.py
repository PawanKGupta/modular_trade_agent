"""payment.captured with performance_bill_id marks MonthlyPerformanceBill paid."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.application.services.billing_webhook_service import BillingWebhookService
from src.infrastructure.db.models import (
    BillingAdminSettings,
    PerformanceBillStatus,
    UserRole,
    Users,
)
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.performance_billing_repository import (
    PerformanceBillingRepository,
)


@pytest.fixture
def perf_user(db_session) -> Users:
    u = Users(
        email="perf-webhook@test.local",
        name="U",
        password_hash="x",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _make_payload(*, bill_id: int, user_id: int, amount_paise: int, pay_id: str = "pay_perf_1"):
    return {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": pay_id,
                    "status": "captured",
                    "amount": amount_paise,
                    "currency": "INR",
                    "notes": {
                        "user_id": str(user_id),
                        "performance_bill_id": str(bill_id),
                    },
                }
            }
        },
    }


def test_payment_captured_marks_performance_bill_paid(db_session, perf_user):
    db_session.add(BillingAdminSettings(id=1))
    db_session.commit()
    gen = ist_now()
    bill = PerformanceBillingRepository(db_session).create_bill(
        user_id=perf_user.id,
        bill_month=date(2026, 2, 1),
        generated_at=gen,
        due_at=gen + timedelta(days=15),
        previous_carry_forward_loss=0.0,
        current_month_pnl=5000.0,
        fee_percentage=10.0,
        chargeable_profit=5000.0,
        fee_amount=500.0,
        new_carry_forward_loss=0.0,
        payable_amount=500.0,
        status=PerformanceBillStatus.PENDING_PAYMENT,
    )
    db_session.commit()

    payload = _make_payload(bill_id=bill.id, user_id=perf_user.id, amount_paise=50_000)
    BillingWebhookService(db_session).process_payload(payload)

    db_session.refresh(bill)
    assert bill.status == PerformanceBillStatus.PAID
    assert bill.razorpay_payment_id == "pay_perf_1"
    assert bill.paid_at is not None


def test_payment_captured_marks_overdue_performance_bill_paid(db_session, perf_user):
    db_session.add(BillingAdminSettings(id=1))
    db_session.commit()
    gen = ist_now()
    bill = PerformanceBillingRepository(db_session).create_bill(
        user_id=perf_user.id,
        bill_month=date(2026, 4, 1),
        generated_at=gen,
        due_at=gen,
        previous_carry_forward_loss=0.0,
        current_month_pnl=200.0,
        fee_percentage=10.0,
        chargeable_profit=200.0,
        fee_amount=20.0,
        new_carry_forward_loss=0.0,
        payable_amount=20.0,
        status=PerformanceBillStatus.OVERDUE,
    )
    db_session.commit()

    payload = _make_payload(
        bill_id=bill.id, user_id=perf_user.id, amount_paise=2000, pay_id="pay_perf_od"
    )
    BillingWebhookService(db_session).process_payload(payload)

    db_session.refresh(bill)
    assert bill.status == PerformanceBillStatus.PAID
    assert bill.razorpay_payment_id == "pay_perf_od"


def test_performance_bill_amount_mismatch_skips(db_session, perf_user):
    db_session.add(BillingAdminSettings(id=1))
    db_session.commit()
    gen = ist_now()
    bill = PerformanceBillingRepository(db_session).create_bill(
        user_id=perf_user.id,
        bill_month=date(2026, 3, 1),
        generated_at=gen,
        due_at=gen + timedelta(days=15),
        previous_carry_forward_loss=0.0,
        current_month_pnl=100.0,
        fee_percentage=10.0,
        chargeable_profit=100.0,
        fee_amount=10.0,
        new_carry_forward_loss=0.0,
        payable_amount=10.0,
        status=PerformanceBillStatus.PENDING_PAYMENT,
    )
    db_session.commit()

    payload = _make_payload(
        bill_id=bill.id, user_id=perf_user.id, amount_paise=999, pay_id="pay_wrong"
    )
    BillingWebhookService(db_session).process_payload(payload)

    db_session.refresh(bill)
    assert bill.status == PerformanceBillStatus.PENDING_PAYMENT
    assert bill.paid_at is None
