"""add_granular_service_event_preferences

Revision ID: 1f2671ff2c90
Revises: 53c66ed1105b
Create Date: 2025-11-29 22:39:50.299314+00:00
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "1f2671ff2c90"
down_revision = "53c66ed1105b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add granular service event preferences to user_notification_preferences table.

    This migration adds per-service-event notification preferences, allowing users to control
    which specific service events trigger notifications. All new preferences default to
    TRUE to maintain backward compatibility (current behavior where all service events notify).

    Uses raw SQL for SQLite compatibility.
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
    columns_to_add = []
    if "notify_service_started" not in existing_columns:
        columns_to_add.append("notify_service_started BOOLEAN DEFAULT 1 NOT NULL")
    if "notify_service_stopped" not in existing_columns:
        columns_to_add.append("notify_service_stopped BOOLEAN DEFAULT 1 NOT NULL")
    if "notify_service_execution_completed" not in existing_columns:
        columns_to_add.append("notify_service_execution_completed BOOLEAN DEFAULT 1 NOT NULL")

    # Execute all ALTER TABLE statements
    for col_def in columns_to_add:
        try:
            op.execute(sa.text(f"ALTER TABLE user_notification_preferences ADD COLUMN {col_def}"))
        except Exception as e:
            # Log error but continue (column might already exist)
            import logging

            logging.warning(f"Failed to add column {col_def.split()[0]}: {e}")


def downgrade() -> None:
    """Remove granular service event preferences."""
    # SQLite doesn't support DROP COLUMN directly, so we use batch_alter_table for downgrade
    with op.batch_alter_table("user_notification_preferences", schema=None) as batch_op:
        # Drop columns in reverse order
        batch_op.drop_column("notify_service_execution_completed")
        batch_op.drop_column("notify_service_stopped")
        batch_op.drop_column("notify_service_started")
