# ruff: noqa
"""Remove subscription_catalog_enabled (legacy plan catalog toggle removed).

Revision ID: 20260501_drop_sub_catalog
Revises: 20260430_sub_catalog
Create Date: 2026-05-01
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260501_drop_sub_catalog"
down_revision = "20260430_sub_catalog"
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
    if _COL in cols:
        op.drop_column(_TABLE, _COL)


def downgrade() -> None:
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
