"""Add max_order_value to user_trading_config.

Revision ID: 20260626_add_max_order_value
Revises: 20260613_user_sec
Create Date: 2026-06-26
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260626_add_max_order_value"
down_revision = "20260613_user_sec"
branch_labels = None
depends_on = None

_TABLE = "user_trading_config"
_COL = "max_order_value"


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if _TABLE not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(_TABLE)}
    if _COL in cols:
        return
    op.add_column(
        _TABLE,
        sa.Column(_COL, sa.Float(), nullable=False, server_default="500000.0"),
    )
    op.alter_column(_TABLE, _COL, server_default=None)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if _TABLE not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(_TABLE)}
    if _COL not in cols:
        return
    op.drop_column(_TABLE, _COL)
