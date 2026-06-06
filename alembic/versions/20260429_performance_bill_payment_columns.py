# ruff: noqa
"""Razorpay order / payment tracking on monthly performance bills.

Revision ID: 20260429_perf_bill_pay
Revises: 20260428_perf_fee_billing
Create Date: 2026-04-29
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260429_perf_bill_pay"
down_revision = "20260428_perf_fee_billing"
branch_labels = None
depends_on = None

_TABLE = "monthly_performance_bills"
_COLS = (
    ("razorpay_order_id", sa.String(128), True),
    ("razorpay_payment_id", sa.String(128), True),
    ("paid_at", sa.DateTime(), True),
)


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if _TABLE not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(_TABLE)}
    for name, typ, nullable in _COLS:
        if name not in cols:
            op.add_column(_TABLE, sa.Column(name, typ, nullable=nullable))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if _TABLE not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(_TABLE)}
    for name, _, _ in reversed(_COLS):
        if name in cols:
            op.drop_column(_TABLE, name)
