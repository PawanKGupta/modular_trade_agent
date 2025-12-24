"""add_analytics_cache

Revision ID: d3afc70a65bb
Revises: b59a30826b38
Create Date: 2025-12-23 22:00:00.000000+00:00
"""
import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op


# revision identifiers, used by Alembic.
revision = "d3afc70a65bb"
down_revision = "b59a30826b38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create analytics_cache table (Phase 0.8)"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "analytics_cache" in existing_tables:
        return

    # Create analytics_cache table
    op.create_table(
        "analytics_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("cache_key", sa.String(128), nullable=False),
        sa.Column("analytics_type", sa.String(32), nullable=False),
        sa.Column("date_range_start", sa.Date(), nullable=True),
        sa.Column("date_range_end", sa.Date(), nullable=True),
        sa.Column("cached_data", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index("ix_analytics_cache_cache_key", "analytics_cache", ["cache_key"])
    op.create_index(
        "ix_analytics_cache_user_type",
        "analytics_cache",
        ["user_id", "analytics_type"],
    )

    # Create unique constraint
    op.create_unique_constraint(
        "uq_analytics_cache_user_key",
        "analytics_cache",
        ["user_id", "cache_key"],
    )


def downgrade() -> None:
    """Drop analytics_cache table"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "analytics_cache" not in existing_tables:
        return

    # Drop unique constraint first
    try:
        op.drop_constraint("uq_analytics_cache_user_key", "analytics_cache", type_="unique")
    except Exception:
        pass

    # Drop indexes
    try:
        op.drop_index("ix_analytics_cache_user_type", table_name="analytics_cache")
    except Exception:
        pass

    try:
        op.drop_index("ix_analytics_cache_cache_key", table_name="analytics_cache")
    except Exception:
        pass

    # Drop table
    op.drop_table("analytics_cache")
