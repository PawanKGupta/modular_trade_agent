"""Default notify_order_modified to true for new preference rows.

Revision ID: 20260610_order_mod_on
Revises: 20260606_user_mobile
Create Date: 2026-06-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260610_order_mod_on"
down_revision = "20260606_user_mobile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Change column default only; existing user rows are unchanged."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_notification_preferences" not in inspector.get_table_names():
        return

    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "ALTER TABLE user_notification_preferences "
                "ALTER COLUMN notify_order_modified SET DEFAULT true"
            )
        )
    else:
        # SQLite: recreate default via batch alter is heavy; new rows use app defaults.
        # Best-effort: no-op when ALTER COLUMN DEFAULT unsupported.
        pass


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_notification_preferences" not in inspector.get_table_names():
        return

    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "ALTER TABLE user_notification_preferences "
                "ALTER COLUMN notify_order_modified SET DEFAULT false"
            )
        )
