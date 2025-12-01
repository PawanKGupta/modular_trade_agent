"""add_metadata_to_orders

Revision ID: 06c37167974d
Revises: 0002_phase1
Create Date: 2025-11-16 20:14:24.176098+00:00
"""

import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

from alembic import op

# revision identifiers, used by Alembic.
revision = "06c37167974d"
down_revision = "0002_phase1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add metadata JSON column to orders table
    from sqlalchemy import inspect

    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "orders" in existing_tables:
        orders_columns = [col["name"] for col in inspector.get_columns("orders")]
        if "metadata" not in orders_columns:
            # Use JSON type for SQLite (stored as TEXT)
            if isinstance(op.get_bind().dialect, sqlite.dialect):
                op.add_column("orders", sa.Column("metadata", sa.JSON(), nullable=True))
            else:
                op.add_column("orders", sa.Column("metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove metadata column from orders table
    from sqlalchemy import inspect

    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "orders" in existing_tables:
        orders_columns = [col["name"] for col in inspector.get_columns("orders")]
        if "metadata" in orders_columns:
            op.drop_column("orders", "metadata")
