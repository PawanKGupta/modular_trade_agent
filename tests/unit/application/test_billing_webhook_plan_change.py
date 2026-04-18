"""apply_pending_plan_change swaps plan when pending_plan_id is set."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.application.services.billing_webhook_service import apply_pending_plan_change
from src.infrastructure.db.models import (
    BillingInterval,
    BillingProvider,
    PlanTier,
    SubscriptionPlan,
    UserRole,
    Users,
    UserSubscription,
    UserSubscriptionStatus,
)


@pytest.fixture
def user(db_session) -> Users:
    u = Users(
        email="plan-change@example.com",
        name="U",
        password_hash="x",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def plans(db_session) -> tuple[SubscriptionPlan, SubscriptionPlan]:
    a = SubscriptionPlan(
        slug="pc-a",
        name="A",
        description=None,
        plan_tier=PlanTier.PAPER_BASIC,
        billing_interval=BillingInterval.MONTH,
        base_amount_paise=0,
        currency="INR",
        features_json={"stock_recommendations": True, "broker_execution": False},
        is_active=True,
    )
    b = SubscriptionPlan(
        slug="pc-b",
        name="B",
        description=None,
        plan_tier=PlanTier.AUTO_ADVANCED,
        billing_interval=BillingInterval.MONTH,
        base_amount_paise=0,
        currency="INR",
        features_json={"stock_recommendations": True, "broker_execution": True},
        is_active=True,
    )
    db_session.add_all([a, b])
    db_session.commit()
    db_session.refresh(a)
    db_session.refresh(b)
    return a, b


def test_apply_pending_plan_change_updates_plan(
    db_session,
    user,
    plans: tuple[SubscriptionPlan, SubscriptionPlan],
):
    a, b = plans
    sub = UserSubscription(
        user_id=user.id,
        plan_id=a.id,
        plan_tier_snapshot=a.plan_tier,
        features_snapshot=a.features_json,
        status=UserSubscriptionStatus.ACTIVE,
        billing_provider=BillingProvider.RAZORPAY,
        started_at=datetime.utcnow(),
        current_period_end=datetime.utcnow(),
        pending_plan_id=b.id,
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)

    apply_pending_plan_change(db_session, sub)
    db_session.commit()
    db_session.refresh(sub)

    assert sub.plan_id == b.id
    assert sub.plan_tier_snapshot == b.plan_tier
    assert sub.pending_plan_id is None
    assert sub.features_snapshot.get("broker_execution") is True
