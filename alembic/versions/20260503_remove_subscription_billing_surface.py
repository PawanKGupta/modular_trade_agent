# ruff: noqa
"""Drop subscription-style billing admin prefs and notification toggles.

Revision ID: 20260503_rm_sub_billing
Revises: 20260502_sub_admin_metrics
Create Date: 2026-05-03
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260503_rm_sub_billing"
down_revision = "20260502_sub_admin_metrics"
branch_labels = None
depends_on = None

_ADMIN = "billing_admin_settings"
_ADMIN_COLS = (
    "default_trial_days",
    "grace_period_days",
    "renewal_reminder_days_before",
    "dunning_retry_interval_hours",
    "show_subscription_admin_metrics",
)

_PREFS = "user_notification_preferences"
_PREF_COLS = (
    "notify_subscription_renewal_reminder",
    "notify_subscription_activated",
    "notify_subscription_cancelled",
)


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if _ADMIN in tables:
        cols = {c["name"] for c in inspector.get_columns(_ADMIN)}
        for name in _ADMIN_COLS:
            if name in cols:
                op.drop_column(_ADMIN, name)

    if _PREFS in tables:
        cols = {c["name"] for c in inspector.get_columns(_PREFS)}
        for name in _PREF_COLS:
            if name in cols:
                op.drop_column(_PREFS, name)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if _ADMIN in tables:
        cols = {c["name"] for c in inspector.get_columns(_ADMIN)}
        adds = [
            ("default_trial_days", sa.Integer(), "0"),
            ("grace_period_days", sa.Integer(), "3"),
            ("renewal_reminder_days_before", sa.Integer(), "7"),
            ("dunning_retry_interval_hours", sa.Integer(), "24"),
            ("show_subscription_admin_metrics", sa.Boolean(), "false"),
        ]
        for name, typ, default in adds:
            if name not in cols:
                op.add_column(
                    _ADMIN,
                    sa.Column(name, typ, nullable=False, server_default=sa.text(default)),
                )

    if _PREFS in tables:
        cols = {c["name"] for c in inspector.get_columns(_PREFS)}
        for name in _PREF_COLS:
            if name not in cols:
                op.add_column(
                    _PREFS,
                    sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.text("true")),
                )
