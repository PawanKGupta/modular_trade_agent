"""add_fills_table

Revision ID: a1b2c3d4e5f7
Revises: g1h2i3j4k5l6
Create Date: 2025-12-26 11:45:00.000000+00:00
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "g1h2i3j4k5l6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add fills table for partial order execution tracking (Phase 1)"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "fills" in existing_tables:
        print("⚠ fills table already exists, skipping creation")
        return

    op.create_table(
        "fills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("fill_value", sa.Float(), nullable=False),
        sa.Column("charges", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("filled_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("broker_fill_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name="fk_fills_order_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_fills_user_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("broker_fill_id", name="uq_fills_broker_fill_id"),
    )
    op.create_index("ix_fills_order_id", "fills", ["order_id"], unique=False)
    op.create_index("ix_fills_user_id", "fills", ["user_id"], unique=False)
    op.create_index("ix_fills_order_filled_at", "fills", ["order_id", "filled_at"], unique=False)
    op.create_index("ix_fills_user_filled_at", "fills", ["user_id", "filled_at"], unique=False)
    op.create_index("ix_fills_filled_at", "fills", ["filled_at"], unique=False)

    print("✓ Created fills table with indexes")


def downgrade() -> None:
    """Remove fills table"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "fills" not in existing_tables:
        return

    op.drop_index("ix_fills_filled_at", table_name="fills")
    op.drop_index("ix_fills_user_filled_at", table_name="fills")
    op.drop_index("ix_fills_order_filled_at", table_name="fills")
    op.drop_index("ix_fills_user_id", table_name="fills")
    op.drop_index("ix_fills_order_id", table_name="fills")
    op.drop_table("fills")

    print("✓ Removed fills table")
