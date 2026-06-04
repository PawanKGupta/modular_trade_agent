"""Mark performance-fee bills paid (cash / offline admin recording)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.application.services.performance_fee_checkout_service import payable_amount_paise
from src.infrastructure.db.models import (
    BillingTransaction,
    BillingTransactionStatus,
    MonthlyPerformanceBill,
    PerformanceBillStatus,
    Users,
)
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.billing_repository import BillingRepository

logger = logging.getLogger(__name__)

_CASH_IDEMPOTENCY_PREFIX = "perf_bill:cash:"


class PerformanceBillPaymentError(Exception):
    """User-facing validation errors for bill payment recording."""


class PerformanceBillPaymentService:
    def __init__(self, db: Session):
        self.db = db
        self._billing = BillingRepository(db)

    def record_cash_payment(
        self,
        bill_id: int,
        admin: Users,
        *,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Mark a performance bill fully paid and record a captured billing transaction (no Razorpay)."""
        bill = self.db.get(MonthlyPerformanceBill, bill_id)
        if not bill:
            raise PerformanceBillPaymentError("Performance bill not found")

        if bill.status == PerformanceBillStatus.PAID:
            raise PerformanceBillPaymentError("This bill is already paid")

        if bill.status not in (
            PerformanceBillStatus.PENDING_PAYMENT,
            PerformanceBillStatus.OVERDUE,
        ):
            st = bill.status.value if hasattr(bill.status, "value") else str(bill.status)
            raise PerformanceBillPaymentError(f"Bill is not payable (status={st})")

        amount_paise = payable_amount_paise(float(bill.payable_amount or 0))
        if amount_paise <= 0:
            raise PerformanceBillPaymentError("Nothing to pay for this bill")

        idempotency_key = f"{_CASH_IDEMPOTENCY_PREFIX}{bill.id}"
        existing = self.db.execute(
            select(BillingTransaction).where(BillingTransaction.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing:
            raise PerformanceBillPaymentError("Cash payment already recorded for this bill")

        note_clean = (note or "").strip()[:480] or None
        payment_ref = f"cash-bill-{bill.id}-by-admin-{admin.id}"

        bill.status = PerformanceBillStatus.PAID
        bill.paid_at = ist_now()
        bill.razorpay_payment_id = payment_ref

        tx = self._billing.add_transaction(
            user_id=bill.user_id,
            user_subscription_id=None,
            amount_paise=amount_paise,
            currency="INR",
            status=BillingTransactionStatus.CAPTURED,
            razorpay_payment_id=payment_ref,
            razorpay_invoice_id=None,
            failure_reason=f"Cash payment recorded by admin {admin.id}"
            + (f": {note_clean}" if note_clean else ""),
            idempotency_key=idempotency_key,
        )
        self.db.commit()
        self.db.refresh(bill)

        logger.info(
            "Admin %s recorded cash payment for performance bill %s (user %s, %s paise)",
            admin.id,
            bill.id,
            bill.user_id,
            amount_paise,
        )
        return {
            "bill_id": bill.id,
            "user_id": bill.user_id,
            "billing_transaction_id": tx.id,
            "amount_paise": amount_paise,
            "paid_at": bill.paid_at,
        }
