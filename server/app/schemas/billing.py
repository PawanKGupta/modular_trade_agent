# ruff: noqa: B008
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PlanOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str | None
    plan_tier: str
    billing_interval: str
    base_amount_paise: int
    effective_amount_paise: int
    currency: str
    features_json: dict[str, Any]
    razorpay_plan_id: str | None
    is_active: bool


class EntitlementsOut(BaseModel):
    active: bool
    status: str | None
    plan_tier: str | None
    features: dict[str, Any]
    current_period_end: datetime | None


class SubscribeRequest(BaseModel):
    plan_id: int
    coupon_code: str | None = None


class SubscribeResponse(BaseModel):
    razorpay_key_id: str | None
    razorpay_subscription_id: str | None
    user_subscription_id: int
    amount_quoted_paise: int
    trial_days_applied: int = 0


class SubscriptionPayLinkOut(BaseModel):
    """Razorpay-hosted URL to authenticate / retry payment when available."""

    short_url: str | None = None
    detail: str | None = None


class UserSubscriptionOut(BaseModel):
    id: int
    plan_id: int
    status: str
    billing_provider: str
    started_at: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    trial_end: datetime | None
    pending_plan_id: int | None


class TransactionOut(BaseModel):
    id: int
    user_id: int
    user_subscription_id: int | None
    amount_paise: int
    currency: str
    status: str
    razorpay_payment_id: str | None
    failure_reason: str | None
    created_at: datetime


class AdminPlanCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=64)
    name: str
    description: str | None = None
    plan_tier: Literal["paper_basic", "auto_advanced"]
    billing_interval: Literal["month", "year"]
    base_amount_paise: int = Field(ge=0)
    currency: str = "INR"
    features_json: dict[str, Any] | None = None
    sync_razorpay_plan: bool = False


class AdminPlanUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    base_amount_paise: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    razorpay_plan_id: str | None = None
    features_json: dict[str, Any] | None = None


class AdminPriceScheduleCreate(BaseModel):
    amount_paise: int = Field(ge=0)
    currency: str = "INR"
    effective_from: datetime


class AdminCouponCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    discount_type: Literal["percent", "fixed"]
    discount_value: int = Field(ge=0)
    max_redemptions: int | None = None
    per_user_max: int = 1
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    allowed_user_id: int | None = None
    allowed_plan_ids: list[int] | None = None


class AdminBillingSettingsUpdate(BaseModel):
    payment_card_enabled: bool | None = None
    payment_upi_enabled: bool | None = None
    default_trial_days: int | None = Field(default=None, ge=0, le=90)
    grace_period_days: int | None = Field(default=None, ge=0, le=60)
    renewal_reminder_days_before: int | None = Field(default=None, ge=1, le=30)
    dunning_retry_interval_hours: int | None = Field(default=None, ge=1, le=168)


class AdminManualSubscription(BaseModel):
    user_id: int
    plan_id: int
    period_months: int = Field(default=1, ge=1, le=36)


class AdminRefundRequest(BaseModel):
    billing_transaction_id: int
    amount_paise: int | None = Field(
        default=None,
        description="Partial refund in paise; omit for full refund (Razorpay default)",
    )
    reason: str | None = None


class BillingReportsOut(BaseModel):
    active_subscribers: int
    revenue_paise_month: int
    mrr_paise_approx: int
    churned_users: int
    active_at_period_start: int
    churn_rate: float | None
