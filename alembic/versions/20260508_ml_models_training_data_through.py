# ruff: noqa
"""Add training_data_through_date to ml_models (incremental training watermark).

Revision ID: 20260508_ml_through
Revises: 20260504_notify_pay_failed
Create Date: 2026-05-08
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260508_ml_through"
down_revision = "20260504_notify_pay_failed"
branch_labels = None
depends_on = None

_TABLE = "ml_models"


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if _TABLE not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(_TABLE)}
    if "training_data_through_date" not in cols:
        op.add_column(
            _TABLE,
            sa.Column("training_data_through_date", sa.Date(), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if _TABLE not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(_TABLE)}
    if "training_data_through_date" in cols:
        op.drop_column(_TABLE, "training_data_through_date")
