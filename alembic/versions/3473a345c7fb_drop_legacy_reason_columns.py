"""drop_legacy_reason_columns

Revision ID: 3473a345c7fb
Revises: 873e86bc5772
Create Date: 2025-11-23 20:00:00.000000+00:00
"""

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import sqlite

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

    # Check if we need to drop any columns
    columns_to_drop = []
    if "failure_reason" in orders_columns:
        columns_to_drop.append("failure_reason")
    if "rejection_reason" in orders_columns:
        columns_to_drop.append("rejection_reason")
    if "cancelled_reason" in orders_columns:
        columns_to_drop.append("cancelled_reason")

    if not columns_to_drop:
        return

    # SQLite requires batch mode for dropping columns
    if isinstance(conn.dialect, sqlite.dialect):
        with op.batch_alter_table("orders", schema=None) as batch_op:
            for col_name in columns_to_drop:
                batch_op.drop_column(col_name)
    else:
        # For PostgreSQL and other databases, drop columns directly
        for col_name in columns_to_drop:
            op.drop_column("orders", col_name)


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

    # Check which columns need to be added
    columns_to_add = []
    if "failure_reason" not in orders_columns:
        columns_to_add.append(("failure_reason", sa.String(256)))
    if "rejection_reason" not in orders_columns:
        columns_to_add.append(("rejection_reason", sa.String(256)))
    if "cancelled_reason" not in orders_columns:
        columns_to_add.append(("cancelled_reason", sa.String(256)))

    if not columns_to_add:
        return

    # SQLite requires batch mode for adding columns (though adding is usually fine)
    if isinstance(conn.dialect, sqlite.dialect):
        with op.batch_alter_table("orders", schema=None) as batch_op:
            for col_name, col_type in columns_to_add:
                batch_op.add_column(sa.Column(col_name, col_type, nullable=True))
    else:
        # For PostgreSQL and other databases, add columns directly
        for col_name, col_type in columns_to_add:
            op.add_column("orders", sa.Column(col_name, col_type, nullable=True))
