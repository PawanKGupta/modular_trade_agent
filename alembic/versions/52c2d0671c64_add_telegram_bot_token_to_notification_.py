"""add_telegram_bot_token_to_notification_preferences

Revision ID: 52c2d0671c64
Revises: f76d787cb8c8
Create Date: 2025-12-02 16:45:00.000000+00:00
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '52c2d0671c64'
down_revision = 'f76d787cb8c8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add telegram_bot_token column to user_notification_preferences
    op.add_column(
        'user_notification_preferences',
        sa.Column('telegram_bot_token', sa.String(length=128), nullable=True)
    )


def downgrade() -> None:
    # Remove telegram_bot_token column
    op.drop_column('user_notification_preferences', 'telegram_bot_token')
