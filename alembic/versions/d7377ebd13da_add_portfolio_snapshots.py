"""add_portfolio_snapshots

Revision ID: d7377ebd13da
Revises: e4bec30fd3ca
Create Date: 2025-12-23 20:29:35.210851+00:00
"""
import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op


# revision identifiers, used by Alembic.
revision = "d7377ebd13da"
down_revision = "e4bec30fd3ca"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create portfolio_snapshots table (Phase 0.3)"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "portfolio_snapshots" in existing_tables:
        return

    # Create portfolio_snapshots table
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("total_value", sa.Float(), nullable=False),
        sa.Column("invested_value", sa.Float(), nullable=False),
        sa.Column("available_cash", sa.Float(), nullable=False),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("realized_pnl", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("open_positions_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("closed_positions_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_return", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("daily_return", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("snapshot_type", sa.String(16), nullable=False, server_default="eod"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index("ix_portfolio_snapshots_user_id", "portfolio_snapshots", ["user_id"])
    op.create_index("ix_portfolio_snapshots_date", "portfolio_snapshots", ["date"])
    op.create_index(
        "ix_portfolio_snapshot_user_date", "portfolio_snapshots", ["user_id", "date"]
    )

    # Create unique constraint
    op.create_unique_constraint(
        "uq_portfolio_snapshot_user_date_type",
        "portfolio_snapshots",
        ["user_id", "date", "snapshot_type"],
    )


def downgrade() -> None:
    """Drop portfolio_snapshots table"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "portfolio_snapshots" not in existing_tables:
        return

    # Drop indexes and constraints first
    try:
        op.drop_constraint(
            "uq_portfolio_snapshot_user_date_type", "portfolio_snapshots", type_="unique"
        )
    except Exception:
        pass

    try:
        op.drop_index("ix_portfolio_snapshot_user_date", table_name="portfolio_snapshots")
    except Exception:
        pass

    try:
        op.drop_index("ix_portfolio_snapshots_date", table_name="portfolio_snapshots")
    except Exception:
        pass

    try:
        op.drop_index("ix_portfolio_snapshots_user_id", table_name="portfolio_snapshots")
    except Exception:
        pass

    # Drop table
    op.drop_table("portfolio_snapshots")
