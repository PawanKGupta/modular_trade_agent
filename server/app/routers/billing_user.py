# ruff: noqa: B008
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.application.services.billing_checkout_service import (
    BillingCheckoutError,
    BillingCheckoutService,
)
from src.application.services.subscription_entitlement_service import SubscriptionEntitlementService
from src.infrastructure.db.models import Users
from src.infrastructure.persistence.billing_repository import BillingRepository

from ..core.deps import get_current_user, get_db
from ..schemas.billing import (
    EntitlementsOut,
    PlanOut,
    SubscribeRequest,
    SubscribeResponse,
    TransactionOut,
    UserSubscriptionOut,
)

router = APIRouter()


def _plan_out(repo: BillingRepository, p) -> PlanOut:
    eff = repo.effective_amount_paise(p)
    return PlanOut(
        id=p.id,
        slug=p.slug,
        name=p.name,
        description=p.description,
        plan_tier=p.plan_tier.value,
        billing_interval=p.billing_interval.value,
        base_amount_paise=p.base_amount_paise,
        effective_amount_paise=eff,
        currency=p.currency,
        features_json=p.features_json or {},
        razorpay_plan_id=p.razorpay_plan_id,
        is_active=p.is_active,
    )


@router.get("/billing/plans", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)):
    repo = BillingRepository(db)
    return [_plan_out(repo, p) for p in repo.list_active_plans()]


@router.get("/billing/entitlements", response_model=EntitlementsOut)
def get_entitlements(db: Session = Depends(get_db), current: Users = Depends(get_current_user)):
    ent = SubscriptionEntitlementService(db).resolve(current)
    return EntitlementsOut(
        active=ent.active,
        status=ent.status,
        plan_tier=ent.plan_tier.value if ent.plan_tier else None,
        features=ent.features,
        current_period_end=ent.current_period_end,
    )


@router.get("/billing/subscription", response_model=UserSubscriptionOut | None)
def get_my_subscription(db: Session = Depends(get_db), current: Users = Depends(get_current_user)):
    repo = BillingRepository(db)
    subs = repo.list_subscriptions_for_user(current.id)
    if not subs:
        return None
    s = subs[0]
    return UserSubscriptionOut(
        id=s.id,
        plan_id=s.plan_id,
        status=s.status.value,
        billing_provider=s.billing_provider.value,
        started_at=s.started_at,
        current_period_end=s.current_period_end,
        cancel_at_period_end=s.cancel_at_period_end,
        trial_end=s.trial_end,
        pending_plan_id=s.pending_plan_id,
    )


@router.post("/billing/subscribe", response_model=SubscribeResponse)
def subscribe(
    payload: SubscribeRequest,
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
):
    repo = BillingRepository(db)
    plan = repo.get_plan(payload.plan_id)
    if not plan or not plan.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    coupon = repo.get_coupon_by_code(payload.coupon_code) if payload.coupon_code else None
    try:
        data = BillingCheckoutService(db).create_checkout(current, plan, coupon)
    except BillingCheckoutError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return SubscribeResponse(**data)


@router.post("/billing/cancel", response_model=UserSubscriptionOut)
def cancel_subscription(
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
    user_subscription_id: int = Query(..., description="Local user_subscriptions.id"),
):
    try:
        s = BillingCheckoutService(db).cancel_at_period_end(current, user_subscription_id)
    except BillingCheckoutError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return UserSubscriptionOut(
        id=s.id,
        plan_id=s.plan_id,
        status=s.status.value,
        billing_provider=s.billing_provider.value,
        started_at=s.started_at,
        current_period_end=s.current_period_end,
        cancel_at_period_end=s.cancel_at_period_end,
        trial_end=s.trial_end,
        pending_plan_id=s.pending_plan_id,
    )


@router.post("/billing/change-plan", response_model=UserSubscriptionOut)
def change_plan(
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
    user_subscription_id: int = Query(...),
    new_plan_id: int = Query(...),
):
    try:
        s = BillingCheckoutService(db).schedule_plan_change(
            current, user_subscription_id, new_plan_id
        )
    except BillingCheckoutError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return UserSubscriptionOut(
        id=s.id,
        plan_id=s.plan_id,
        status=s.status.value,
        billing_provider=s.billing_provider.value,
        started_at=s.started_at,
        current_period_end=s.current_period_end,
        cancel_at_period_end=s.cancel_at_period_end,
        trial_end=s.trial_end,
        pending_plan_id=s.pending_plan_id,
    )


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
