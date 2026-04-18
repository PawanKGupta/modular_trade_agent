"""Persistence for broker performance-fee invoices and carry-forward state."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.infrastructure.db.models import (
    MonthlyPerformanceBill,
    PerformanceBillStatus,
    UserPerformanceBillingState,
)
from src.infrastructure.db.timezone_utils import ist_now


class PerformanceBillingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_state(self, user_id: int) -> UserPerformanceBillingState | None:
        return self.db.get(UserPerformanceBillingState, user_id)

    def get_or_create_state(self, user_id: int) -> UserPerformanceBillingState:
        row = self.get_state(user_id)
        if row:
            return row
        row = UserPerformanceBillingState(
            user_id=user_id,
            carry_forward_loss=0.0,
            updated_at=ist_now(),
        )
        self.db.add(row)
        self.db.flush()
        return row

    def update_carry_forward(self, user_id: int, new_carry: float) -> None:
        st = self.get_or_create_state(user_id)
        st.carry_forward_loss = new_carry
        st.updated_at = ist_now()

    def get_bill_for_month(self, user_id: int, bill_month: date) -> MonthlyPerformanceBill | None:
        return self.db.execute(
            select(MonthlyPerformanceBill).where(
                MonthlyPerformanceBill.user_id == user_id,
                MonthlyPerformanceBill.bill_month == bill_month,
            )
        ).scalar_one_or_none()

    def create_bill(  # noqa: PLR0913
        self,
        *,
        user_id: int,
        bill_month: date,
        generated_at: datetime,
        due_at: datetime,
        previous_carry_forward_loss: float,
        current_month_pnl: float,
        fee_percentage: float,
        chargeable_profit: float,
        fee_amount: float,
        new_carry_forward_loss: float,
        payable_amount: float,
        status: PerformanceBillStatus = PerformanceBillStatus.PENDING_PAYMENT,
    ) -> MonthlyPerformanceBill:
        row = MonthlyPerformanceBill(
            user_id=user_id,
            bill_month=bill_month,
            generated_at=generated_at,
            due_at=due_at,
            previous_carry_forward_loss=previous_carry_forward_loss,
            current_month_pnl=current_month_pnl,
            fee_percentage=fee_percentage,
            chargeable_profit=chargeable_profit,
            fee_amount=fee_amount,
            new_carry_forward_loss=new_carry_forward_loss,
            payable_amount=payable_amount,
            status=status,
        )
        self.db.add(row)
        self.db.flush()
        self.db.refresh(row)
        return row

    def list_bills_for_user(self, user_id: int, *, limit: int = 36) -> list[MonthlyPerformanceBill]:
        stmt = (
            select(MonthlyPerformanceBill)
            .where(MonthlyPerformanceBill.user_id == user_id)
            .order_by(MonthlyPerformanceBill.bill_month.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_bill_owned_by_user(self, bill_id: int, user_id: int) -> MonthlyPerformanceBill | None:
        return self.db.execute(
            select(MonthlyPerformanceBill).where(
                MonthlyPerformanceBill.id == bill_id,
                MonthlyPerformanceBill.user_id == user_id,
            )
        ).scalar_one_or_none()

    def mark_overdue_performance_bills(self, now_naive_ist: datetime) -> int:
        """Set status to overdue when due date has passed and bill is still unpaid."""
        stmt = (
            update(MonthlyPerformanceBill)
            .where(
                MonthlyPerformanceBill.status == PerformanceBillStatus.PENDING_PAYMENT,
                MonthlyPerformanceBill.due_at < now_naive_ist,
            )
            .values(status=PerformanceBillStatus.OVERDUE)
        )
        res = self.db.execute(stmt)
        n = int(res.rowcount or 0)
        if n:
            self.db.commit()
        return n
