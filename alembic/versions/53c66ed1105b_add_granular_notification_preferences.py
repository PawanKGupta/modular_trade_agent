# ruff: noqa
"""add_granular_notification_preferences

Revision ID: 53c66ed1105b
Revises: d8bee4599cff
Create Date: 2025-11-29 20:20:46.090174+00:00
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "53c66ed1105b"
down_revision = "d8bee4599cff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add granular notification event preferences to user_notification_preferences table.

    This migration adds per-event notification preferences, allowing users to control
    which specific trading events trigger notifications. All new preferences default to
    TRUE to maintain backward compatibility (current behavior where all events notify).

    Uses raw SQL for SQLite compatibility (op.add_column() had issues with execution).
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Check if table exists
    if "user_notification_preferences" not in inspector.get_table_names():
        return

    # Get existing columns
    existing_columns = [
        col["name"] for col in inspector.get_columns("user_notification_preferences")
    ]

    # Use raw SQL for SQLite (more reliable than op.add_column())
    # Order event preferences
    # Note: For Postgres, use true/false instead of 1/0; for SQLite we'll use 1/0 and let Postgres convert
    # Actually, let's use IF/ELSE to handle both dialects
    columns_to_add = []
    is_postgres = conn.dialect.name == "postgresql"
    default_true = "TRUE" if is_postgres else "1"
    default_false = "FALSE" if is_postgres else "0"

    if "notify_order_placed" not in existing_columns:
        columns_to_add.append(f"notify_order_placed BOOLEAN DEFAULT {default_true} NOT NULL")
    if "notify_order_rejected" not in existing_columns:
        columns_to_add.append(f"notify_order_rejected BOOLEAN DEFAULT {default_true} NOT NULL")
    if "notify_order_executed" not in existing_columns:
        columns_to_add.append(f"notify_order_executed BOOLEAN DEFAULT {default_true} NOT NULL")
    if "notify_order_cancelled" not in existing_columns:
        columns_to_add.append(f"notify_order_cancelled BOOLEAN DEFAULT {default_true} NOT NULL")
    if "notify_order_modified" not in existing_columns:
        columns_to_add.append(f"notify_order_modified BOOLEAN DEFAULT {default_false} NOT NULL")
    if "notify_retry_queue_added" not in existing_columns:
        columns_to_add.append(f"notify_retry_queue_added BOOLEAN DEFAULT {default_true} NOT NULL")
    if "notify_retry_queue_updated" not in existing_columns:
        columns_to_add.append(f"notify_retry_queue_updated BOOLEAN DEFAULT {default_true} NOT NULL")
    if "notify_retry_queue_removed" not in existing_columns:
        columns_to_add.append(f"notify_retry_queue_removed BOOLEAN DEFAULT {default_true} NOT NULL")
    if "notify_retry_queue_retried" not in existing_columns:
        columns_to_add.append(f"notify_retry_queue_retried BOOLEAN DEFAULT {default_true} NOT NULL")
    if "notify_partial_fill" not in existing_columns:
        columns_to_add.append(f"notify_partial_fill BOOLEAN DEFAULT {default_true} NOT NULL")

    # System event preferences (more granular)
    if "notify_system_errors" not in existing_columns:
        columns_to_add.append(f"notify_system_errors BOOLEAN DEFAULT {default_true} NOT NULL")
    if "notify_system_warnings" not in existing_columns:
        columns_to_add.append(f"notify_system_warnings BOOLEAN DEFAULT {default_false} NOT NULL")
    if "notify_system_info" not in existing_columns:
        columns_to_add.append(f"notify_system_info BOOLEAN DEFAULT {default_false} NOT NULL")

    # Execute all ALTER TABLE statements
    # Use op.execute() which handles transactions properly in Alembic context
    for col_def in columns_to_add:
        op.execute(sa.text(f"ALTER TABLE user_notification_preferences ADD COLUMN {col_def}"))


def downgrade() -> None:
    """Remove granular notification event preferences."""
    # SQLite doesn't support DROP COLUMN directly, so we use batch_alter_table for downgrade
    with op.batch_alter_table("user_notification_preferences", schema=None) as batch_op:
        # Drop columns in reverse order
        batch_op.drop_column("notify_system_info")
        batch_op.drop_column("notify_system_warnings")
        batch_op.drop_column("notify_system_errors")
        batch_op.drop_column("notify_partial_fill")
        batch_op.drop_column("notify_retry_queue_retried")
        batch_op.drop_column("notify_retry_queue_removed")
        batch_op.drop_column("notify_retry_queue_updated")
        batch_op.drop_column("notify_retry_queue_added")
        batch_op.drop_column("notify_order_modified")
        batch_op.drop_column("notify_order_cancelled")
        batch_op.drop_column("notify_order_executed")
        batch_op.drop_column("notify_order_rejected")
        batch_op.drop_column("notify_order_placed")
