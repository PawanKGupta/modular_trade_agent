"""add_order_id_indexes_for_performance

Revision ID: c9d8e7f6g5h6
Revises: b8f2a1c3d4e5
Create Date: 2025-01-XX 00:00:00.000000+00:00
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "c9d8e7f6g5h6"
down_revision = "b8f2a1c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add indexes for broker_order_id and order_id for query performance"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "orders" not in existing_tables:
        return

    # Get existing indexes
    existing_indexes = [idx["name"] for idx in inspector.get_indexes("orders")]

    # Add index for broker_order_id (used in get_by_broker_order_id queries)
    if "ix_orders_broker_order_id" not in existing_indexes:
        try:
            op.create_index(
                "ix_orders_broker_order_id",
                "orders",
                ["broker_order_id"],
                unique=False,
            )
        except Exception:
            # Index might already exist or creation might fail - continue
            pass

    # Add index for order_id (used in get_by_order_id queries)
    if "ix_orders_order_id" not in existing_indexes:
        try:
            op.create_index(
                "ix_orders_order_id",
                "orders",
                ["order_id"],
                unique=False,
            )
        except Exception:
            # Index might already exist or creation might fail - continue
            pass

    # Add composite index for user_id + broker_order_id (common query pattern)
    if "ix_orders_user_broker_order_id" not in existing_indexes:
        try:
            op.create_index(
                "ix_orders_user_broker_order_id",
                "orders",
                ["user_id", "broker_order_id"],
                unique=False,
            )
        except Exception:
            # Index might already exist or creation might fail - continue
            pass

    # Add composite index for user_id + order_id (common query pattern)
    if "ix_orders_user_order_id" not in existing_indexes:
        try:
            op.create_index(
                "ix_orders_user_order_id",
                "orders",
                ["user_id", "order_id"],
                unique=False,
            )
        except Exception:
            # Index might already exist or creation might fail - continue
            pass


def downgrade() -> None:
    """Remove indexes for broker_order_id and order_id"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "orders" not in existing_tables:
        return

    existing_indexes = [idx["name"] for idx in inspector.get_indexes("orders")]

    # Remove indexes if they exist
    if "ix_orders_broker_order_id" in existing_indexes:
        try:
            op.drop_index("ix_orders_broker_order_id", table_name="orders")
        except Exception:
            pass

    if "ix_orders_order_id" in existing_indexes:
        try:
            op.drop_index("ix_orders_order_id", table_name="orders")
        except Exception:
            pass

    if "ix_orders_user_broker_order_id" in existing_indexes:
        try:
            op.drop_index("ix_orders_user_broker_order_id", table_name="orders")
        except Exception:
            pass

    if "ix_orders_user_order_id" in existing_indexes:
        try:
            op.drop_index("ix_orders_user_order_id", table_name="orders")
        except Exception:
            pass

