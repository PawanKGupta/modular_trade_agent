from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from src.application.services.performance_billing_service import (
    PerformanceBillingService,
    user_has_real_broker_configured,
)
from src.infrastructure.db.models import (
    BillingAdminSettings,
    PerformanceBillStatus,
    Positions,
    PnlDaily,
    TradeMode,
    UserPerformanceBillingState,
    UserRole,
    Users,
    UserSettings,
)
from src.infrastructure.persistence.billing_repository import BillingRepository
from src.infrastructure.persistence.performance_billing_repository import (
    PerformanceBillingRepository,
)


@pytest.fixture
def broker_user_and_settings(db_session):
    u = Users(email="perf-bill@test.local", password_hash="x", role=UserRole.USER)
    db_session.add(u)
    db_session.flush()
    settings = UserSettings(
        user_id=u.id,
        trade_mode=TradeMode.BROKER,
        broker="kotak-neo",
        broker_creds_encrypted=b"fake-ciphertext",
    )
    db_session.add(settings)
    db_session.commit()
    return u, settings


def test_user_has_real_broker_configured(broker_user_and_settings):
    _, settings = broker_user_and_settings
    assert user_has_real_broker_configured(settings) is True
    assert user_has_real_broker_configured(None) is False


def test_generate_bill_sums_pnl_and_applies_fee(db_session, broker_user_and_settings):
    u, _ = broker_user_and_settings
    db_session.add(
        Positions(
            user_id=u.id,
            symbol="BILL-EQ",
            quantity=0,
            avg_price=100.0,
            realized_pnl=3000.0,
            closed_at=datetime(2026, 3, 10, 12, 0, 0),
        )
    )
    db_session.add(BillingAdminSettings(id=1))
    db_session.commit()

    svc = PerformanceBillingService(db_session)
    gen_at = datetime(2026, 4, 1, 10, 0, 0)
    bill = svc.generate_bill_for_user_month(u.id, 2026, 3, generated_at=gen_at)
    assert bill is not None
    assert bill.current_month_pnl == 3000.0
    assert bill.chargeable_profit == 3000.0
    assert bill.fee_amount == 300.0
    assert bill.payable_amount == 300.0
    assert bill.new_carry_forward_loss == 0.0
    assert bill.due_at == gen_at + timedelta(days=15)

    st = db_session.get(UserPerformanceBillingState, u.id)
    assert st is not None
    assert float(st.carry_forward_loss) == 0.0


def test_generate_bill_idempotent(db_session, broker_user_and_settings):
    u, _ = broker_user_and_settings
    db_session.add(
        Positions(
            user_id=u.id,
            symbol="BILL2-EQ",
            quantity=0,
            avg_price=10.0,
            realized_pnl=100.0,
            closed_at=datetime(2026, 2, 1, 12, 0, 0),
        )
    )
    db_session.add(BillingAdminSettings(id=1))
    db_session.commit()

    svc = PerformanceBillingService(db_session)
    assert svc.generate_bill_for_user_month(u.id, 2026, 2) is not None
    assert svc.generate_bill_for_user_month(u.id, 2026, 2) is None


def test_carry_forward_applied_next_month(db_session, broker_user_and_settings):
    u, _ = broker_user_and_settings
    db_session.add(BillingAdminSettings(id=1))
    db_session.add(
        Positions(
            user_id=u.id,
            symbol="LOSS-EQ",
            quantity=0,
            avg_price=100.0,
            realized_pnl=-2000.0,
            closed_at=datetime(2026, 1, 5, 12, 0, 0),
        )
    )
    db_session.commit()

    svc = PerformanceBillingService(db_session)
    jan = svc.generate_bill_for_user_month(u.id, 2026, 1)
    assert jan is not None
    assert jan.new_carry_forward_loss == 2000.0

    db_session.add(
        Positions(
            user_id=u.id,
            symbol="WIN-EQ",
            quantity=0,
            avg_price=100.0,
            realized_pnl=3000.0,
            closed_at=datetime(2026, 2, 10, 12, 0, 0),
        )
    )
    db_session.commit()

    feb = svc.generate_bill_for_user_month(u.id, 2026, 2)
    assert feb is not None
    assert feb.previous_carry_forward_loss == 2000.0
    assert feb.chargeable_profit == 1000.0
    assert feb.fee_amount == 100.0


def test_paper_user_skipped(db_session):
    u = Users(email="paper-only@test.local", password_hash="x", role=UserRole.USER)
    db_session.add(u)
    db_session.flush()
    db_session.add(UserSettings(user_id=u.id, trade_mode=TradeMode.PAPER))
    db_session.add(BillingAdminSettings(id=1))
    db_session.commit()

    svc = PerformanceBillingService(db_session)
    assert svc.generate_bill_for_user_month(u.id, 2026, 1) is None


def test_admin_payment_days_config(db_session, broker_user_and_settings):
    u, _ = broker_user_and_settings
    repo = BillingRepository(db_session)
    s = repo.get_admin_settings()
    s.performance_fee_payment_days_after_invoice = 7
    db_session.commit()

    db_session.commit()

    gen_at = datetime(2026, 6, 1, 0, 0, 0)
    bill = PerformanceBillingService(db_session).generate_bill_for_user_month(
        u.id, 2026, 5, generated_at=gen_at
    )
    assert bill is not None
    assert bill.due_at == gen_at + timedelta(days=7)


def test_generate_bill_from_closed_positions_when_pnldaily_empty(
    db_session, broker_user_and_settings
):
    """Regression: broker closes wrote positions only; billing must not read empty pnldaily."""
    u, _ = broker_user_and_settings
    db_session.add(BillingAdminSettings(id=1))
    db_session.add_all(
        [
            Positions(
                user_id=u.id,
                symbol="POWERGRID-EQ",
                quantity=0,
                avg_price=100.0,
                realized_pnl=219.45,
                closed_at=datetime(2026, 5, 21, 15, 0, 0),
            ),
            Positions(
                user_id=u.id,
                symbol="DMART-EQ",
                quantity=0,
                avg_price=200.0,
                realized_pnl=8.60,
                closed_at=datetime(2026, 5, 27, 15, 0, 0),
            ),
        ]
    )
    db_session.commit()

    bill = PerformanceBillingService(db_session).generate_bill_for_user_month(u.id, 2026, 5)
    assert bill is not None
    assert float(bill.current_month_pnl) == pytest.approx(228.05)
    assert float(bill.chargeable_profit) == pytest.approx(228.05)
    assert float(bill.fee_amount) == pytest.approx(22.8)
    assert float(bill.payable_amount) == pytest.approx(22.8)


def test_mark_overdue_bills(db_session, broker_user_and_settings):
    u, _ = broker_user_and_settings
    db_session.add(BillingAdminSettings(id=1))
    gen = datetime(2026, 1, 5, 12, 0, 0)
    bill = PerformanceBillingRepository(db_session).create_bill(
        user_id=u.id,
        bill_month=date(2026, 1, 1),
        generated_at=gen,
        due_at=datetime(2026, 1, 3, 0, 0, 0),
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

    n = PerformanceBillingService(db_session).mark_overdue_bills(now=datetime(2026, 1, 10, 0, 0, 0))
    assert n == 1
    db_session.refresh(bill)
    assert bill.status == PerformanceBillStatus.OVERDUE
