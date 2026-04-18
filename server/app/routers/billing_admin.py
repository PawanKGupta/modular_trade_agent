# ruff: noqa: B008, PLR0911
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from server.app.core.crypto import (
    MissingDedicatedEncryptionKeyError,
    assert_db_secret_encryption_allowed,
    encrypt_blob,
)
from src.application.services.billing_reconciliation_service import BillingReconciliationService
from src.application.services.razorpay_credentials import get_razorpay_gateway, razorpay_admin_meta
from src.application.services.subscription_entitlement_service import default_features_for_tier
from src.infrastructure.db.models import (
    BillingInterval,
    BillingProvider,
    BillingTransaction,
    BillingTransactionStatus,
    Coupon,
    CouponDiscountType,
    PlanPriceSchedule,
    PlanPriceScheduleStatus,
    PlanTier,
    SubscriptionPlan,
    Users,
    UserSubscription,
    UserSubscriptionStatus,
)
from src.infrastructure.payments.razorpay_gateway import RazorpayGateway
from src.infrastructure.persistence.billing_repository import BillingRepository

from ..core.deps import get_db, require_admin
from ..schemas.billing import (
    AdminBillingSettingsUpdate,
    AdminCouponCreate,
    AdminManualSubscription,
    AdminPlanCreate,
    AdminPlanUpdate,
    AdminPriceScheduleCreate,
    AdminRazorpayCredentialsPatch,
    AdminRefundRequest,
    BillingReportsOut,
    PlanOut,
    TransactionOut,
    UserSubscriptionOut,
)

router = APIRouter(dependencies=[Depends(require_admin)])


def _user_subscription_out(
    s: UserSubscription,
    *,
    user: Users | None = None,
    plan: SubscriptionPlan | None = None,
) -> UserSubscriptionOut:
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
        user_id=user.id if user else s.user_id,
        user_email=user.email if user else None,
        user_name=user.name if user else None,
        plan_slug=plan.slug if plan else None,
        plan_name=plan.name if plan else None,
    )


def _plan_out(repo: BillingRepository, p: SubscriptionPlan) -> PlanOut:
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


@router.get("/billing/settings")
def get_billing_settings(db: Session = Depends(get_db)):
    s = BillingRepository(db).get_admin_settings()
    rz = razorpay_admin_meta(s)
    return {
        "payment_card_enabled": s.payment_card_enabled,
        "payment_upi_enabled": s.payment_upi_enabled,
        "default_trial_days": s.default_trial_days,
        "grace_period_days": s.grace_period_days,
        "renewal_reminder_days_before": s.renewal_reminder_days_before,
        "dunning_retry_interval_hours": s.dunning_retry_interval_hours,
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
        "default_trial_days": s.default_trial_days,
        "grace_period_days": s.grace_period_days,
        "renewal_reminder_days_before": s.renewal_reminder_days_before,
        "dunning_retry_interval_hours": s.dunning_retry_interval_hours,
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


@router.get("/billing/plans", response_model=list[PlanOut])
def admin_list_plans(db: Session = Depends(get_db)):
    repo = BillingRepository(db)
    return [_plan_out(repo, p) for p in repo.list_all_plans()]


@router.post("/billing/plans", response_model=PlanOut)
def admin_create_plan(
    payload: AdminPlanCreate,
    db: Session = Depends(get_db),
):
    repo = BillingRepository(db)
    if repo.get_plan_by_slug(payload.slug):
        raise HTTPException(status_code=409, detail="Slug already exists")
    # If Razorpay sync is requested, validate credentials before persisting the plan.
    # Otherwise a 400 after commit leaves the slug in the DB and the next submit returns 409.
    gw: RazorpayGateway | None = None
    if payload.sync_razorpay_plan:
        gw = get_razorpay_gateway(db)
        if not gw.is_configured:
            raise HTTPException(status_code=400, detail="Razorpay not configured")
    tier = PlanTier(payload.plan_tier)
    feats = payload.features_json or default_features_for_tier(tier)
    plan = SubscriptionPlan(
        slug=payload.slug,
        name=payload.name,
        description=payload.description,
        plan_tier=tier,
        billing_interval=BillingInterval(payload.billing_interval),
        base_amount_paise=payload.base_amount_paise,
        currency=payload.currency,
        features_json=feats,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    if payload.sync_razorpay_plan:
        assert gw is not None
        period = "monthly" if payload.billing_interval == "month" else "yearly"  # noqa: PLR2004
        rz_plan = gw.create_plan(
            period=period,
            interval=1,
            item={
                "name": payload.name,
                "amount": payload.base_amount_paise,
                "currency": payload.currency,
                "description": (payload.description or "")[:200],
            },
            notes={"slug": payload.slug},
        )
        plan.razorpay_plan_id = rz_plan.get("id")
        db.commit()
        db.refresh(plan)

    return _plan_out(repo, plan)


@router.patch("/billing/plans/{plan_id}", response_model=PlanOut)
def admin_update_plan(
    plan_id: int,
    payload: AdminPlanUpdate,
    db: Session = Depends(get_db),
):
    repo = BillingRepository(db)
    plan = repo.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(plan, k, v)
    db.commit()
    db.refresh(plan)
    return _plan_out(repo, plan)


@router.post("/billing/plans/{plan_id}/deactivate")
def admin_deactivate_plan(plan_id: int, db: Session = Depends(get_db)):
    repo = BillingRepository(db)
    plan = repo.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Not found")
    plan.is_active = False
    db.commit()
    return {"ok": True}


@router.post("/billing/plans/{plan_id}/activate")
def admin_activate_plan(plan_id: int, db: Session = Depends(get_db)):
    repo = BillingRepository(db)
    plan = repo.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Not found")
    plan.is_active = True
    db.commit()
    return {"ok": True}


@router.post("/billing/plans/{plan_id}/price-schedules", response_model=dict)
def admin_add_price_schedule(
    plan_id: int,
    payload: AdminPriceScheduleCreate,
    db: Session = Depends(get_db),
):
    repo = BillingRepository(db)
    plan = repo.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Not found")
    row = PlanPriceSchedule(
        plan_id=plan_id,
        amount_paise=payload.amount_paise,
        currency=payload.currency,
        effective_from=payload.effective_from,
        status=PlanPriceScheduleStatus.SCHEDULED,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "plan_id": row.plan_id,
        "amount_paise": row.amount_paise,
        "effective_from": row.effective_from,
    }


@router.post("/billing/coupons", response_model=dict)
def admin_create_coupon(
    payload: AdminCouponCreate,
    db: Session = Depends(get_db),
):
    c = Coupon(
        code=payload.code.strip(),
        discount_type=CouponDiscountType(payload.discount_type),
        discount_value=payload.discount_value,
        max_redemptions=payload.max_redemptions,
        per_user_max=payload.per_user_max,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        allowed_user_id=payload.allowed_user_id,
        allowed_plan_ids=payload.allowed_plan_ids,
        is_active=True,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "code": c.code}


@router.get("/billing/subscriptions", response_model=list[UserSubscriptionOut])
def admin_list_subscriptions(
    db: Session = Depends(get_db),
    limit: int = Query(200, le=1000),
    offset: int = 0,
):
    rows = BillingRepository(db).list_all_subscriptions_with_user_plan(limit=limit, offset=offset)
    return [_user_subscription_out(s, user=u, plan=p) for s, u, p in rows]


@router.post("/billing/subscriptions/manual", response_model=UserSubscriptionOut)
def admin_manual_subscription(
    payload: AdminManualSubscription,
    db: Session = Depends(get_db),
):
    repo = BillingRepository(db)
    plan = repo.get_plan(payload.plan_id)
    user = db.get(Users, payload.user_id)
    if not plan or not user:
        raise HTTPException(status_code=404, detail="User or plan not found")
    now = datetime.utcnow()
    end = now + timedelta(days=30 * payload.period_months)
    sub = UserSubscription(
        user_id=user.id,
        plan_id=plan.id,
        plan_tier_snapshot=plan.plan_tier,
        features_snapshot=plan.features_json or default_features_for_tier(plan.plan_tier),
        status=UserSubscriptionStatus.ACTIVE,
        billing_provider=BillingProvider.MANUAL,
        started_at=now,
        current_period_end=end,
        auto_renew=False,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return _user_subscription_out(sub, user=user, plan=plan)


@router.post("/billing/subscriptions/{sub_id}/deactivate")
def admin_deactivate_subscription(
    sub_id: int,
    db: Session = Depends(get_db),
):
    sub = db.get(UserSubscription, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Not found")
    sub.status = UserSubscriptionStatus.SUSPENDED
    db.commit()
    return {"ok": True}


@router.post("/billing/subscriptions/{sub_id}/activate")
def admin_activate_subscription(
    sub_id: int,
    db: Session = Depends(get_db),
):
    sub = db.get(UserSubscription, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Not found")
    sub.status = UserSubscriptionStatus.ACTIVE
    if not sub.started_at:
        sub.started_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


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


@router.get("/billing/reports", response_model=BillingReportsOut)
def billing_reports(
    db: Session = Depends(get_db),
    year: int = Query(datetime.utcnow().year),
    month: int = Query(datetime.utcnow().month),
):
    repo = BillingRepository(db)
    start = datetime(year, month, 1)
    if month == 12:  # noqa: PLR2004
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    rev = repo.revenue_paise_between(start, end)
    churned, denom = repo.churn_logo_count(start, end)
    rate = (churned / denom) if denom else None
    # MRR approximation: monthly revenue for this calendar month (same as rev for all-monthly)
    mrr = rev
    return BillingReportsOut(
        active_subscribers=repo.active_subscriber_count(),
        revenue_paise_month=rev,
        mrr_paise_approx=mrr,
        churned_users=churned,
        active_at_period_start=denom,
        churn_rate=rate,
    )


@router.post("/billing/reconcile")
def run_reconcile(db: Session = Depends(get_db)):
    return BillingReconciliationService(db).run()
