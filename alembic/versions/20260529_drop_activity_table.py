"""Drop unused activity table.

Operational logs use file-based JSONL (System Logs UI). The activity table had
no writers and zero rows in production.

Revision ID: 20260529_drop_activity
Revises: 20260523_ohlcv_meta
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260529_drop_activity"
down_revision = "20260523_ohlcv_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "activity" not in inspector.get_table_names():
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("activity")}
    for index_name in ("ix_activity_user_id", "ix_activity_type", "ix_activity_ts"):
        if index_name in indexes:
            op.drop_index(index_name, table_name="activity")

    fks = inspector.get_foreign_keys("activity")
    for fk in fks:
        op.drop_constraint(fk["name"], "activity", type_="foreignkey")

    op.drop_table("activity")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "activity" in inspector.get_table_names():
        return

    op.create_table(
        "activity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("ref_id", sa.String(length=64), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_activity_type", "activity", ["type"])
    op.create_index("ix_activity_ts", "activity", ["ts"])
    op.create_index("ix_activity_user_id", "activity", ["user_id"])
    op.create_foreign_key(
        "fk_activity_user_id", "activity", "users", ["user_id"], ["id"], ondelete="SET NULL"
    )
