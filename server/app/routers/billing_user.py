# ruff: noqa: B008
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from server.app.core.crypto import encryption_uses_dedicated_env_key
from src.application.services.performance_fee_arrears_service import PerformanceFeeArrearsService
from src.application.services.performance_fee_checkout_service import (
    PerformanceFeeCheckoutError,
    PerformanceFeeCheckoutService,
)
from src.application.services.razorpay_credentials import (
    get_razorpay_gateway,
    razorpay_admin_meta,
    resolve_razorpay_key_id,
    resolve_razorpay_key_secret,
)
from src.infrastructure.db.models import MonthlyPerformanceBill, Users
from src.infrastructure.payments.razorpay_gateway import verify_checkout_payment_signature
from src.infrastructure.persistence.billing_repository import BillingRepository
from src.infrastructure.persistence.performance_billing_repository import (
    PerformanceBillingRepository,
)

from ..core.deps import get_current_user, get_db
from ..schemas.billing import (
    PerformanceBillOut,
    PerformanceFeeArrearBillOut,
    PerformanceFeeArrearsOut,
    PerformanceFeeCheckoutResponse,
    RazorpayCreateOrderRequest,
    RazorpayCreateOrderResponse,
    RazorpayVerifyPaymentRequest,
    RazorpayVerifyPaymentResponse,
    TransactionOut,
)

logger = logging.getLogger(__name__)

# Guardrails for generic test / Playground orders (not performance-fee invoices).
_MAX_GENERIC_ORDER_PAISE = 10_000_00  # ₹1,00,000

router = APIRouter()


@router.get("/billing/performance-fee-arrears", response_model=PerformanceFeeArrearsOut)
def performance_fee_arrears(
    db: Session = Depends(get_db), current: Users = Depends(get_current_user)
):
    st = PerformanceFeeArrearsService(db).status_for_user(current)
    return PerformanceFeeArrearsOut(
        blocks_new_broker_buys=st.blocks_new_broker_buys,
        message=st.message,
        bills=[PerformanceFeeArrearBillOut(**b) for b in st.bills],
    )


def _performance_bill_out(b: MonthlyPerformanceBill) -> PerformanceBillOut:
    st = b.status.value if hasattr(b.status, "value") else str(b.status)
    return PerformanceBillOut(
        id=b.id,
        bill_month=b.bill_month,
        generated_at=b.generated_at,
        due_at=b.due_at,
        status=st,
        payable_amount=float(b.payable_amount),
        fee_amount=float(b.fee_amount),
        chargeable_profit=float(b.chargeable_profit),
        current_month_pnl=float(b.current_month_pnl),
        previous_carry_forward_loss=float(b.previous_carry_forward_loss),
        new_carry_forward_loss=float(b.new_carry_forward_loss),
        fee_percentage=float(b.fee_percentage),
        paid_at=b.paid_at,
        razorpay_order_id=b.razorpay_order_id,
    )


@router.get("/billing/performance-bills", response_model=list[PerformanceBillOut])
def list_performance_bills(
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
    limit: int = Query(36, ge=1, le=120),
):
    rows = PerformanceBillingRepository(db).list_bills_for_user(current.id, limit=limit)
    return [_performance_bill_out(b) for b in rows]


@router.post(
    "/billing/performance-bills/{bill_id}/checkout",
    response_model=PerformanceFeeCheckoutResponse,
)
def checkout_performance_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
):
    try:
        data = PerformanceFeeCheckoutService(db).create_order_for_bill(current, bill_id)
    except PerformanceFeeCheckoutError as e:
        msg = str(e)
        code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if "not configured" in msg.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=msg) from e
    return PerformanceFeeCheckoutResponse(**data)


@router.post("/billing/razorpay/create-order", response_model=RazorpayCreateOrderResponse)
def razorpay_create_order(
    body: RazorpayCreateOrderRequest,
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
):
    """
    Create a generic Razorpay order (Standard Checkout step 1).
    For performance-fee payments prefer ``POST .../performance-bills/{id}/checkout``.
    """
    if body.amount_paise > _MAX_GENERIC_ORDER_PAISE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount too large for this endpoint",
        )
    admin = BillingRepository(db).get_admin_settings()
    key_id = resolve_razorpay_key_id(admin)
    key_secret = resolve_razorpay_key_secret(admin)
    gw = get_razorpay_gateway(db)
    if not key_id or not key_secret:
        meta = razorpay_admin_meta(admin)
        meta["db_secret_encryption_ready"] = encryption_uses_dedicated_env_key()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "Razorpay API keys not configured", "meta": meta},
        )
    receipt = (body.receipt or f"G{current.id}T{int(time.time())}")[:40]
    try:
        order = gw.create_order(
            amount_paise=body.amount_paise,
            currency=body.currency or "INR",
            receipt=receipt,
            notes={"user_id": str(current.id), "type": "generic_checkout"},
        )
    except Exception as e:
        logger.exception("Razorpay create_order failed")
        err = str(e).lower()
        if "authentication" in err or "unauthorized" in err or "access denied" in err:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Razorpay rejected API credentials",
            ) from e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Razorpay order creation failed",
        ) from e
    oid = order.get("id")
    if not oid:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Razorpay did not return an order id",
        )
    return RazorpayCreateOrderResponse(
        order_id=str(oid),
        amount=int(order.get("amount") or body.amount_paise),
        currency=str(order.get("currency") or body.currency or "INR"),
        key_id=key_id,
    )


@router.post("/billing/razorpay/verify-payment", response_model=RazorpayVerifyPaymentResponse)
def razorpay_verify_payment(
    body: RazorpayVerifyPaymentRequest,
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
):
    """
    Standard Checkout step 3: verify ``razorpay_signature`` (HMAC of order_id|payment_id).
    If ``performance_bill_id`` is set, the order id must match that bill for the current user.
    This does not replace webhooks; it confirms the client callback before you rely on it in UI.
    """
    o = (body.razorpay_order_id or "").strip()
    p = (body.razorpay_payment_id or "").strip()
    s = (body.razorpay_signature or "").strip()
    if not o or not p or not s:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing order id, payment id, or signature",
        )
    admin = BillingRepository(db).get_admin_settings()
    key_secret = resolve_razorpay_key_secret(admin)
    if not key_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Razorpay API secret not configured",
        )

    if body.performance_bill_id is not None:
        bill = PerformanceBillingRepository(db).get_bill_owned_by_user(
            body.performance_bill_id, current.id
        )
        if not bill or not (bill.razorpay_order_id and str(bill.razorpay_order_id) == o):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order id does not match this performance bill",
            )

    if not verify_checkout_payment_signature(o, p, s, key_secret=key_secret):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment signature",
        )
    return RazorpayVerifyPaymentResponse(verified=True, detail="Signature valid")


@router.get("/billing/transactions", response_model=list[TransactionOut])
def my_transactions(
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
    limit: int = 100,
):
    repo = BillingRepository(db)
    rows = repo.list_transactions(user_id=current.id, limit=limit)
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
