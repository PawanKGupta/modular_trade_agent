"""Add notify_balance_shortfall preference (default on).

Revision ID: 20260610_bal_short
Revises: 20260610_svc_off
Create Date: 2026-06-10
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260610_bal_short"
down_revision = "20260610_svc_off"
branch_labels = None
depends_on = None

_PREFS = "user_notification_preferences"
_COL = "notify_balance_shortfall"


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
