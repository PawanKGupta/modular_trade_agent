"""Add optional profile mobile_number to users.

Revision ID: 20260606_user_mobile
Revises: 20260606_user_auth
Create Date: 2026-06-06
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260606_user_mobile"
down_revision = "20260606_user_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "mobile_number" not in cols:
        op.add_column("users", sa.Column("mobile_number", sa.String(length=15), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "mobile_number" in cols:
        op.drop_column("users", "mobile_number")
