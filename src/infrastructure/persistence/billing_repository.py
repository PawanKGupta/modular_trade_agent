"""Persistence helpers for billing / subscriptions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from src.infrastructure.db.models import (
    BillingAdminSettings,
    BillingRefund,
    BillingTransaction,
    BillingTransactionStatus,
    Coupon,
    CouponDiscountType,
    CouponRedemption,
    FreeTrialUsage,
    PlanPriceSchedule,
    PlanPriceScheduleStatus,
    RazorpayWebhookEvent,
    SubscriptionPlan,
    UserBillingProfile,
    Users,
    UserSubscription,
    UserSubscriptionStatus,
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

    # --- Plans ---
    def list_active_plans(self) -> list[SubscriptionPlan]:
        return (
            self.db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.is_active.is_(True))
            .order_by(SubscriptionPlan.id.asc())
            .all()
        )

    def list_all_plans(self) -> list[SubscriptionPlan]:
        return self.db.query(SubscriptionPlan).order_by(SubscriptionPlan.id.asc()).all()

    def get_plan(self, plan_id: int) -> SubscriptionPlan | None:
        return self.db.get(SubscriptionPlan, plan_id)

    def get_plan_by_slug(self, slug: str) -> SubscriptionPlan | None:
        return self.db.query(SubscriptionPlan).filter(SubscriptionPlan.slug == slug).first()

    _LIVE_SUBSCRIPTION_STATUSES: tuple[UserSubscriptionStatus, ...] = (
        UserSubscriptionStatus.ACTIVE,
        UserSubscriptionStatus.TRIALING,
        UserSubscriptionStatus.GRACE,
        UserSubscriptionStatus.PAST_DUE,
        UserSubscriptionStatus.PENDING,
    )

    def count_subscriptions_referencing_plan(self, plan_id: int) -> int:
        return int(
            self.db.query(func.count(UserSubscription.id))
            .filter(
                or_(
                    UserSubscription.plan_id == plan_id,
                    UserSubscription.pending_plan_id == plan_id,
                )
            )
            .scalar()
            or 0
        )

    def count_live_subscriptions_on_plan(self, plan_id: int) -> int:
        """Active / trial / grace / past_due / pending — blocks catalog delete per product rules."""
        return int(
            self.db.query(func.count(UserSubscription.id))
            .filter(
                or_(
                    UserSubscription.plan_id == plan_id,
                    UserSubscription.pending_plan_id == plan_id,
                ),
                UserSubscription.status.in_(self._LIVE_SUBSCRIPTION_STATUSES),
            )
            .scalar()
            or 0
        )

    def coupon_allowed_list_references_plan(self, plan_id: int) -> bool:
        rows = self.db.query(Coupon).filter(Coupon.allowed_plan_ids.isnot(None)).all()
        for c in rows:
            ids = c.allowed_plan_ids
            if isinstance(ids, list) and plan_id in ids:
                return True
        return False

    def delete_plan_and_schedules(self, plan_id: int) -> None:
        """Remove price schedules then the plan row. Caller must enforce preconditions."""
        try:
            self.db.query(PlanPriceSchedule).filter(PlanPriceSchedule.plan_id == plan_id).delete(
                synchronize_session=False
            )
            p = self.db.get(SubscriptionPlan, plan_id)
            if p is not None:
                self.db.delete(p)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    # --- Effective price (base + latest applicable schedule) ---
    def effective_amount_paise(self, plan: SubscriptionPlan, at: datetime | None = None) -> int:
        """Pick scheduled price with max effective_from <= at (or now), else base_amount_paise."""
        ref = at or datetime.utcnow()
        sched = (
            self.db.query(PlanPriceSchedule)
            .filter(
                PlanPriceSchedule.plan_id == plan.id,
                PlanPriceSchedule.status == PlanPriceScheduleStatus.SCHEDULED,
                PlanPriceSchedule.effective_from <= ref,
            )
            .order_by(PlanPriceSchedule.effective_from.desc())
            .first()
        )
        if sched:
            return int(sched.amount_paise)
        return int(plan.base_amount_paise)

    # --- Profile ---
    def get_billing_profile(self, user_id: int) -> UserBillingProfile | None:
        return (
            self.db.query(UserBillingProfile).filter(UserBillingProfile.user_id == user_id).first()
        )

    def upsert_billing_profile(
        self, user_id: int, *, razorpay_customer_id: str | None = None
    ) -> UserBillingProfile:
        row = self.get_billing_profile(user_id)
        if not row:
            row = UserBillingProfile(user_id=user_id)
            self.db.add(row)
        if razorpay_customer_id is not None:
            row.razorpay_customer_id = razorpay_customer_id
        self.db.commit()
        self.db.refresh(row)
        return row

    # --- Subscriptions ---
    def get_subscription(self, sub_id: int) -> UserSubscription | None:
        return self.db.get(UserSubscription, sub_id)

    def list_subscriptions_for_user(self, user_id: int) -> list[UserSubscription]:
        return (
            self.db.query(UserSubscription)
            .filter(UserSubscription.user_id == user_id)
            .order_by(UserSubscription.id.desc())
            .all()
        )

    def list_all_subscriptions(self, limit: int = 500, offset: int = 0) -> list[UserSubscription]:
        return (
            self.db.query(UserSubscription)
            .order_by(UserSubscription.id.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def list_all_subscriptions_with_user_plan(
        self, limit: int = 500, offset: int = 0
    ) -> list[tuple[UserSubscription, Users, SubscriptionPlan]]:
        return (
            self.db.query(UserSubscription, Users, SubscriptionPlan)
            .join(Users, UserSubscription.user_id == Users.id)
            .join(SubscriptionPlan, UserSubscription.plan_id == SubscriptionPlan.id)
            .order_by(UserSubscription.id.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    # --- Coupons ---
    def get_coupon_by_code(self, code: str) -> Coupon | None:
        return (
            self.db.query(Coupon)
            .filter(func.lower(Coupon.code) == code.lower().strip())
            .filter(Coupon.is_active.is_(True))
            .first()
        )

    def count_coupon_redemptions(self, coupon_id: int) -> int:
        return (
            self.db.query(func.count(CouponRedemption.id))
            .filter(CouponRedemption.coupon_id == coupon_id)
            .scalar()
            or 0
        )

    def count_user_coupon_redemptions(self, coupon_id: int, user_id: int) -> int:
        return (
            self.db.query(func.count(CouponRedemption.id))
            .filter(
                CouponRedemption.coupon_id == coupon_id,
                CouponRedemption.user_id == user_id,
            )
            .scalar()
            or 0
        )

    def redeem_coupon(
        self, coupon_id: int, user_id: int, user_subscription_id: int | None
    ) -> CouponRedemption:
        r = CouponRedemption(
            coupon_id=coupon_id,
            user_id=user_id,
            user_subscription_id=user_subscription_id,
        )
        self.db.add(r)
        self.db.commit()
        self.db.refresh(r)
        return r

    # --- Trial ---
    def trial_used(self, user_id: int, trial_key: str) -> bool:
        return (
            self.db.query(FreeTrialUsage)
            .filter(
                FreeTrialUsage.user_id == user_id,
                FreeTrialUsage.trial_key == trial_key,
            )
            .first()
            is not None
        )

    def mark_trial_used(self, user_id: int, trial_key: str) -> None:
        if self.trial_used(user_id, trial_key):
            return
        self.db.add(FreeTrialUsage(user_id=user_id, trial_key=trial_key))
        self.db.commit()

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

    # --- Reports ---
    def active_subscriber_count(self, as_of: datetime | None = None) -> int:
        ref = as_of or datetime.utcnow()
        return (
            self.db.query(func.count(UserSubscription.id))
            .filter(
                UserSubscription.status.in_(
                    (
                        UserSubscriptionStatus.ACTIVE,
                        UserSubscriptionStatus.TRIALING,
                        UserSubscriptionStatus.GRACE,
                    )
                ),
                or_(
                    UserSubscription.current_period_end.is_(None),
                    UserSubscription.current_period_end >= ref,
                ),
            )
            .scalar()
            or 0
        )

    def revenue_paise_between(self, start: datetime, end: datetime) -> int:
        q = (
            self.db.query(func.coalesce(func.sum(BillingTransaction.amount_paise), 0))
            .filter(
                BillingTransaction.status == BillingTransactionStatus.CAPTURED,
                BillingTransaction.created_at >= start,
                BillingTransaction.created_at < end,
            )
            .scalar()
        )
        return int(q or 0)

    def churn_logo_count(self, period_start: datetime, period_end: datetime) -> tuple[int, int]:
        """
        Logo churn for (period_start, period_end]:
        churned = distinct users whose subscription moved to cancelled/expired in window.
        denominator = active subscribers at period_start (snapshot heuristic:
        status in active set at start).
        """
        active_at_start = (
            self.db.query(func.count(func.distinct(UserSubscription.user_id)))
            .filter(
                UserSubscription.status.in_(
                    (
                        UserSubscriptionStatus.ACTIVE,
                        UserSubscriptionStatus.TRIALING,
                        UserSubscriptionStatus.GRACE,
                    )
                ),
                UserSubscription.started_at.isnot(None),
                UserSubscription.started_at < period_start,
                or_(
                    UserSubscription.current_period_end.is_(None),
                    UserSubscription.current_period_end >= period_start,
                ),
            )
            .scalar()
            or 0
        )
        churned = (
            self.db.query(func.count(func.distinct(UserSubscription.user_id)))
            .filter(
                UserSubscription.status.in_(
                    (UserSubscriptionStatus.CANCELLED, UserSubscriptionStatus.EXPIRED)
                ),
                UserSubscription.updated_at > period_start,
                UserSubscription.updated_at <= period_end,
            )
            .scalar()
            or 0
        )
        return int(churned), int(active_at_start)


def apply_coupon_discount(amount_paise: int, coupon: Coupon) -> int:
    if coupon.discount_type == CouponDiscountType.PERCENT:
        pct = min(100, max(0, int(coupon.discount_value)))
        return max(0, int(amount_paise * (100 - pct) / 100))
    return max(0, amount_paise - int(coupon.discount_value))
