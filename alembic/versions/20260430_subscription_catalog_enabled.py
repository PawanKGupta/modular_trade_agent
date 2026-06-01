# ruff: noqa
"""Admin toggle: user-facing subscription plan catalog (subscribe / change plan).

Revision ID: 20260430_sub_catalog
Revises: 20260429_perf_bill_pay
Create Date: 2026-04-30
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260430_sub_catalog"
down_revision = "20260429_perf_bill_pay"
branch_labels = None
depends_on = None

_TABLE = "billing_admin_settings"
_COL = "subscription_catalog_enabled"


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if _TABLE not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(_TABLE)}
    if _COL not in cols:
        op.add_column(
            _TABLE,
            sa.Column(_COL, sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if _TABLE not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(_TABLE)}
    if _COL in cols:
        op.drop_column(_TABLE, _COL)
