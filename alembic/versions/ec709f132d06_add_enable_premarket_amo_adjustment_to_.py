# ruff: noqa
"""add_enable_premarket_amo_adjustment_to_user_trading_config

Revision ID: ec709f132d06
Revises: 4d5e6f7g8h9i
Create Date: 2025-11-26 15:09:47.862055+00:00
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "ec709f132d06"
down_revision = "4d5e6f7g8h9i"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "user_trading_config" in existing_tables:
        existing_columns = [col["name"] for col in inspector.get_columns("user_trading_config")]
        if "enable_premarket_amo_adjustment" not in existing_columns:
            op.add_column(
                "user_trading_config",
                sa.Column(
                    "enable_premarket_amo_adjustment",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text(
                        "true"
                    ),  # Default to True (enabled), Postgres requires 'true' not '1'
                ),
            )


def downgrade() -> None:
    op.drop_column("user_trading_config", "enable_premarket_amo_adjustment")
