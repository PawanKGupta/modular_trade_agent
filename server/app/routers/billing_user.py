# ruff: noqa: B008
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.application.services.performance_fee_checkout_service import (
    PerformanceFeeCheckoutError,
    PerformanceFeeCheckoutService,
)
from src.infrastructure.db.models import MonthlyPerformanceBill, Users
from src.infrastructure.persistence.billing_repository import BillingRepository
from src.infrastructure.persistence.performance_billing_repository import (
    PerformanceBillingRepository,
)

from ..core.deps import get_current_user, get_db
from ..schemas.billing import PerformanceBillOut, PerformanceFeeCheckoutResponse, TransactionOut

router = APIRouter()


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
