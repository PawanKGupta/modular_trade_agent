"""add_pnl_calculation_audit

Revision ID: e3c7a9ca471c
Revises: fa4e76102303
Create Date: 2025-12-23 20:45:00.000000+00:00
"""
import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op


# revision identifiers, used by Alembic.
revision = "e3c7a9ca471c"
down_revision = "fa4e76102303"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create pnl_calculation_audit table (Phase 0.5)"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "pnl_calculation_audit" in existing_tables:
        return

    # Create pnl_calculation_audit table
    op.create_table(
        "pnl_calculation_audit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("calculation_type", sa.String(32), nullable=False),
        sa.Column("date_range_start", sa.Date(), nullable=True),
        sa.Column("date_range_end", sa.Date(), nullable=True),
        sa.Column("positions_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("orders_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pnl_records_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pnl_records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_message", sa.String(512), nullable=True),
        sa.Column("triggered_by", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index("ix_pnl_calculation_audit_user_id", "pnl_calculation_audit", ["user_id"])
    op.create_index(
        "ix_pnl_audit_user_created",
        "pnl_calculation_audit",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    """Drop pnl_calculation_audit table"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "pnl_calculation_audit" not in existing_tables:
        return

    # Drop indexes first
    try:
        op.drop_index("ix_pnl_audit_user_created", table_name="pnl_calculation_audit")
    except Exception:
        pass

    try:
        op.drop_index("ix_pnl_calculation_audit_user_id", table_name="pnl_calculation_audit")
    except Exception:
        pass

    # Drop table
    op.drop_table("pnl_calculation_audit")
