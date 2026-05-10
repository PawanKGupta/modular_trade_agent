"""Add ml_price_enabled to user_trading_config.

Revision ID: 20260510_ml_price_enabled
Revises: 20260508_ml_through
Create Date: 2026-05-10
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260510_ml_price_enabled"
down_revision = "20260508_ml_through"
branch_labels = None
depends_on = None

_TABLE = "user_trading_config"
_COL = "ml_price_enabled"


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
        sa.Column(_COL, sa.Boolean(), nullable=False, server_default=sa.false()),
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
