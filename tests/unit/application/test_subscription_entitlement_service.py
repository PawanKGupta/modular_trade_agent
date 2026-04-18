from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from server.app.core.config import settings
from src.application.services.subscription_entitlement_service import SubscriptionEntitlementService
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
        email="entitlement-test@example.com",
        name="T",
        password_hash="x",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def paper_plan(db_session) -> SubscriptionPlan:
    p = SubscriptionPlan(
        slug="t-paper-ent",
        name="Paper",
        description=None,
        plan_tier=PlanTier.PAPER_BASIC,
        billing_interval=BillingInterval.MONTH,
        base_amount_paise=100,
        currency="INR",
        features_json={
            "stock_recommendations": True,
            "broker_execution": False,
            "auto_trade_services": False,
            "paper_trading": True,
        },
        is_active=True,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


def test_enforcement_off_grants_all(db_session, user):
    prev = settings.subscription_enforcement_enabled
    settings.subscription_enforcement_enabled = False
    try:
        ent = SubscriptionEntitlementService(db_session).resolve(user)
        assert ent.active is True
        assert ent.features.get("broker_execution") is True
    finally:
        settings.subscription_enforcement_enabled = prev


def test_enforcement_on_paper_plan_blocks_broker(db_session, user, paper_plan):
    prev_e = settings.subscription_enforcement_enabled
    settings.subscription_enforcement_enabled = True
    settings.subscription_grandfather_until = None
    try:
        db_session.add(
            UserSubscription(
                user_id=user.id,
                plan_id=paper_plan.id,
                plan_tier_snapshot=paper_plan.plan_tier,
                features_snapshot=paper_plan.features_json,
                status=UserSubscriptionStatus.ACTIVE,
                billing_provider=BillingProvider.MANUAL,
                started_at=datetime.utcnow(),
                current_period_end=datetime.utcnow() + timedelta(days=30),
            )
        )
        db_session.commit()

        ent = SubscriptionEntitlementService(db_session).resolve(user)
        assert ent.active is True
        assert ent.features.get("broker_execution") is False
        assert ent.features.get("stock_recommendations") is True
    finally:
        settings.subscription_enforcement_enabled = prev_e


def test_admin_always_full(db_session):
    u = Users(
        email="admin-ent@example.com",
        name="A",
        password_hash="x",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    prev = settings.subscription_enforcement_enabled
    settings.subscription_enforcement_enabled = True
    try:
        ent = SubscriptionEntitlementService(db_session).resolve(u)
        assert ent.features.get("broker_execution") is True
    finally:
        settings.subscription_enforcement_enabled = prev
