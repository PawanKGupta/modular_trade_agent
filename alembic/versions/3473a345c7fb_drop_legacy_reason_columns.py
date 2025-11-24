"""drop_legacy_reason_columns

Revision ID: 3473a345c7fb
Revises: 873e86bc5772
Create Date: 2025-11-23 20:00:00.000000+00:00
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "3473a345c7fb"
down_revision = "873e86bc5772"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop legacy reason columns (failure_reason, rejection_reason, cancelled_reason)

    These columns have been replaced by the unified 'reason' field.
    All data has been migrated to the 'reason' field in the previous migration.
    """
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "orders" not in existing_tables:
        return

    orders_columns = [col["name"] for col in inspector.get_columns("orders")]

    # Drop legacy reason columns
    if "failure_reason" in orders_columns:
        op.drop_column("orders", "failure_reason")

    if "rejection_reason" in orders_columns:
        op.drop_column("orders", "rejection_reason")

    if "cancelled_reason" in orders_columns:
        op.drop_column("orders", "cancelled_reason")


def downgrade() -> None:
    """Restore legacy reason columns (for rollback purposes)

    Note: This will recreate empty columns. Data from 'reason' field
    cannot be automatically split back into the original columns.
    """
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "orders" not in existing_tables:
        return

    orders_columns = [col["name"] for col in inspector.get_columns("orders")]

    # Restore legacy reason columns (empty, as we can't split 'reason' back)
    if "failure_reason" not in orders_columns:
        op.add_column("orders", sa.Column("failure_reason", sa.String(256), nullable=True))

    if "rejection_reason" not in orders_columns:
        op.add_column("orders", sa.Column("rejection_reason", sa.String(256), nullable=True))

    if "cancelled_reason" not in orders_columns:
        op.add_column("orders", sa.Column("cancelled_reason", sa.String(256), nullable=True))
