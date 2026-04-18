"""Periodic billing reconciliation: reminders, grace expiry, subscription expiry."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from services.email_notifier import EmailNotifier
from services.notification_preference_service import (
    NotificationEventType,
    NotificationPreferenceService,
)
from src.infrastructure.db.models import Users, UserSubscription, UserSubscriptionStatus
from src.infrastructure.persistence.billing_repository import BillingRepository

logger = logging.getLogger(__name__)


class BillingReconciliationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = BillingRepository(db)

    def run(self) -> dict:
        """Run all lightweight reconciliation steps; return counters."""
        admin = self.repo.get_admin_settings()
        now = datetime.utcnow()
        reminders = self._renewal_reminders(admin, now)
        trials = self._expire_trials(now)
        grace = self._grace_and_expiry(now)
        return {
            "renewal_reminders_sent": reminders,
            "trial_subscriptions_expired": trials,
            "subscriptions_updated": grace,
        }

    def _expire_trials(self, now: datetime) -> int:
        """Mark TRIALING subscriptions past trial_end as EXPIRED (no webhook yet)."""
        rows = (
            self.db.query(UserSubscription)
            .filter(
                UserSubscription.status == UserSubscriptionStatus.TRIALING,
                UserSubscription.trial_end.isnot(None),
                UserSubscription.trial_end < now,
            )
            .all()
        )
        n = 0
        for sub in rows:
            sub.status = UserSubscriptionStatus.EXPIRED
            n += 1
        if n:
            self.db.commit()
        return n

    def _renewal_reminders(self, admin, now: datetime) -> int:
        lead = int(admin.renewal_reminder_days_before or 7)
        window_start = now + timedelta(days=lead)
        window_end = now + timedelta(days=lead + 1)
        q = (
            self.db.query(UserSubscription)
            .filter(
                UserSubscription.status == UserSubscriptionStatus.ACTIVE,
                UserSubscription.current_period_end.isnot(None),
                UserSubscription.current_period_end >= window_start,
                UserSubscription.current_period_end < window_end,
            )
            .all()
        )
        sent = 0
        notifier = EmailNotifier()
        pref = NotificationPreferenceService(self.db)
        for sub in q:
            if sub.last_renewal_reminder_for_period_end == sub.current_period_end:
                continue
            user = self.db.get(Users, sub.user_id)
            if not user:
                continue
            if not pref.should_notify(
                user.id, NotificationEventType.SUBSCRIPTION_RENEWAL_REMINDER, channel="email"
            ):
                continue
            prefs = pref.get_preferences(user.id)
            email_to = (prefs.email_address if prefs else None) or user.email
            if notifier.is_available() and email_to:
                ok = notifier.send_email(
                    email_to,
                    "Subscription renewal reminder",
                    f"Your subscription renews on {sub.current_period_end}.",
                )
                if ok:
                    sub.last_renewal_reminder_for_period_end = sub.current_period_end
                    self.db.commit()
                    sent += 1
        return sent

    def _grace_and_expiry(self, now: datetime) -> int:
        n = 0
        overdue = (
            self.db.query(UserSubscription)
            .filter(
                UserSubscription.status.in_(
                    (
                        UserSubscriptionStatus.PAST_DUE,
                        UserSubscriptionStatus.GRACE,
                    )
                ),
                UserSubscription.grace_until.isnot(None),
                UserSubscription.grace_until < now,
            )
            .all()
        )
        for sub in overdue:
            sub.status = UserSubscriptionStatus.EXPIRED
            n += 1
        expired = (
            self.db.query(UserSubscription)
            .filter(
                UserSubscription.status == UserSubscriptionStatus.ACTIVE,
                UserSubscription.cancel_at_period_end.is_(True),
                UserSubscription.current_period_end.isnot(None),
                UserSubscription.current_period_end < now,
            )
            .all()
        )
        for sub in expired:
            sub.status = UserSubscriptionStatus.CANCELLED
            n += 1
        hard = (
            self.db.query(UserSubscription)
            .filter(
                UserSubscription.status == UserSubscriptionStatus.ACTIVE,
                UserSubscription.current_period_end.isnot(None),
                UserSubscription.current_period_end < now,
                UserSubscription.cancel_at_period_end.is_(False),
            )
            .all()
        )
        for sub in hard:
            sub.status = UserSubscriptionStatus.EXPIRED
            n += 1
        if n:
            self.db.commit()
        return n
