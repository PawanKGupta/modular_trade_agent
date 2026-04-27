# ruff: noqa: PLR0911
"""
Resolve effective subscription entitlements for a user.

When `subscription_enforcement_enabled` is False (default), all non-blocked users
receive full feature access for backward compatibility.

Admins always receive full access.

Grandfathering: if `subscription_grandfather_until` is set and now is before that
instant (UTC), non-admin users receive full access regardless of subscription rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from server.app.core.config import settings
from src.infrastructure.db.models import (
    PlanTier,
    UserRole,
    Users,
    UserSubscription,
    UserSubscriptionStatus,
)


@dataclass
class EffectiveEntitlement:
    """Resolved entitlements for authorization and UI."""

    active: bool
    status: str | None
    plan_tier: PlanTier | None
    features: dict[str, Any]
    current_period_end: datetime | None
    user_subscription_id: int | None


FULL_FEATURES: dict[str, bool] = {
    "stock_recommendations": True,
    "broker_execution": True,
    "auto_trade_services": True,
    "paper_trading": True,
}


def default_features_for_tier(tier: PlanTier) -> dict[str, bool]:
    if tier == PlanTier.PAPER_BASIC:
        return {
            "stock_recommendations": True,
            "broker_execution": False,
            "auto_trade_services": False,
            "paper_trading": True,
        }
    return dict(FULL_FEATURES)


class SubscriptionEntitlementService:
    def __init__(self, db: Session):
        self._db = db

    def _grandfather_active(self) -> bool:
        raw = settings.subscription_grandfather_until
        if not raw:
            return False
        try:
            # Accept date-only or full ISO
            if len(raw) == 10:  # noqa: PLR2004
                end = datetime.fromisoformat(raw + "T23:59:59+00:00")
            else:
                end = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if end.tzinfo is None:
                end = end.replace(tzinfo=UTC)
            return datetime.now(UTC) <= end
        except ValueError:
            return False

    def _primary_subscription(self, user_id: int) -> UserSubscription | None:
        statuses = (
            UserSubscriptionStatus.ACTIVE,
            UserSubscriptionStatus.TRIALING,
            UserSubscriptionStatus.GRACE,
            UserSubscriptionStatus.PAST_DUE,
        )
        return (
            self._db.query(UserSubscription)
            .filter(UserSubscription.user_id == user_id)
            .filter(UserSubscription.status.in_(statuses))
            .order_by(UserSubscription.id.desc())
            .first()
        )

    def resolve(self, user: Users) -> EffectiveEntitlement:
        if user.role == UserRole.ADMIN or not user.is_active:
            # Inactive users: treat as no subscription (API layer already blocks auth for inactive)
            if not user.is_active:
                return EffectiveEntitlement(
                    active=False,
                    status=None,
                    plan_tier=None,
                    features={k: False for k in FULL_FEATURES},
                    current_period_end=None,
                    user_subscription_id=None,
                )
            return EffectiveEntitlement(
                active=True,
                status="admin",
                plan_tier=PlanTier.AUTO_ADVANCED,
                features=dict(FULL_FEATURES),
                current_period_end=None,
                user_subscription_id=None,
            )

        if not settings.subscription_enforcement_enabled:
            return EffectiveEntitlement(
                active=True,
                status="enforcement_off",
                plan_tier=PlanTier.AUTO_ADVANCED,
                features=dict(FULL_FEATURES),
                current_period_end=None,
                user_subscription_id=None,
            )

        if self._grandfather_active():
            return EffectiveEntitlement(
                active=True,
                status="grandfathered",
                plan_tier=PlanTier.AUTO_ADVANCED,
                features=dict(FULL_FEATURES),
                current_period_end=None,
                user_subscription_id=None,
            )

        sub = self._primary_subscription(user.id)
        if not sub:
            return EffectiveEntitlement(
                active=False,
                status=None,
                plan_tier=None,
                features={k: False for k in FULL_FEATURES},
                current_period_end=None,
                user_subscription_id=None,
            )

        if sub.status == UserSubscriptionStatus.TRIALING and sub.trial_end:
            if datetime.utcnow() > sub.trial_end:
                return EffectiveEntitlement(
                    active=False,
                    status="trial_expired",
                    plan_tier=sub.plan_tier_snapshot,
                    features={k: False for k in FULL_FEATURES},
                    current_period_end=sub.current_period_end,
                    user_subscription_id=sub.id,
                )

        feats = dict(sub.features_snapshot or {})
        for k, v in default_features_for_tier(sub.plan_tier_snapshot).items():
            feats.setdefault(k, v)

        return EffectiveEntitlement(
            active=True,
            status=sub.status.value,
            plan_tier=sub.plan_tier_snapshot,
            features=feats,
            current_period_end=sub.current_period_end,
            user_subscription_id=sub.id,
        )

    def user_has_feature(self, user: Users, feature: str) -> bool:
        ent = self.resolve(user)
        return bool(ent.features.get(feature))
