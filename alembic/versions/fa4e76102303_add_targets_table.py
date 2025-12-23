"""add_targets_table

Revision ID: fa4e76102303
Revises: d7377ebd13da
Create Date: 2025-12-23 20:35:18.106808+00:00
"""
import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op


# revision identifiers, used by Alembic.
revision = "fa4e76102303"
down_revision = "d7377ebd13da"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create targets table (Phase 0.4)"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "targets" in existing_tables:
        return

    # Create targets table
    op.create_table(
        "targets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("position_id", sa.Integer(), nullable=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("target_price", sa.Float(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("distance_to_target", sa.Float(), nullable=True),
        sa.Column("distance_to_target_absolute", sa.Float(), nullable=True),
        sa.Column("target_type", sa.String(32), nullable=False, server_default="ema9"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("trade_mode", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("achieved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index("ix_targets_user_id", "targets", ["user_id"])
    op.create_index("ix_targets_symbol", "targets", ["symbol"])
    op.create_index(
        "ix_targets_user_symbol_active", "targets", ["user_id", "symbol", "is_active"]
    )
    op.create_index("ix_targets_position", "targets", ["position_id"])


def downgrade() -> None:
    """Drop targets table"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "targets" not in existing_tables:
        return

    # Drop indexes first
    try:
        op.drop_index("ix_targets_position", table_name="targets")
    except Exception:
        pass

    try:
        op.drop_index("ix_targets_user_symbol_active", table_name="targets")
    except Exception:
        pass

    try:
        op.drop_index("ix_targets_symbol", table_name="targets")
    except Exception:
        pass

    try:
        op.drop_index("ix_targets_user_id", table_name="targets")
    except Exception:
        pass

    # Drop table
    op.drop_table("targets")
