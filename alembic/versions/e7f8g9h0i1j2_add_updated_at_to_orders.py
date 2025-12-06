"""add_updated_at_to_orders

Revision ID: e7f8g9h0i1j2
Revises: d1e2f3a4b5c6
Create Date: 2025-12-06 23:50:00.000000+00:00
"""
import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "e7f8g9h0i1j2"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add updated_at column to Orders table"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "orders" not in existing_tables:
        return

    orders_columns = [col["name"] for col in inspector.get_columns("orders")]

    # Add updated_at column if it doesn't exist
    if "updated_at" not in orders_columns:
        # SQLite doesn't support adding NOT NULL column with default in one step
        # So we add it as nullable first, then update values, then make it NOT NULL
        from sqlalchemy.dialects import sqlite

        if isinstance(conn.dialect, sqlite.dialect):
            # For SQLite: Add as nullable, update values, then recreate table with NOT NULL
            # Actually, SQLite doesn't support ALTER COLUMN, so we'll add as nullable
            # and the application code will ensure it's always set
            op.add_column(
                "orders",
                sa.Column("updated_at", sa.DateTime(), nullable=True),
            )

            # For existing records, set updated_at to placed_at (or current timestamp)
            op.execute(
                sa.text("""
                    UPDATE orders
                    SET updated_at = COALESCE(placed_at, datetime('now'))
                    WHERE updated_at IS NULL
                """)
            )
        else:
            # For PostgreSQL and other databases: Can add with NOT NULL and default
            op.add_column(
                "orders",
                sa.Column(
                    "updated_at",
                    sa.DateTime(),
                    nullable=False,
                    server_default=sa.text("CURRENT_TIMESTAMP"),
                ),
            )

            # For existing records, set updated_at to placed_at (or current timestamp)
            op.execute(
                sa.text("""
                    UPDATE orders
                    SET updated_at = COALESCE(placed_at, CURRENT_TIMESTAMP)
                    WHERE updated_at IS NULL
                """)
            )

        # Create index on updated_at for better query performance
        op.create_index("ix_orders_updated_at", "orders", ["updated_at"])


def downgrade() -> None:
    """Remove updated_at column from Orders table"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "orders" not in existing_tables:
        return

    orders_columns = [col["name"] for col in inspector.get_columns("orders")]

    # Drop index first
    if "updated_at" in orders_columns:
        try:
            op.drop_index("ix_orders_updated_at", table_name="orders")
        except Exception:
            # Index might not exist, ignore
            pass

        # Drop column
        op.drop_column("orders", "updated_at")

