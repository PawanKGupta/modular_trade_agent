"""Thin Razorpay client wrapper (optional when keys unset)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def verify_webhook_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify X-Razorpay-Signature for raw webhook body."""
    if not secret or not signature:
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


class RazorpayGateway:
    def __init__(self, key_id: str | None, key_secret: str | None):
        self._key_id = key_id
        self._key_secret = key_secret
        self._client: Any = None
        if key_id and key_secret:
            try:
                import razorpay  # noqa: PLC0415

                self._client = razorpay.Client(auth=(key_id, key_secret))
            except Exception as e:  # pragma: no cover - import guard
                logger.warning("Razorpay SDK unavailable: %s", e)

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    @property
    def key_id(self) -> str | None:
        return self._key_id

    def create_customer(self, *, name: str | None, email: str, notes: dict | None = None) -> dict:
        if not self._client:
            raise RuntimeError("Razorpay is not configured")
        payload: dict[str, Any] = {"email": email}
        if name:
            payload["name"] = name
        if notes:
            payload["notes"] = {k: str(v)[:250] for k, v in notes.items()}
        return self._client.customer.create(payload)

    def create_plan(
        self,
        *,
        period: str,
        interval: int,
        item: dict,
        notes: dict | None = None,
    ) -> dict:
        if not self._client:
            raise RuntimeError("Razorpay is not configured")
        payload: dict[str, Any] = {"period": period, "interval": interval, "item": item}
        if notes:
            payload["notes"] = {k: str(v)[:250] for k, v in notes.items()}
        return self._client.plan.create(payload)

    def create_subscription(  # noqa: PLR0913
        self,
        *,
        plan_id: str,
        customer_id: str,
        total_count: int,
        quantity: int = 1,
        customer_notify: int = 1,
        notes: dict | None = None,
        start_at: int | None = None,
        expire_by: int | None = None,
    ) -> dict:
        if not self._client:
            raise RuntimeError("Razorpay is not configured")
        payload: dict[str, Any] = {
            "plan_id": plan_id,
            "customer_id": customer_id,
            "customer_notify": customer_notify,
            "quantity": quantity,
            "total_count": total_count,
        }
        if notes:
            payload["notes"] = {k: str(v)[:250] for k, v in notes.items()}
        if start_at is not None:
            payload["start_at"] = start_at
        if expire_by is not None:
            payload["expire_by"] = expire_by
        return self._client.subscription.create(payload)

    def cancel_subscription(self, subscription_id: str, *, cancel_at_cycle_end: int = 1) -> dict:
        if not self._client:
            raise RuntimeError("Razorpay is not configured")
        return self._client.subscription.cancel(
            subscription_id, {"cancel_at_cycle_end": cancel_at_cycle_end}
        )

    def fetch_payment(self, payment_id: str) -> dict:
        if not self._client:
            raise RuntimeError("Razorpay is not configured")
        return self._client.payment.fetch(payment_id)

    def create_refund(
        self, payment_id: str, *, amount_paise: int | None = None, notes: dict | None = None
    ) -> dict:
        if not self._client:
            raise RuntimeError("Razorpay is not configured")
        data: dict[str, Any] = {}
        if amount_paise is not None:
            data["amount"] = amount_paise
        if notes:
            data["notes"] = {k: str(v)[:250] for k, v in notes.items()}
        return self._client.payment.refund(payment_id, data)

    def fetch_subscription(self, subscription_id: str) -> dict:
        if not self._client:
            raise RuntimeError("Razorpay is not configured")
        return self._client.subscription.fetch(subscription_id)

    def create_order(
        self,
        *,
        amount_paise: int,
        currency: str = "INR",
        receipt: str,
        notes: dict | None = None,
    ) -> dict:
        if not self._client:
            raise RuntimeError("Razorpay is not configured")
        receipt_safe = (receipt or "")[:40]
        payload: dict[str, Any] = {
            "amount": int(amount_paise),
            "currency": currency,
            "receipt": receipt_safe,
        }
        if notes:
            payload["notes"] = {k: str(v)[:250] for k, v in notes.items()}
        return self._client.order.create(payload)


def safe_json_loads(body: bytes) -> dict:
    return json.loads(body.decode("utf-8"))
