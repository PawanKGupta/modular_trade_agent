"""Generate end-of-month performance fee bills for users on real broker mode."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.application.services.performance_fee_invoice_calculator import (
    compute_performance_fee_invoice,
)
from src.infrastructure.db.models import (
    MonthlyPerformanceBill,
    TradeMode,
    Users,
    UserSettings,
)
from src.infrastructure.db.timezone_utils import ist_now, ist_now_naive
from src.infrastructure.persistence.billing_repository import BillingRepository
from src.infrastructure.persistence.performance_billing_repository import (
    PerformanceBillingRepository,
)
from src.infrastructure.persistence.pnl_repository import PnlRepository


def user_has_real_broker_configured(settings: UserSettings | None) -> bool:
    if not settings:
        return False
    if settings.trade_mode != TradeMode.BROKER:
        return False
    if not (settings.broker or "").strip():
        return False
    if not settings.broker_creds_encrypted:
        return False
    return True


class PerformanceBillingService:
    def __init__(self, db: Session):
        self.db = db
        self._perf = PerformanceBillingRepository(db)
        self._pnl = PnlRepository(db)
        self._billing = BillingRepository(db)

    def iter_broker_trading_user_ids(self) -> Iterable[int]:
        stmt = (
            select(UserSettings.user_id)
            .join(Users, Users.id == UserSettings.user_id)
            .where(UserSettings.trade_mode == TradeMode.BROKER)
            .where(UserSettings.broker.isnot(None))
            .where(UserSettings.broker != "")
            .where(UserSettings.broker_creds_encrypted.isnot(None))
        )
        return [int(x) for x in self.db.execute(stmt).scalars().all()]

    def generate_bill_for_user_month(
        self,
        user_id: int,
        year: int,
        month: int,
        *,
        generated_at: datetime | None = None,
    ) -> MonthlyPerformanceBill | None:
        """
        Sum realized PnL for the calendar month, apply carry-forward fee rules, persist bill
        and updated carry-forward. Skips if the user is not on a configured broker or a bill
        already exists for that month.
        """
        settings = self.db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        ).scalar_one_or_none()
        if not user_has_real_broker_configured(settings):
            return None

        bill_month = date(year, month, 1)
        if self._perf.get_bill_for_month(user_id, bill_month):
            return None

        admin = self._billing.get_admin_settings()
        fee_pct = float(admin.performance_fee_default_percentage)
        pay_days = int(admin.performance_fee_payment_days_after_invoice)

        current_month_pnl = self._pnl.sum_realized_pnl_calendar_month(user_id, year, month)
        state = self._perf.get_or_create_state(user_id)
        prev_carry = float(state.carry_forward_loss or 0.0)

        calc = compute_performance_fee_invoice(prev_carry, current_month_pnl, fee_pct)
        gen_at = generated_at or ist_now()
        due_at = gen_at + timedelta(days=pay_days)

        bill = self._perf.create_bill(
            user_id=user_id,
            bill_month=bill_month,
            generated_at=gen_at,
            due_at=due_at,
            previous_carry_forward_loss=float(calc["previous_carry_forward_loss"]),
            current_month_pnl=float(calc["current_month_pnl"]),
            fee_percentage=fee_pct,
            chargeable_profit=float(calc["chargeable_profit"]),
            fee_amount=float(calc["fee_amount"]),
            new_carry_forward_loss=float(calc["new_carry_forward_loss"]),
            payable_amount=float(calc["payable_amount"]),
        )
        self._perf.update_carry_forward(user_id, float(calc["new_carry_forward_loss"]))
        self.db.commit()
        self.db.refresh(bill)
        return bill

    def mark_overdue_bills(self, now: datetime | None = None) -> int:
        """Mark past-due pending performance bills as overdue (IST wall-clock vs stored due_at)."""
        ref = now if now is not None else ist_now_naive()
        return self._perf.mark_overdue_performance_bills(ref)

    def close_month_for_all_broker_users(
        self, year: int, month: int, *, generated_at: datetime | None = None
    ) -> list[MonthlyPerformanceBill]:
        """One performance-fee bill per eligible broker user for the calendar month."""
        created: list[MonthlyPerformanceBill] = []
        for uid in self.iter_broker_trading_user_ids():
            bill = self.generate_bill_for_user_month(uid, year, month, generated_at=generated_at)
            if bill:
                created.append(bill)
        return created
