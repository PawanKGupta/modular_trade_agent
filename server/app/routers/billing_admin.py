# ruff: noqa: B008, PLR0911
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from server.app.core.crypto import (
    MissingDedicatedEncryptionKeyError,
    assert_db_secret_encryption_allowed,
    encrypt_blob,
)
from src.application.services.billing_reconciliation_service import BillingReconciliationService
from src.application.services.razorpay_credentials import get_razorpay_gateway, razorpay_admin_meta
from src.infrastructure.db.models import BillingTransaction, BillingTransactionStatus, Users
from src.infrastructure.persistence.billing_repository import BillingRepository

from ..core.deps import get_db, require_admin
from ..schemas.billing import (
    AdminBillingSettingsUpdate,
    AdminRazorpayCredentialsPatch,
    AdminRefundRequest,
    TransactionOut,
)

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/billing/settings")
def get_billing_settings(db: Session = Depends(get_db)):
    s = BillingRepository(db).get_admin_settings()
    rz = razorpay_admin_meta(s)
    return {
        "payment_card_enabled": s.payment_card_enabled,
        "payment_upi_enabled": s.payment_upi_enabled,
        "performance_fee_payment_days_after_invoice": s.performance_fee_payment_days_after_invoice,
        "performance_fee_default_percentage": float(s.performance_fee_default_percentage),
        **rz,
    }


@router.patch("/billing/settings")
def patch_billing_settings(
    payload: AdminBillingSettingsUpdate,
    db: Session = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    s = BillingRepository(db).update_admin_settings(**data)
    return {
        "payment_card_enabled": s.payment_card_enabled,
        "payment_upi_enabled": s.payment_upi_enabled,
        "performance_fee_payment_days_after_invoice": s.performance_fee_payment_days_after_invoice,
        "performance_fee_default_percentage": float(s.performance_fee_default_percentage),
        **razorpay_admin_meta(s),
    }


@router.patch("/billing/razorpay-credentials")
def patch_razorpay_credentials(
    payload: AdminRazorpayCredentialsPatch,
    db: Session = Depends(get_db),
):
    """Store Razorpay key id (plain) and encrypt API + webhook secrets (needs Fernet env key)."""
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    repo = BillingRepository(db)
    s = repo.get_admin_settings()
    try:
        if "razorpay_key_id" in data:
            rid = data["razorpay_key_id"]
            s.razorpay_key_id = (rid or "").strip() or None
        if "razorpay_key_secret" in data:
            val = data["razorpay_key_secret"]
            if val is None or val == "":
                s.razorpay_key_secret_encrypted = None
            else:
                assert_db_secret_encryption_allowed()
                s.razorpay_key_secret_encrypted = encrypt_blob(str(val).encode("utf-8"))
        if "razorpay_webhook_secret" in data:
            val = data["razorpay_webhook_secret"]
            if val is None or val == "":
                s.razorpay_webhook_secret_encrypted = None
            else:
                assert_db_secret_encryption_allowed()
                s.razorpay_webhook_secret_encrypted = encrypt_blob(str(val).encode("utf-8"))
    except MissingDedicatedEncryptionKeyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    db.refresh(s)
    return {"ok": True, **razorpay_admin_meta(s)}


@router.get("/billing/transactions", response_model=list[TransactionOut])
def admin_transactions(
    db: Session = Depends(get_db),
    user_id: int | None = None,
    failed_only: bool = False,
    limit: int = 500,
):
    rows = BillingRepository(db).list_transactions(
        user_id=user_id, failed_only=failed_only, limit=limit
    )
    return [
        TransactionOut(
            id=t.id,
            user_id=t.user_id,
            user_subscription_id=t.user_subscription_id,
            amount_paise=t.amount_paise,
            currency=t.currency,
            status=t.status.value,
            razorpay_payment_id=t.razorpay_payment_id,
            failure_reason=t.failure_reason,
            created_at=t.created_at,
        )
        for t in rows
    ]


@router.post("/billing/refunds")
def admin_refund(
    payload: AdminRefundRequest,
    db: Session = Depends(get_db),
    admin: Users = Depends(require_admin),
):
    repo = BillingRepository(db)
    tx = db.get(BillingTransaction, payload.billing_transaction_id)
    if not tx or not tx.razorpay_payment_id:
        raise HTTPException(status_code=404, detail="Transaction not refundable")
    gw = get_razorpay_gateway(db)
    if not gw.is_configured:
        raise HTTPException(status_code=400, detail="Razorpay not configured")
    try:
        ref = gw.create_refund(
            tx.razorpay_payment_id,
            amount_paise=payload.amount_paise,
            notes={"reason": (payload.reason or "")[:200]},
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    repo.add_refund(
        billing_transaction_id=tx.id,
        amount_paise=payload.amount_paise or tx.amount_paise,
        status=str(ref.get("status") or "created"),
        razorpay_refund_id=ref.get("id"),
        reason=payload.reason,
        created_by_user_id=admin.id,
    )
    tx.status = BillingTransactionStatus.REFUNDED
    db.commit()
    return {"ok": True, "razorpay": ref}


@router.post("/billing/reconcile")
def run_reconcile(db: Session = Depends(get_db)):
    return BillingReconciliationService(db).run()
