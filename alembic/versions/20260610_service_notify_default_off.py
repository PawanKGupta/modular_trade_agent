"""Default service notification preferences to false for new rows.

Revision ID: 20260610_svc_off
Revises: 20260610_order_mod_on
Create Date: 2026-06-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260610_svc_off"
down_revision = "20260610_order_mod_on"
branch_labels = None
depends_on = None

_SERVICE_COLUMNS = (
    "notify_service_events",
    "notify_service_started",
    "notify_service_stopped",
    "notify_service_execution_completed",
)


def upgrade() -> None:
    """Change column defaults only; existing user rows are unchanged."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_notification_preferences" not in inspector.get_table_names():
        return

    if bind.dialect.name == "postgresql":
        for column in _SERVICE_COLUMNS:
            op.execute(
                sa.text(
                    f"ALTER TABLE user_notification_preferences "
                    f"ALTER COLUMN {column} SET DEFAULT false"
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_notification_preferences" not in inspector.get_table_names():
        return

    if bind.dialect.name == "postgresql":
        for column in _SERVICE_COLUMNS:
            op.execute(
                sa.text(
                    f"ALTER TABLE user_notification_preferences "
                    f"ALTER COLUMN {column} SET DEFAULT true"
                )
            )
