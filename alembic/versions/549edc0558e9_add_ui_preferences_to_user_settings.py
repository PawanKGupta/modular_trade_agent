"""add_ui_preferences_to_user_settings

Revision ID: 549edc0558e9
Revises: 990c03febc2e
Create Date: 2025-11-17 18:54:56.146451+00:00
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "549edc0558e9"
down_revision = "990c03febc2e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usersettings", sa.Column("ui_preferences", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("usersettings", "ui_preferences")
