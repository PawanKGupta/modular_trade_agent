"""add_price_cache

Revision ID: e164471c7941
Revises: e3c7a9ca471c
Create Date: 2025-12-23 21:00:00.000000+00:00
"""
import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op


# revision identifiers, used by Alembic.
revision = "e164471c7941"
down_revision = "e3c7a9ca471c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create price_cache table (Phase 0.6)"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "price_cache" in existing_tables:
        return

    # Create price_cache table
    op.create_table(
        "price_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="yfinance"),
        sa.Column("cached_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index("ix_price_cache_symbol", "price_cache", ["symbol"])
    op.create_index("ix_price_cache_date", "price_cache", ["date"])
    op.create_index(
        "ix_price_cache_symbol_date",
        "price_cache",
        ["symbol", "date"],
    )

    # Create unique constraint
    op.create_unique_constraint(
        "uq_price_cache_symbol_date",
        "price_cache",
        ["symbol", "date"],
    )


def downgrade() -> None:
    """Drop price_cache table"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "price_cache" not in existing_tables:
        return

    # Drop unique constraint first
    try:
        op.drop_constraint("uq_price_cache_symbol_date", "price_cache", type_="unique")
    except Exception:
        pass

    # Drop indexes
    try:
        op.drop_index("ix_price_cache_symbol_date", table_name="price_cache")
    except Exception:
        pass

    try:
        op.drop_index("ix_price_cache_date", table_name="price_cache")
    except Exception:
        pass

    try:
        op.drop_index("ix_price_cache_symbol", table_name="price_cache")
    except Exception:
        pass

    # Drop table
    op.drop_table("price_cache")
