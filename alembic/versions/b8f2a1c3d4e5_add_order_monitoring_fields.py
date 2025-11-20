"""add_order_monitoring_fields

Revision ID: b8f2a1c3d4e5
Revises: a17c57ecf620
Create Date: 2025-01-XX 00:00:00.000000+00:00
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "b8f2a1c3d4e5"
down_revision = "a17c57ecf620"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add order monitoring fields and new status values"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "orders" not in existing_tables:
        return

    orders_columns = [col["name"] for col in inspector.get_columns("orders")]

    # Add new status values to OrderStatus enum
    # Note: For SQLite, we'll use string columns. For PostgreSQL, we'd alter the enum type.
    # Since we're using string-based enums, we just need to add the columns.

    # Failure and retry tracking fields
    if "failure_reason" not in orders_columns:
        op.add_column("orders", sa.Column("failure_reason", sa.String(256), nullable=True))

    if "first_failed_at" not in orders_columns:
        op.add_column("orders", sa.Column("first_failed_at", sa.DateTime(), nullable=True))

    if "last_retry_attempt" not in orders_columns:
        op.add_column("orders", sa.Column("last_retry_attempt", sa.DateTime(), nullable=True))

    if "retry_count" not in orders_columns:
        op.add_column(
            "orders", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0")
        )

    if "rejection_reason" not in orders_columns:
        op.add_column("orders", sa.Column("rejection_reason", sa.String(256), nullable=True))

    if "cancelled_reason" not in orders_columns:
        op.add_column("orders", sa.Column("cancelled_reason", sa.String(256), nullable=True))

    if "last_status_check" not in orders_columns:
        op.add_column("orders", sa.Column("last_status_check", sa.DateTime(), nullable=True))

    # Execution tracking fields
    if "execution_price" not in orders_columns:
        op.add_column("orders", sa.Column("execution_price", sa.Float(), nullable=True))

    if "execution_qty" not in orders_columns:
        op.add_column("orders", sa.Column("execution_qty", sa.Float(), nullable=True))

    if "execution_time" not in orders_columns:
        op.add_column("orders", sa.Column("execution_time", sa.DateTime(), nullable=True))

    # Add index for status and last_status_check (for efficient querying)
    # Check if index already exists
    existing_indexes = [idx["name"] for idx in inspector.get_indexes("orders")]
    if "ix_orders_status_last_check" not in existing_indexes:
        try:
            op.create_index(
                "ix_orders_status_last_check",
                "orders",
                ["status", "last_status_check"],
            )
        except Exception:
            # Index might already exist or creation might fail - continue
            pass


def downgrade() -> None:
    """Remove order monitoring fields"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "orders" not in existing_tables:
        return

    orders_columns = [col["name"] for col in inspector.get_columns("orders")]

    # Drop index
    existing_indexes = [idx["name"] for idx in inspector.get_indexes("orders")]
    if "ix_orders_status_last_check" in existing_indexes:
        try:
            op.drop_index("ix_orders_status_last_check", table_name="orders")
        except Exception:
            pass

    # Drop columns in reverse order
    if "execution_time" in orders_columns:
        op.drop_column("orders", "execution_time")

    if "execution_qty" in orders_columns:
        op.drop_column("orders", "execution_qty")

    if "execution_price" in orders_columns:
        op.drop_column("orders", "execution_price")

    if "last_status_check" in orders_columns:
        op.drop_column("orders", "last_status_check")

    if "cancelled_reason" in orders_columns:
        op.drop_column("orders", "cancelled_reason")

    if "rejection_reason" in orders_columns:
        op.drop_column("orders", "rejection_reason")

    if "retry_count" in orders_columns:
        op.drop_column("orders", "retry_count")

    if "last_retry_attempt" in orders_columns:
        op.drop_column("orders", "last_retry_attempt")

    if "first_failed_at" in orders_columns:
        op.drop_column("orders", "first_failed_at")

    if "failure_reason" in orders_columns:
        op.drop_column("orders", "failure_reason")
