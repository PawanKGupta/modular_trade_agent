"""order_status_simplification_and_unified_reason

Revision ID: 873e86bc5772
Revises: c38b470b20d1
Create Date: 2025-11-23 16:18:45.298540+00:00
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "873e86bc5772"
down_revision = "c38b470b20d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Order status simplification and unified reason field migration

    Changes:
    1. Add unified 'reason' field (replaces failure_reason, rejection_reason, cancelled_reason)
    2. Migrate existing reason data to unified field
    3. Migrate status values:
       - AMO → PENDING
       - PENDING_EXECUTION → PENDING
       - RETRY_PENDING → FAILED
       - REJECTED → FAILED
       - SELL → PENDING (for orders with side='sell')
    """
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "orders" not in existing_tables:
        return

    orders_columns = [col["name"] for col in inspector.get_columns("orders")]

    # Step 1: Add unified reason field
    if "reason" not in orders_columns:
        op.add_column("orders", sa.Column("reason", sa.String(512), nullable=True))

    # Step 2: Migrate existing reason data to unified field
    # Migrate failure_reason → reason
    if "failure_reason" in orders_columns:
        op.execute(
            sa.text(
                """
            UPDATE orders
            SET reason = failure_reason
            WHERE failure_reason IS NOT NULL AND reason IS NULL
        """
            )
        )

    # Migrate rejection_reason → reason
    if "rejection_reason" in orders_columns:
        op.execute(
            sa.text(
                """
            UPDATE orders
            SET reason = rejection_reason
            WHERE rejection_reason IS NOT NULL AND reason IS NULL
        """
            )
        )

    # Migrate cancelled_reason → reason
    if "cancelled_reason" in orders_columns:
        op.execute(
            sa.text(
                """
            UPDATE orders
            SET reason = cancelled_reason
            WHERE cancelled_reason IS NOT NULL AND reason IS NULL
        """
            )
        )

    # Step 3: Migrate status values
    # Note: For SQLite, status is stored as string, so we can update directly
    # For other databases with enum types, this might need special handling

    # AMO → PENDING
    op.execute(
        sa.text(
            """
        UPDATE orders
        SET status = 'pending'
        WHERE status = 'amo'
    """
        )
    )

    # PENDING_EXECUTION → PENDING
    op.execute(
        sa.text(
            """
        UPDATE orders
        SET status = 'pending'
        WHERE status = 'pending_execution'
    """
        )
    )

    # RETRY_PENDING → FAILED
    op.execute(
        sa.text(
            """
        UPDATE orders
        SET status = 'failed'
        WHERE status = 'retry_pending'
    """
        )
    )

    # REJECTED → FAILED
    op.execute(
        sa.text(
            """
        UPDATE orders
        SET status = 'failed'
        WHERE status = 'rejected'
    """
        )
    )

    # SELL → PENDING (sell orders use side='sell' + status, not separate SELL status)
    op.execute(
        sa.text(
            """
        UPDATE orders
        SET status = 'pending'
        WHERE status = 'sell'
    """
        )
    )


def downgrade() -> None:
    """Reverse order status simplification migration

    Note: This may lose data if reason field had unified data from multiple sources.
    """
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "orders" not in existing_tables:
        return

    orders_columns = [col["name"] for col in inspector.get_columns("orders")]

    # Reverse status migrations (approximate - may not be 100% accurate)
    # PENDING → AMO (for orders placed before migration date)
    # Note: We can't perfectly distinguish AMO vs PENDING_EXECUTION
    op.execute(
        sa.text(
            """
        UPDATE orders
        SET status = 'amo'
        WHERE status = 'pending' AND side = 'buy'
    """
        )
    )

    # FAILED → RETRY_PENDING (for orders with first_failed_at)
    # Note: We can't perfectly distinguish RETRY_PENDING vs REJECTED vs FAILED
    op.execute(
        sa.text(
            """
        UPDATE orders
        SET status = 'retry_pending'
        WHERE status = 'failed' AND first_failed_at IS NOT NULL
    """
        )
    )

    # Restore old reason fields from unified reason (if data was preserved)
    # Note: This is approximate - we can't know which field it came from
    if "failure_reason" in orders_columns and "reason" in orders_columns:
        op.execute(
            sa.text(
                """
            UPDATE orders
            SET failure_reason = reason
            WHERE reason IS NOT NULL
                AND failure_reason IS NULL
                AND status IN ('failed', 'retry_pending')
        """
            )
        )

    if "rejection_reason" in orders_columns and "reason" in orders_columns:
        op.execute(
            sa.text(
                """
            UPDATE orders
            SET rejection_reason = reason
            WHERE reason IS NOT NULL
                AND rejection_reason IS NULL
                AND reason LIKE 'Broker rejected:%'
        """
            )
        )

    if "cancelled_reason" in orders_columns and "reason" in orders_columns:
        op.execute(
            sa.text(
                """
            UPDATE orders
            SET cancelled_reason = reason
            WHERE reason IS NOT NULL AND cancelled_reason IS NULL AND status = 'cancelled'
        """
            )
        )

    # Remove unified reason field
    if "reason" in orders_columns:
        op.drop_column("orders", "reason")
