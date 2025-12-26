"""add_rejection_reason_to_orders

Revision ID: f1a2b3c4d5e6
Revises: 80eb0b3dcf5a
Create Date: 2025-12-26 11:30:00.000000+00:00
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "80eb0b3dcf5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add rejection_reason column to Orders table"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "orders" not in existing_tables:
        return

    orders_columns = [col["name"] for col in inspector.get_columns("orders")]

    if "rejection_reason" not in orders_columns:
        op.add_column(
            "orders",
            sa.Column("rejection_reason", sa.String(length=512), nullable=True),
        )
        print("✓ Added rejection_reason column to orders table")


def downgrade() -> None:
    """Remove rejection_reason column from Orders table"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "orders" not in existing_tables:
        return

    orders_columns = [col["name"] for col in inspector.get_columns("orders")]

    if "rejection_reason" in orders_columns:
        op.drop_column("orders", "rejection_reason")
        print("✓ Removed rejection_reason column from orders table")
