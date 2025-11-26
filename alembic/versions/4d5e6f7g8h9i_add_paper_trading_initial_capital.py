"""add_paper_trading_initial_capital

Revision ID: 4d5e6f7g8h9i
Revises: 3473a345c7fb
Create Date: 2025-11-26 00:00:00.000000+00:00
"""

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import sqlite

from alembic import op

# revision identifiers, used by Alembic.
revision = "4d5e6f7g8h9i"
down_revision = "3473a345c7fb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add paper_trading_initial_capital column to user_trading_config table

    This column stores the user's preferred starting balance for paper trading.
    Default: Rs 3,00,000 (more realistic than the previous hardcoded Rs 1,00,000)
    """
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "user_trading_config" not in existing_tables:
        return

    config_columns = [col["name"] for col in inspector.get_columns("user_trading_config")]

    # Check if column already exists
    if "paper_trading_initial_capital" in config_columns:
        return

    # SQLite requires batch mode for adding columns
    if isinstance(conn.dialect, sqlite.dialect):
        with op.batch_alter_table("user_trading_config", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "paper_trading_initial_capital",
                    sa.Float(),
                    nullable=False,
                    server_default="300000.0",
                )
            )
    else:
        # For PostgreSQL and other databases, add column directly
        op.add_column(
            "user_trading_config",
            sa.Column(
                "paper_trading_initial_capital",
                sa.Float(),
                nullable=False,
                server_default="300000.0",
            ),
        )


def downgrade() -> None:
    """Remove paper_trading_initial_capital column from user_trading_config table"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "user_trading_config" not in existing_tables:
        return

    config_columns = [col["name"] for col in inspector.get_columns("user_trading_config")]

    # Check if column exists
    if "paper_trading_initial_capital" not in config_columns:
        return

    # SQLite requires batch mode for dropping columns
    if isinstance(conn.dialect, sqlite.dialect):
        with op.batch_alter_table("user_trading_config", schema=None) as batch_op:
            batch_op.drop_column("paper_trading_initial_capital")
    else:
        # For PostgreSQL and other databases, drop column directly
        op.drop_column("user_trading_config", "paper_trading_initial_capital")
