"""migrate_fills_table_schema

Revision ID: b9c0cf7b482d
Revises: 68601da84070
Create Date: 2025-12-29 09:19:16.025115+00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "b9c0cf7b482d"
down_revision = "68601da84070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Migrate existing fills table to new schema with additional columns"""
    conn = op.get_bind()
    inspector = inspect(conn)

    # Check if fills table exists
    existing_tables = inspector.get_table_names()
    if "fills" not in existing_tables:
        print("⚠ fills table does not exist, skipping migration")
        return

    # Get existing columns
    existing_columns = {col["name"] for col in inspector.get_columns("fills")}

    # Rename old columns to match new schema
    if "qty" in existing_columns and "quantity" not in existing_columns:
        op.alter_column("fills", "qty", new_column_name="quantity")
        print("✓ Renamed qty -> quantity")

    if "ts" in existing_columns and "filled_at" not in existing_columns:
        op.alter_column("fills", "ts", new_column_name="filled_at")
        print("✓ Renamed ts -> filled_at")

    # Add new columns if they don't exist
    if "user_id" not in existing_columns:
        op.add_column("fills", sa.Column("user_id", sa.Integer(), nullable=True))
        # Populate user_id from orders table
        op.execute(
            """
            UPDATE fills
            SET user_id = orders.user_id
            FROM orders
            WHERE fills.order_id = orders.id
        """
        )
        # Make it non-nullable after population
        op.alter_column("fills", "user_id", nullable=False)
        op.create_foreign_key("fk_fills_user_id", "fills", "users", ["user_id"], ["id"])
        op.create_index("ix_fills_user_id", "fills", ["user_id"])
        print("✓ Added user_id column")

    if "fill_value" not in existing_columns:
        op.add_column("fills", sa.Column("fill_value", sa.Float(), nullable=True))
        # Calculate fill_value from quantity * price
        op.execute("UPDATE fills SET fill_value = quantity * price")
        op.alter_column("fills", "fill_value", nullable=False)
        print("✓ Added fill_value column")

    if "charges" not in existing_columns:
        op.add_column(
            "fills", sa.Column("charges", sa.Float(), nullable=False, server_default="0.0")
        )
        print("✓ Added charges column")

    if "created_at" not in existing_columns:
        op.add_column("fills", sa.Column("created_at", sa.DateTime(), nullable=True))
        # Set created_at to filled_at for existing records
        op.execute("UPDATE fills SET created_at = filled_at")
        op.alter_column("fills", "created_at", nullable=False)
        print("✓ Added created_at column")

    if "broker_fill_id" not in existing_columns:
        op.add_column("fills", sa.Column("broker_fill_id", sa.String(length=64), nullable=True))
        op.create_unique_constraint("uq_fills_broker_fill_id", "fills", ["broker_fill_id"])
        print("✓ Added broker_fill_id column")

    # Create additional indexes if they don't exist
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("fills")}

    if "ix_fills_order_filled_at" not in existing_indexes:
        op.create_index("ix_fills_order_filled_at", "fills", ["order_id", "filled_at"])

    if "ix_fills_user_filled_at" not in existing_indexes:
        op.create_index("ix_fills_user_filled_at", "fills", ["user_id", "filled_at"])

    if "ix_fills_filled_at" not in existing_indexes:
        op.create_index("ix_fills_filled_at", "fills", ["filled_at"])

    print("✓ Fills table schema migration completed")


def downgrade() -> None:
    """Revert fills table to old schema"""
    conn = op.get_bind()
    inspector = inspect(conn)

    existing_tables = inspector.get_table_names()
    if "fills" not in existing_tables:
        return

    existing_columns = {col["name"] for col in inspector.get_columns("fills")}
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("fills")}

    # Drop new indexes
    if "ix_fills_filled_at" in existing_indexes:
        op.drop_index("ix_fills_filled_at", table_name="fills")
    if "ix_fills_user_filled_at" in existing_indexes:
        op.drop_index("ix_fills_user_filled_at", table_name="fills")
    if "ix_fills_order_filled_at" in existing_indexes:
        op.drop_index("ix_fills_order_filled_at", table_name="fills")

    # Drop new columns
    if "broker_fill_id" in existing_columns:
        op.drop_constraint("uq_fills_broker_fill_id", "fills", type_="unique")
        op.drop_column("fills", "broker_fill_id")

    if "created_at" in existing_columns:
        op.drop_column("fills", "created_at")

    if "charges" in existing_columns:
        op.drop_column("fills", "charges")

    if "fill_value" in existing_columns:
        op.drop_column("fills", "fill_value")

    if "user_id" in existing_columns:
        op.drop_index("ix_fills_user_id", table_name="fills")
        op.drop_constraint("fk_fills_user_id", "fills", type_="foreignkey")
        op.drop_column("fills", "user_id")

    # Rename columns back
    if "filled_at" in existing_columns:
        op.alter_column("fills", "filled_at", new_column_name="ts")

    if "quantity" in existing_columns:
        op.alter_column("fills", "quantity", new_column_name="qty")

    print("✓ Fills table reverted to old schema")
