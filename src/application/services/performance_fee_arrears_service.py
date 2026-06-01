"""Soft enforcement: unpaid performance-fee invoices past due block new broker buys only.

Sell monitoring, sell placement, and exit logic do not use this service — users can always
close existing positions when a fee is overdue.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from src.infrastructure.db.models import UserRole, Users
from src.infrastructure.db.timezone_utils import ist_now_naive
from src.infrastructure.persistence.performance_billing_repository import (
    PerformanceBillingRepository,
)


@dataclass(frozen=True)
class PerformanceFeeArrearsStatus:
    """Whether automated / policy should skip new broker long entries."""

    blocks_new_broker_buys: bool
    message: str | None
    bills: list[dict[str, Any]]


class PerformanceFeeArrearsService:
    def __init__(self, db: Session):
        self._db = db
        self._repo = PerformanceBillingRepository(db)

    def status_for_user(
        self, user: Users, *, now: datetime | None = None
    ) -> PerformanceFeeArrearsStatus:
        if user.role == UserRole.ADMIN:
            return PerformanceFeeArrearsStatus(False, None, [])
        ref = now if now is not None else ist_now_naive()
        rows = self._repo.list_unpaid_performance_bills_past_due(user.id, ref)
        if not rows:
            return PerformanceFeeArrearsStatus(False, None, [])
        first = rows[0]
        bm = (
            first.bill_month.isoformat()
            if hasattr(first.bill_month, "isoformat")
            else str(first.bill_month)
        )
        msg = (
            f"Unpaid broker performance fee (invoice {bm}, due passed). "
            "New buys and re-entries are paused until you pay from Billing. "
            "Sell orders still run so you can exit open positions."
        )
        bills_out: list[dict[str, Any]] = []
        for b in rows[:24]:
            st = b.status.value if hasattr(b.status, "value") else str(b.status)
            due = b.due_at.isoformat() if hasattr(b.due_at, "isoformat") else str(b.due_at)
            bm_s = (
                b.bill_month.isoformat()
                if hasattr(b.bill_month, "isoformat")
                else str(b.bill_month)
            )
            bills_out.append(
                {
                    "id": b.id,
                    "bill_month": bm_s,
                    "due_at": due,
                    "payable_amount": float(b.payable_amount or 0),
                    "status": st,
                }
            )
        return PerformanceFeeArrearsStatus(True, msg, bills_out)

    def blocks_new_broker_buys(self, user: Users, *, now: datetime | None = None) -> bool:
        return self.status_for_user(user, now=now).blocks_new_broker_buys
