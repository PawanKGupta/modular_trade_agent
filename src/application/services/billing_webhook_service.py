"""Process Razorpay webhooks: performance-fee orders and generic payment records."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from services.email_notifier import EmailNotifier
from services.notification_preference_service import (
    NotificationEventType,
    NotificationPreferenceService,
)
from src.application.services.performance_fee_checkout_service import payable_amount_paise
from src.infrastructure.db.models import (
    BillingTransactionStatus,
    MonthlyPerformanceBill,
    PerformanceBillStatus,
    Users,
)
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.billing_repository import BillingRepository

logger = logging.getLogger(__name__)


def _send_billing_email_if_allowed(
    db: Session,
    *,
    user_id: int,
    event_type: str,
    subject: str,
    body: str,
) -> None:
    """Best-effort billing email respecting user notification preferences."""
    user = db.get(Users, user_id)
    if not user:
        return
    pref_svc = NotificationPreferenceService(db)
    if not pref_svc.should_notify(user_id, event_type, channel="email"):
        return
    prefs = pref_svc.get_preferences(user_id)
    email_to = (prefs.email_address if prefs else None) or user.email
    notifier = EmailNotifier()
    if notifier.is_available() and email_to:
        notifier.send_email(email_to, subject, body)


class BillingWebhookService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = BillingRepository(db)

    def process_payload(self, payload: dict) -> None:
        event = payload.get("event") or payload.get("type")
        entity = payload.get("payload", {})
        if not event:
            return

        if event.startswith("payment.") or event == "invoice.paid":
            self._handle_payment_event(event, entity)

    def _try_capture_performance_bill_payment(  # noqa: PLR0911
        self,
        pay: dict,
        *,
        status: str,
        amount: int,
        pid: str | None,
        invoice_id: str | None,
    ) -> bool:
        """Match Razorpay notes to a performance bill; mark paid and record a transaction."""
        notes = pay.get("notes") or {}
        raw = notes.get("performance_bill_id")
        if raw is None or not str(raw).isdigit():
            return False
        bill = self.db.get(MonthlyPerformanceBill, int(str(raw)))
        if not bill:
            logger.info("Performance bill webhook: unknown bill id %s", raw)
            return True
        uid_note = notes.get("user_id")
        if uid_note is None or not str(uid_note).isdigit() or int(str(uid_note)) != bill.user_id:
            logger.warning(
                "Performance bill %s payment user mismatch (note=%s bill.user_id=%s)",
                bill.id,
                uid_note,
                bill.user_id,
            )
            return True
        if status != "captured":
            return True
        expected = payable_amount_paise(float(bill.payable_amount or 0))
        if expected <= 0 or amount != expected:
            logger.warning(
                "Performance bill %s amount mismatch: rz=%s expected_paise=%s",
                bill.id,
                amount,
                expected,
            )
            return True
        if bill.status == PerformanceBillStatus.PAID:
            logger.info("Performance bill %s already paid; ignoring duplicate webhook", bill.id)
            return True
        if bill.status not in (
            PerformanceBillStatus.PENDING_PAYMENT,
            PerformanceBillStatus.OVERDUE,
        ):
            st = bill.status.value if hasattr(bill.status, "value") else str(bill.status)
            logger.info("Performance bill %s not payable (status=%s)", bill.id, st)
            return True

        bill.status = PerformanceBillStatus.PAID
        bill.paid_at = ist_now()
        if pid:
            bill.razorpay_payment_id = str(pid)
        self.repo.add_transaction(
            user_id=bill.user_id,
            user_subscription_id=None,
            amount_paise=amount,
            currency=pay.get("currency") or "INR",
            status=BillingTransactionStatus.CAPTURED,
            razorpay_payment_id=str(pid) if pid else None,
            razorpay_invoice_id=invoice_id,
            idempotency_key=f"perf_bill:{bill.id}:{pid}" if pid else None,
        )
        return True

    def _handle_payment_event(self, event: str, entity: dict) -> None:
        pay = entity.get("payment", entity.get("invoice", {}))
        if isinstance(pay, dict) and "entity" in pay:
            pay = pay.get("entity") or pay
        if not isinstance(pay, dict):
            return
        pid = pay.get("id")
        status = (pay.get("status") or "").lower()
        amount = int(pay.get("amount") or 0)
        invoice_id = pay.get("invoice_id")

        if self._try_capture_performance_bill_payment(
            pay, status=status, amount=amount, pid=str(pid) if pid else None, invoice_id=invoice_id
        ):
            return

        notes = pay.get("notes") or {}
        uid = notes.get("user_id")
        if uid is None or not str(uid).isdigit():
            logger.info("Payment webhook without user_id in notes: %s", pid)
            return
        user_id = int(str(uid))

        if status == "captured":
            self.repo.add_transaction(
                user_id=user_id,
                user_subscription_id=None,
                amount_paise=amount,
                currency=pay.get("currency") or "INR",
                status=BillingTransactionStatus.CAPTURED,
                razorpay_payment_id=pid,
                razorpay_invoice_id=invoice_id,
                idempotency_key=f"pay:{pid}" if pid else None,
            )
        elif status in ("failed",):
            self.repo.add_transaction(
                user_id=user_id,
                user_subscription_id=None,
                amount_paise=amount,
                currency=pay.get("currency") or "INR",
                status=BillingTransactionStatus.FAILED,
                razorpay_payment_id=pid,
                razorpay_invoice_id=invoice_id,
                failure_reason=str(
                    pay.get("error_description") or pay.get("error_code") or "failed"
                ),
                idempotency_key=f"payfail:{pid}" if pid else None,
            )
            reason = str(pay.get("error_description") or pay.get("error_code") or "Payment failed")
            _send_billing_email_if_allowed(
                self.db,
                user_id=user_id,
                event_type=NotificationEventType.PAYMENT_FAILED,
                subject="Payment failed",
                body=(
                    "We could not complete a billing payment.\n\n"
                    f"Reason: {reason}\n\n"
                    "Open Billing in the app to review or retry if a payment is due."
                ),
            )
