# ruff: noqa
"""add_trade_mode_to_orders

Revision ID: 80eb0b3dcf5a
Revises: 20250117_migrate_positions_to_full_symbols
Create Date: 2025-12-23 20:12:58.907640+00:00
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "80eb0b3dcf5a"
down_revision = "a1b2c3d4e5f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add trade_mode column to Orders table (Phase 0.1)"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "orders" not in existing_tables:
        return

    orders_columns = [col["name"] for col in inspector.get_columns("orders")]

    # Add trade_mode column if it doesn't exist
    if "trade_mode" not in orders_columns:
        # Phase 0.1: Add trade_mode as nullable for backward compatibility
        # Legacy orders will have NULL trade_mode
        # New orders will have trade_mode populated from UserSettings
        op.add_column(
            "orders",
            sa.Column("trade_mode", sa.String(16), nullable=True),
        )

        # Create index on trade_mode for efficient filtering
        op.create_index("ix_orders_trade_mode", "orders", ["trade_mode"])


def downgrade() -> None:
    """Remove trade_mode column from Orders table"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "orders" not in existing_tables:
        return

    orders_columns = [col["name"] for col in inspector.get_columns("orders")]

    # Drop index first
    if "trade_mode" in orders_columns:
        try:
            op.drop_index("ix_orders_trade_mode", table_name="orders")
        except Exception:
            # Index might not exist, ignore
            pass

        # Drop column
        op.drop_column("orders", "trade_mode")
