# ruff: noqa
"""Ensure billing notification columns on user_notification_preferences

Revision ID: 20260419_notify_prefs_billing
Revises: 20260418_billing_sub
Create Date: 2026-04-19

Some databases were stamped after 20260418_billing_sub before the parent
migration added these columns. This revision adds them idempotently.
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260419_notify_prefs_billing"
down_revision = "20260418_billing_sub"
branch_labels = None
depends_on = None

_PREFS_TABLE = "user_notification_preferences"

_BILLING_BOOL_COLS = (
    ("notify_subscription_renewal_reminder", "true"),
    ("notify_payment_failed", "true"),
    ("notify_subscription_activated", "true"),
    ("notify_subscription_cancelled", "true"),
)


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name
    inspector = inspect(conn)
    if _PREFS_TABLE not in inspector.get_table_names():
        return
    if dialect == "postgresql":
        # Idempotent DDL; safe if 20260418 already added columns or partial applies.
        for name, default in _BILLING_BOOL_COLS:
            op.execute(
                sa.text(
                    f'ALTER TABLE "{_PREFS_TABLE}" ADD COLUMN IF NOT EXISTS '
                    f'"{name}" boolean NOT NULL DEFAULT {default}'
                )
            )
        return
    cols = {c["name"] for c in inspector.get_columns(_PREFS_TABLE)}
    for name, default in _BILLING_BOOL_COLS:
        if name not in cols:
            op.add_column(
                _PREFS_TABLE,
                sa.Column(
                    name,
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text(default),
                ),
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if _PREFS_TABLE not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(_PREFS_TABLE)}
    for name, _ in reversed(_BILLING_BOOL_COLS):
        if name in cols:
            op.drop_column(_PREFS_TABLE, name)
