# ruff: noqa
"""add_telegram_bot_token_to_notification_preferences

Revision ID: 52c2d0671c64
Revises: f76d787cb8c8
Create Date: 2025-12-02 16:45:00.000000+00:00
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "52c2d0671c64"
down_revision = "f76d787cb8c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "user_notification_preferences" in existing_tables:
        existing_columns = [
            col["name"] for col in inspector.get_columns("user_notification_preferences")
        ]
        if "telegram_bot_token" not in existing_columns:
            # Add telegram_bot_token column to user_notification_preferences
            op.add_column(
                "user_notification_preferences",
                sa.Column("telegram_bot_token", sa.String(length=128), nullable=True),
            )


def downgrade() -> None:
    # Remove telegram_bot_token column
    op.drop_column("user_notification_preferences", "telegram_bot_token")
