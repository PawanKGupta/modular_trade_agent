"""Razorpay order checkout for monthly performance-fee bills."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.application.services.razorpay_credentials import get_razorpay_gateway
from src.infrastructure.db.models import PerformanceBillStatus, Users
from src.infrastructure.persistence.performance_billing_repository import (
    PerformanceBillingRepository,
)


class PerformanceFeeCheckoutError(Exception):
    """User-facing checkout validation errors."""


def payable_amount_paise(payable_rupees: float) -> int:
    """Convert bill payable (INR) to integer paise for Razorpay."""
    d = Decimal(str(payable_rupees)) * 100
    return max(0, int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


class PerformanceFeeCheckoutService:
    def __init__(self, db: Session):
        self.db = db
        self._repo = PerformanceBillingRepository(db)

    def create_order_for_bill(self, user: Users, bill_id: int) -> dict[str, Any]:
        bill = self._repo.get_bill_owned_by_user(bill_id, user.id)
        if not bill:
            raise PerformanceFeeCheckoutError("Bill not found")
        if bill.status not in (
            PerformanceBillStatus.PENDING_PAYMENT,
            PerformanceBillStatus.OVERDUE,
        ):
            raise PerformanceFeeCheckoutError("This bill is not awaiting payment")
        amount_paise = payable_amount_paise(float(bill.payable_amount or 0))
        if amount_paise <= 0:
            raise PerformanceFeeCheckoutError("Nothing to pay for this bill")

        gw = get_razorpay_gateway(self.db)
        if not gw.is_configured:
            raise PerformanceFeeCheckoutError("Online payments are not configured")

        receipt = f"P{bill.id}"[:40]
        notes = {
            "user_id": str(user.id),
            "performance_bill_id": str(bill.id),
        }
        try:
            order = gw.create_order(
                amount_paise=amount_paise,
                currency="INR",
                receipt=receipt,
                notes=notes,
            )
        except Exception as e:
            raise PerformanceFeeCheckoutError(str(e)) from e

        oid = order.get("id") if isinstance(order, dict) else None
        if not oid:
            raise PerformanceFeeCheckoutError("Razorpay did not return an order id")

        bill.razorpay_order_id = str(oid)
        self.db.commit()
        self.db.refresh(bill)

        key_id = gw.key_id or ""
        return {
            "razorpay_key_id": key_id,
            "order_id": str(oid),
            "amount_paise": amount_paise,
            "currency": "INR",
            "bill_id": bill.id,
        }
