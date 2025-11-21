"""add_reentry_tracking_fields

Revision ID: c38b470b20d1
Revises: 64bdece9c0f3
Create Date: 2025-11-21 20:27:38.375680+00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import sqlite


# revision identifiers, used by Alembic.
revision = 'c38b470b20d1'
down_revision = '64bdece9c0f3'
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Add reentry tracking fields to Orders and Positions tables"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # Add entry_type to Orders table
    if "orders" in existing_tables:
        orders_columns = [col["name"] for col in inspector.get_columns("orders")]

        if "entry_type" not in orders_columns:
            op.add_column("orders", sa.Column("entry_type", sa.String(32), nullable=True))

    # Add reentry tracking fields to Positions table
    if "positions" in existing_tables:
        positions_columns = [col["name"] for col in inspector.get_columns("positions")]

        if "reentry_count" not in positions_columns:
            op.add_column("positions", sa.Column("reentry_count", sa.Integer(), nullable=False, server_default="0"))

        if "reentries" not in positions_columns:
            # Use JSON type for SQLite (stored as TEXT)
            if isinstance(op.get_bind().dialect, sqlite.dialect):
                op.add_column("positions", sa.Column("reentries", sa.JSON(), nullable=True))
            else:
                op.add_column("positions", sa.Column("reentries", sa.JSON(), nullable=True))

        if "initial_entry_price" not in positions_columns:
            op.add_column("positions", sa.Column("initial_entry_price", sa.Float(), nullable=True))

        if "last_reentry_price" not in positions_columns:
            op.add_column("positions", sa.Column("last_reentry_price", sa.Float(), nullable=True))

        # Set initial_entry_price to current avg_price for existing positions
        # (copy avg_price to initial_entry_price for backward compatibility)
        op.execute(sa.text("""
            UPDATE positions
            SET initial_entry_price = avg_price
            WHERE initial_entry_price IS NULL AND avg_price IS NOT NULL
        """))


def downgrade() -> None:
    """Remove reentry tracking fields"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # Remove entry_type from Orders table
    if "orders" in existing_tables:
        orders_columns = [col["name"] for col in inspector.get_columns("orders")]
        if "entry_type" in orders_columns:
            op.drop_column("orders", "entry_type")

    # Remove reentry tracking fields from Positions table
    if "positions" in existing_tables:
        positions_columns = [col["name"] for col in inspector.get_columns("positions")]

        if "reentry_count" in positions_columns:
            op.drop_column("positions", "reentry_count")

        if "reentries" in positions_columns:
            op.drop_column("positions", "reentries")

        if "initial_entry_price" in positions_columns:
            op.drop_column("positions", "initial_entry_price")

        if "last_reentry_price" in positions_columns:
            op.drop_column("positions", "last_reentry_price")
