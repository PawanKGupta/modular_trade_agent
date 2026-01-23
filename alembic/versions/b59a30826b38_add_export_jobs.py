"""add_export_jobs

Revision ID: b59a30826b38
Revises: e164471c7941
Create Date: 2025-12-23 21:30:00.000000+00:00
"""
import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op


# revision identifiers, used by Alembic.
revision = "b59a30826b38"
down_revision = "e164471c7941"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create export_jobs table (Phase 0.7)"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "export_jobs" in existing_tables:
        return

    # Create export_jobs table
    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("export_type", sa.String(32), nullable=False),
        sa.Column("data_type", sa.String(32), nullable=False),
        sa.Column("date_range_start", sa.Date(), nullable=True),
        sa.Column("date_range_end", sa.Date(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("records_exported", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("error_message", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index("ix_export_jobs_user_id", "export_jobs", ["user_id"])
    op.create_index(
        "ix_export_jobs_user_status_created",
        "export_jobs",
        ["user_id", "status", "created_at"],
    )


def downgrade() -> None:
    """Drop export_jobs table"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "export_jobs" not in existing_tables:
        return

    # Drop indexes first
    try:
        op.drop_index("ix_export_jobs_user_status_created", table_name="export_jobs")
    except Exception:
        pass

    try:
        op.drop_index("ix_export_jobs_user_id", table_name="export_jobs")
    except Exception:
        pass

    # Drop table
    op.drop_table("export_jobs")
