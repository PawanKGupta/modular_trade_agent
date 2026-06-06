# ruff: noqa
"""Encrypted Razorpay secrets on billing_admin_settings

Revision ID: 20260422_billing_rzp_enc
Revises: 20260419_notify_prefs_billing
Create Date: 2026-04-22
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260422_billing_rzp_enc"
down_revision = "20260419_notify_prefs_billing"
branch_labels = None
depends_on = None

_TABLE = "billing_admin_settings"
_COLS = (
    ("razorpay_key_id", "VARCHAR(128) NULL"),
    ("razorpay_key_secret_encrypted", "BYTEA NULL"),
    ("razorpay_webhook_secret_encrypted", "BYTEA NULL"),
)


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name
    inspector = inspect(conn)
    if _TABLE not in inspector.get_table_names():
        return
    if dialect == "postgresql":
        for name, ddl in _COLS:
            op.execute(sa.text(f'ALTER TABLE "{_TABLE}" ADD COLUMN IF NOT EXISTS "{name}" {ddl}'))
        return
    cols = {c["name"] for c in inspector.get_columns(_TABLE)}
    if "razorpay_key_id" not in cols:
        op.add_column(_TABLE, sa.Column("razorpay_key_id", sa.String(128), nullable=True))
    if "razorpay_key_secret_encrypted" not in cols:
        op.add_column(
            _TABLE, sa.Column("razorpay_key_secret_encrypted", sa.LargeBinary(), nullable=True)
        )
    if "razorpay_webhook_secret_encrypted" not in cols:
        op.add_column(
            _TABLE, sa.Column("razorpay_webhook_secret_encrypted", sa.LargeBinary(), nullable=True)
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if _TABLE not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(_TABLE)}
    for name, _ in reversed(_COLS):
        if name in cols:
            op.drop_column(_TABLE, name)
