"""add_exit_details_to_positions

Revision ID: e4bec30fd3ca
Revises: 80eb0b3dcf5a
Create Date: 2025-12-23 20:22:27.217965+00:00
"""
import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op


# revision identifiers, used by Alembic.
revision = "e4bec30fd3ca"
down_revision = "80eb0b3dcf5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add exit detail columns to Positions table (Phase 0.2)"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "positions" not in existing_tables:
        return

    positions_columns = [col["name"] for col in inspector.get_columns("positions")]

    # Add exit detail columns if they don't exist
    if "exit_price" not in positions_columns:
        op.add_column("positions", sa.Column("exit_price", sa.Float(), nullable=True))

    if "exit_reason" not in positions_columns:
        op.add_column("positions", sa.Column("exit_reason", sa.String(64), nullable=True))

    if "exit_rsi" not in positions_columns:
        op.add_column("positions", sa.Column("exit_rsi", sa.Float(), nullable=True))

    if "realized_pnl" not in positions_columns:
        op.add_column("positions", sa.Column("realized_pnl", sa.Float(), nullable=True))

    if "realized_pnl_pct" not in positions_columns:
        op.add_column("positions", sa.Column("realized_pnl_pct", sa.Float(), nullable=True))

    if "sell_order_id" not in positions_columns:
        op.add_column(
            "positions",
            sa.Column("sell_order_id", sa.Integer(), nullable=True),
        )
        # Add foreign key constraint
        try:
            op.create_foreign_key(
                "fk_positions_sell_order_id",
                "positions",
                "orders",
                ["sell_order_id"],
                ["id"],
            )
        except Exception:
            # Foreign key might already exist or not supported (SQLite)
            pass

    # Create index on exit_reason for analytics queries
    if "exit_reason" in positions_columns or "exit_reason" in [
        col["name"] for col in inspector.get_columns("positions")
    ]:
        try:
            op.create_index("ix_positions_exit_reason", "positions", ["exit_reason"])
        except Exception:
            # Index might already exist
            pass


def downgrade() -> None:
    """Remove exit detail columns from Positions table"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "positions" not in existing_tables:
        return

    positions_columns = [col["name"] for col in inspector.get_columns("positions")]

    # Drop index first
    try:
        op.drop_index("ix_positions_exit_reason", table_name="positions")
    except Exception:
        # Index might not exist
        pass

    # Drop foreign key constraint
    try:
        op.drop_constraint("fk_positions_sell_order_id", "positions", type_="foreignkey")
    except Exception:
        # Constraint might not exist
        pass

    # Drop columns
    if "sell_order_id" in positions_columns:
        op.drop_column("positions", "sell_order_id")

    if "realized_pnl_pct" in positions_columns:
        op.drop_column("positions", "realized_pnl_pct")

    if "realized_pnl" in positions_columns:
        op.drop_column("positions", "realized_pnl")

    if "exit_rsi" in positions_columns:
        op.drop_column("positions", "exit_rsi")

    if "exit_reason" in positions_columns:
        op.drop_column("positions", "exit_reason")

    if "exit_price" in positions_columns:
        op.drop_column("positions", "exit_price")

