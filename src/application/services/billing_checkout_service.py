"""Create Razorpay subscriptions and manage plan changes (user flows)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from src.application.services.razorpay_credentials import get_razorpay_gateway
from src.application.services.subscription_entitlement_service import default_features_for_tier
from src.infrastructure.db.models import (
    BillingProvider,
    Coupon,
    SubscriptionPlan,
    Users,
    UserSubscription,
    UserSubscriptionStatus,
)
from src.infrastructure.payments.razorpay_gateway import RazorpayGateway
from src.infrastructure.persistence.billing_repository import (
    BillingRepository,
    apply_coupon_discount,
)

logger = logging.getLogger(__name__)


class BillingCheckoutError(Exception):
    pass


class BillingCheckoutService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = BillingRepository(db)

    @property
    def rzp(self) -> RazorpayGateway:
        return get_razorpay_gateway(self.db)

    def _validate_coupon(self, coupon: Coupon | None, user_id: int, plan_id: int) -> None:
        if not coupon:
            return
        now = datetime.utcnow()
        if coupon.allowed_user_id is not None and coupon.allowed_user_id != user_id:
            raise BillingCheckoutError("Coupon not valid for this account")
        if coupon.valid_from and now < coupon.valid_from:
            raise BillingCheckoutError("Coupon not yet valid")
        if coupon.valid_until and now > coupon.valid_until:
            raise BillingCheckoutError("Coupon has expired")
        if coupon.max_redemptions is not None:
            if self.repo.count_coupon_redemptions(coupon.id) >= coupon.max_redemptions:
                raise BillingCheckoutError("Coupon redemption limit reached")
        if self.repo.count_user_coupon_redemptions(coupon.id, user_id) >= coupon.per_user_max:
            raise BillingCheckoutError("Coupon already used for this account")
        if coupon.allowed_plan_ids:
            if plan_id not in [int(x) for x in coupon.allowed_plan_ids]:
                raise BillingCheckoutError("Coupon not valid for this plan")

    def create_checkout(
        self,
        user: Users,
        plan: SubscriptionPlan,
        coupon: Coupon | None = None,
        *,
        trial_days: int | None = None,
    ) -> dict:
        if not plan.is_active:
            raise BillingCheckoutError("Plan is not available")
        if not self.rzp.is_configured:
            raise BillingCheckoutError("Payments are not configured (missing Razorpay keys)")

        self._validate_coupon(coupon, user.id, plan.id)

        if not plan.razorpay_plan_id:
            raise BillingCheckoutError(
                "Plan is not linked to Razorpay (admin must set razorpay_plan_id or sync plan)"
            )

        profile = self.repo.upsert_billing_profile(user.id)
        if not profile.razorpay_customer_id:
            cust = self.rzp.create_customer(
                name=user.name, email=user.email, notes={"user_id": str(user.id)}
            )
            profile = self.repo.upsert_billing_profile(
                user.id,
                razorpay_customer_id=cust.get("id"),
            )

        admin = self.repo.get_admin_settings()
        td = trial_days if trial_days is not None else int(admin.default_trial_days or 0)
        if td > 0 and self.repo.trial_used(user.id, "global_v1"):
            td = 0

        amount = self.repo.effective_amount_paise(plan)
        if coupon:
            amount = apply_coupon_discount(amount, coupon)

        sub_row = UserSubscription(
            user_id=user.id,
            plan_id=plan.id,
            plan_tier_snapshot=plan.plan_tier,
            features_snapshot=plan.features_json or default_features_for_tier(plan.plan_tier),
            status=UserSubscriptionStatus.PENDING,
            billing_provider=BillingProvider.RAZORPAY,
            auto_renew=True,
        )
        if td > 0:
            sub_row.status = UserSubscriptionStatus.TRIALING
            sub_row.trial_end = datetime.utcnow() + timedelta(days=td)
        self.db.add(sub_row)
        self.db.commit()
        self.db.refresh(sub_row)

        if coupon:
            self.repo.redeem_coupon(coupon.id, user.id, sub_row.id)

        if td > 0:
            self.repo.mark_trial_used(user.id, "global_v1")

        notes = {"app_user_subscription_id": str(sub_row.id), "user_id": str(user.id)}
        try:
            rsub = self.rzp.create_subscription(
                plan_id=plan.razorpay_plan_id,
                customer_id=profile.razorpay_customer_id or "",
                total_count=240,
                notes=notes,
            )
        except Exception as e:
            logger.exception("Razorpay subscription create failed")
            sub_row.status = UserSubscriptionStatus.SUSPENDED
            self.db.commit()
            raise BillingCheckoutError(str(e)) from e

        sub_row.razorpay_subscription_id = rsub.get("id")
        self.db.commit()

        return {
            "razorpay_key_id": self.rzp.key_id,
            "razorpay_subscription_id": sub_row.razorpay_subscription_id,
            "user_subscription_id": sub_row.id,
            "amount_quoted_paise": amount,
            "trial_days_applied": td,
        }

    def cancel_at_period_end(self, user: Users, user_subscription_id: int) -> UserSubscription:
        sub = self.repo.get_subscription(user_subscription_id)
        if not sub or sub.user_id != user.id:
            raise BillingCheckoutError("Subscription not found")
        if (
            sub.billing_provider == BillingProvider.RAZORPAY
            and sub.razorpay_subscription_id
            and self.rzp.is_configured
        ):
            try:
                self.rzp.cancel_subscription(sub.razorpay_subscription_id, cancel_at_cycle_end=1)
            except Exception as e:
                logger.warning(
                    "Razorpay cancel request failed (continuing with local flags): %s", e
                )
        sub.cancel_at_period_end = True
        # Remain active until period end; reconciliation/webhook may mark cancelled.
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def schedule_plan_change(
        self, user: Users, user_subscription_id: int, new_plan_id: int
    ) -> UserSubscription:
        sub = self.repo.get_subscription(user_subscription_id)
        if not sub or sub.user_id != user.id:
            raise BillingCheckoutError("Subscription not found")
        new_plan = self.repo.get_plan(new_plan_id)
        if not new_plan or not new_plan.is_active:
            raise BillingCheckoutError("Target plan invalid")
        sub.pending_plan_id = new_plan_id
        self.db.commit()
        self.db.refresh(sub)
        return sub
