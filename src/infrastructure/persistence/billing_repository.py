"""Persistence helpers for billing (admin settings, webhooks, transactions, refunds)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.infrastructure.db.models import (
    BillingAdminSettings,
    BillingRefund,
    BillingTransaction,
    BillingTransactionStatus,
    RazorpayWebhookEvent,
)


class BillingRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Admin settings singleton ---
    def get_admin_settings(self) -> BillingAdminSettings:
        row = self.db.query(BillingAdminSettings).filter(BillingAdminSettings.id == 1).first()
        if row:
            return row
        row = BillingAdminSettings(id=1)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_admin_settings(self, **kwargs: Any) -> BillingAdminSettings:
        s = self.get_admin_settings()
        for k, v in kwargs.items():
            if hasattr(s, k) and v is not None:
                setattr(s, k, v)
        self.db.commit()
        self.db.refresh(s)
        return s

    # --- Webhook idempotency ---
    def webhook_event_seen(self, event_id: str) -> bool:
        return (
            self.db.query(RazorpayWebhookEvent)
            .filter(RazorpayWebhookEvent.event_id == event_id)
            .first()
            is not None
        )

    def record_webhook_event(self, event_id: str, event_type: str) -> None:
        self.db.add(RazorpayWebhookEvent(event_id=event_id, event_type=event_type))
        self.db.commit()

    # --- Transactions ---
    def add_transaction(  # noqa: PLR0913
        self,
        *,
        user_id: int,
        user_subscription_id: int | None,
        amount_paise: int,
        currency: str,
        status: BillingTransactionStatus,
        razorpay_payment_id: str | None = None,
        razorpay_invoice_id: str | None = None,
        failure_reason: str | None = None,
        idempotency_key: str | None = None,
    ) -> BillingTransaction:
        tx = BillingTransaction(
            user_id=user_id,
            user_subscription_id=user_subscription_id,
            amount_paise=amount_paise,
            currency=currency,
            status=status,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_invoice_id=razorpay_invoice_id,
            failure_reason=failure_reason,
            idempotency_key=idempotency_key,
        )
        self.db.add(tx)
        self.db.commit()
        self.db.refresh(tx)
        return tx

    def list_transactions(
        self,
        *,
        user_id: int | None = None,
        failed_only: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> list[BillingTransaction]:
        q = self.db.query(BillingTransaction).order_by(BillingTransaction.id.desc())
        if user_id is not None:
            q = q.filter(BillingTransaction.user_id == user_id)
        if failed_only:
            q = q.filter(BillingTransaction.status == BillingTransactionStatus.FAILED)
        return q.limit(limit).offset(offset).all()

    # --- Refunds ---
    def add_refund(  # noqa: PLR0913
        self,
        *,
        billing_transaction_id: int,
        amount_paise: int,
        status: str,
        razorpay_refund_id: str | None,
        reason: str | None,
        created_by_user_id: int | None,
    ) -> BillingRefund:
        r = BillingRefund(
            billing_transaction_id=billing_transaction_id,
            amount_paise=amount_paise,
            status=status,
            razorpay_refund_id=razorpay_refund_id,
            reason=reason,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(r)
        self.db.commit()
        self.db.refresh(r)
        return r
