# ruff: noqa: B008
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.application.services.billing_webhook_service import BillingWebhookService
from src.application.services.razorpay_credentials import resolve_razorpay_webhook_secret_from_db
from src.infrastructure.payments.razorpay_gateway import safe_json_loads, verify_webhook_signature
from src.infrastructure.persistence.billing_repository import BillingRepository

from ..core.deps import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    sig = request.headers.get("X-Razorpay-Signature") or ""
    secret = resolve_razorpay_webhook_secret_from_db(db) or ""
    if not secret or not verify_webhook_signature(body, sig, secret):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    try:
        payload = safe_json_loads(body)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON"
        ) from None

    event_id = str(payload.get("id") or "")
    if not event_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing event id")

    repo = BillingRepository(db)
    if repo.webhook_event_seen(event_id):
        return {"ok": True, "deduped": True}

    try:
        BillingWebhookService(db).process_payload(payload)
        repo.record_webhook_event(event_id, str(payload.get("event") or ""))
    except Exception:
        logger.exception("Webhook processing failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook failed"
        ) from None

    return {"ok": True}
