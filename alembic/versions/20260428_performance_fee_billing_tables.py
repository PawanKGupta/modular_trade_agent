# ruff: noqa
"""Performance fee billing: carry-forward state, monthly bills, admin settings.

Revision ID: 20260428_perf_fee_billing
Revises: 20260422_billing_rzp_enc
Create Date: 2026-04-28
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260428_perf_fee_billing"
down_revision = "20260422_billing_rzp_enc"
branch_labels = None
depends_on = None

_ADMIN_TABLE = "billing_admin_settings"
_ADMIN_COLS = (
    ("performance_fee_payment_days_after_invoice", sa.Integer(), "15"),
    ("performance_fee_default_percentage", sa.Numeric(8, 4), "10"),
)


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if _ADMIN_TABLE in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns(_ADMIN_TABLE)}
        for name, typ, default in _ADMIN_COLS:
            if name not in cols:
                op.add_column(
                    _ADMIN_TABLE,
                    sa.Column(
                        name,
                        typ,
                        nullable=False,
                        server_default=sa.text(default),
                    ),
                )

    if "user_performance_billing_state" not in inspect(conn).get_table_names():
        op.create_table(
            "user_performance_billing_state",
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
            sa.Column("carry_forward_loss", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    if "monthly_performance_bills" not in inspect(conn).get_table_names():
        op.create_table(
            "monthly_performance_bills",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("bill_month", sa.Date(), nullable=False),
            sa.Column("generated_at", sa.DateTime(), nullable=False),
            sa.Column("due_at", sa.DateTime(), nullable=False),
            sa.Column("previous_carry_forward_loss", sa.Numeric(18, 4), nullable=False),
            sa.Column("current_month_pnl", sa.Numeric(18, 4), nullable=False),
            sa.Column("fee_percentage", sa.Numeric(8, 4), nullable=False),
            sa.Column("chargeable_profit", sa.Numeric(18, 4), nullable=False),
            sa.Column("fee_amount", sa.Numeric(18, 4), nullable=False),
            sa.Column("new_carry_forward_loss", sa.Numeric(18, 4), nullable=False),
            sa.Column("payable_amount", sa.Numeric(18, 4), nullable=False),
            sa.Column(
                "status",
                sa.String(32),
                nullable=False,
                server_default="pending_payment",
            ),
        )
        op.create_index(
            "ix_monthly_performance_bills_user_id", "monthly_performance_bills", ["user_id"]
        )
        op.create_index(
            "ix_monthly_performance_bills_bill_month", "monthly_performance_bills", ["bill_month"]
        )
        op.create_index(
            "uq_perf_bill_user_month",
            "monthly_performance_bills",
            ["user_id", "bill_month"],
            unique=True,
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if "monthly_performance_bills" in tables:
        op.drop_index("uq_perf_bill_user_month", table_name="monthly_performance_bills")
        op.drop_index(
            "ix_monthly_performance_bills_bill_month", table_name="monthly_performance_bills"
        )
        op.drop_index(
            "ix_monthly_performance_bills_user_id", table_name="monthly_performance_bills"
        )
        op.drop_table("monthly_performance_bills")

    if "user_performance_billing_state" in tables:
        op.drop_table("user_performance_billing_state")

    if _ADMIN_TABLE in tables:
        cols = {c["name"] for c in inspector.get_columns(_ADMIN_TABLE)}
        for name, _, _ in reversed(_ADMIN_COLS):
            if name in cols:
                op.drop_column(_ADMIN_TABLE, name)
