# ruff: noqa
"""Add notify_payment_failed if missing (post-stamp / legacy DBs).

Revision ID: 20260504_notify_pay_failed
Revises: 20260503_rm_sub_billing
Create Date: 2026-05-04

Databases stamped to head without running 20260419 can lack billing
notification columns while ORM expects them.
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260504_notify_pay_failed"
down_revision = "20260503_rm_sub_billing"
branch_labels = None
depends_on = None

_PREFS = "user_notification_preferences"
_COL = "notify_payment_failed"


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if _PREFS not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(_PREFS)}
    if _COL in cols:
        return
    if conn.dialect.name == "postgresql":
        op.execute(
            sa.text(
                f'ALTER TABLE "{_PREFS}" ADD COLUMN IF NOT EXISTS '
                f'"{_COL}" boolean NOT NULL DEFAULT true'
            )
        )
    else:
        op.add_column(
            _PREFS,
            sa.Column(_COL, sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if _PREFS not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(_PREFS)}
    if _COL in cols:
        op.drop_column(_PREFS, _COL)
