"""Process Razorpay webhooks into local billing state."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from src.application.services.subscription_entitlement_service import default_features_for_tier
from src.infrastructure.db.models import (
    BillingTransactionStatus,
    SubscriptionPlan,
    UserSubscription,
    UserSubscriptionStatus,
)
from src.infrastructure.persistence.billing_repository import BillingRepository

logger = logging.getLogger(__name__)


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        # Razorpay unix timestamp
        if isinstance(value, (int, float)):
            return datetime.utcfromtimestamp(int(value))
        if isinstance(value, str) and value.isdigit():
            return datetime.utcfromtimestamp(int(value))
    except (ValueError, OSError):
        return None
    return None


class BillingWebhookService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = BillingRepository(db)

    def process_payload(self, payload: dict) -> None:
        event = payload.get("event") or payload.get("type")
        entity = payload.get("payload", {})
        if not event:
            return

        if event.startswith("subscription."):
            self._handle_subscription_event(event, entity)
        elif event.startswith("payment.") or event == "invoice.paid":
            self._handle_payment_event(event, entity)

    def _find_local_subscription(self, rz_sub: dict) -> UserSubscription | None:
        rid = rz_sub.get("id")
        if rid:
            row = (
                self.db.query(UserSubscription)
                .filter(UserSubscription.razorpay_subscription_id == rid)
                .first()
            )
            if row:
                return row
        notes = rz_sub.get("notes") or {}
        raw = notes.get("app_user_subscription_id")
        if raw and str(raw).isdigit():
            return self.db.get(UserSubscription, int(raw))
        return None

    def _handle_subscription_event(self, event: str, entity: dict) -> None:
        sub_payload = entity.get("subscription", entity)
        if isinstance(sub_payload, dict) and "entity" in sub_payload:
            sub_payload = sub_payload.get("entity") or sub_payload
        if not isinstance(sub_payload, dict):
            return
        local = self._find_local_subscription(sub_payload)
        if not local:
            logger.info("Webhook subscription: no local row for %s", sub_payload.get("id"))
            return

        status = (sub_payload.get("status") or "").lower()
        current_start = _parse_ts(sub_payload.get("current_start"))
        current_end = _parse_ts(sub_payload.get("current_end"))

        if event in (
            "subscription.authenticated",
            "subscription.activated",
            "subscription.resumed",
        ):
            local.status = UserSubscriptionStatus.ACTIVE
            if current_start:
                local.started_at = current_start
            if current_end:
                local.current_period_end = current_end
        elif event == "subscription.charged":
            local.status = UserSubscriptionStatus.ACTIVE
            if current_end:
                local.current_period_end = current_end
        elif event in ("subscription.pending",):
            local.status = UserSubscriptionStatus.PENDING
        elif event in ("subscription.halted", "subscription.cancelled", "subscription.completed"):
            if local.cancel_at_period_end and event == "subscription.cancelled":
                local.status = UserSubscriptionStatus.CANCELLED
            elif event == "subscription.completed":
                local.status = UserSubscriptionStatus.EXPIRED
            else:
                local.status = UserSubscriptionStatus.SUSPENDED
        elif event == "subscription.paused":
            local.status = UserSubscriptionStatus.SUSPENDED

        self.db.commit()

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

        local_sub: UserSubscription | None = None
        sub_id = pay.get("subscription_id")
        if sub_id:
            local_sub = (
                self.db.query(UserSubscription)
                .filter(UserSubscription.razorpay_subscription_id == sub_id)
                .first()
            )

        user_id = local_sub.user_id if local_sub else None
        if user_id is None:
            notes = pay.get("notes") or {}
            uid = notes.get("user_id")
            if uid and str(uid).isdigit():
                user_id = int(uid)

        if user_id is None:
            logger.info("Payment webhook without resolvable user: %s", pid)
            return

        if status == "captured":
            self.repo.add_transaction(
                user_id=user_id,
                user_subscription_id=local_sub.id if local_sub else None,
                amount_paise=amount,
                currency=pay.get("currency") or "INR",
                status=BillingTransactionStatus.CAPTURED,
                razorpay_payment_id=pid,
                razorpay_invoice_id=invoice_id,
                idempotency_key=f"pay:{pid}" if pid else None,
            )
            if local_sub and local_sub.status == UserSubscriptionStatus.PENDING:
                local_sub.status = UserSubscriptionStatus.ACTIVE
                self.db.commit()
        elif status in ("failed",):
            self.repo.add_transaction(
                user_id=user_id,
                user_subscription_id=local_sub.id if local_sub else None,
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
            if local_sub:
                admin = self.repo.get_admin_settings()
                local_sub.status = UserSubscriptionStatus.PAST_DUE
                local_sub.grace_until = datetime.utcnow() + timedelta(
                    days=int(admin.grace_period_days or 0)
                )
                self.db.commit()


def apply_pending_plan_change(db: Session, local: UserSubscription) -> None:
    """If pending_plan_id set at renewal boundary, swap plan and refresh snapshots."""
    if not local.pending_plan_id:
        return
    plan = db.get(SubscriptionPlan, local.pending_plan_id)
    if not plan:
        return
    local.plan_id = plan.id
    local.plan_tier_snapshot = plan.plan_tier
    local.features_snapshot = plan.features_json or default_features_for_tier(plan.plan_tier)
    local.pending_plan_id = None
    db.commit()
