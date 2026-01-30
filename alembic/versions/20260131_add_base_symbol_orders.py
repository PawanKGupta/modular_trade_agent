"""add base_symbol to orders and unique index for active sells

Revision ID: 20260131_add_base_symbol_orders
Revises:
Create Date: 2026-01-31 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260131_add_base_symbol_orders"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add nullable base_symbol column to orders
    op.add_column("orders", sa.Column("base_symbol", sa.String(length=32), nullable=True))

    # Backfill base_symbol from existing symbol column using split on '-'
    # This will set base_symbol = upper(split_part(symbol,'-',1))
    op.execute(
        "UPDATE orders SET base_symbol = upper(split_part(symbol, '-', 1)) "
        "WHERE base_symbol IS NULL"
    )

    # Create index on base_symbol for lookups
    op.create_index("ix_orders_base_symbol", "orders", ["base_symbol"])

    # Clean up duplicates before creating unique constraint:
    # For each user+base_symbol+status combination with duplicates, keep the most recent (max id)
    # and mark older ones as cancelled
    op.execute(
        """
    WITH duplicates AS (
        SELECT user_id, base_symbol, status, array_agg(id ORDER BY placed_at DESC) as ids
        FROM orders
        WHERE status IN ('pending','ongoing')
        GROUP BY user_id, base_symbol, status
        HAVING COUNT(*) > 1
    )
    UPDATE orders o
    SET status = 'cancelled', reason = 'Cancelled duplicate pending sell during migration'
    WHERE id IN (
        SELECT unnest(ids[2:])
        FROM duplicates d
        WHERE o.user_id = d.user_id AND o.base_symbol = d.base_symbol AND o.status = d.status
    );
    """
    )

    # Create partial unique index to ensure one active sell per user+base_symbol
    # status stored as text enum; ensure conditions match stored values
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_user_base_symbol_active "
        "ON orders (user_id, base_symbol) WHERE status IN ('pending','ongoing')"  # noqa: E501
    )


def downgrade():
    # Drop unique index and base_symbol column
    op.execute("DROP INDEX IF EXISTS uq_orders_user_base_symbol_active")
    op.drop_index("ix_orders_base_symbol", table_name="orders")
    op.drop_column("orders", "base_symbol")
