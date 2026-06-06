"""Add user auth token and email verification columns.

Revision ID: 20260606_user_auth
Revises: 20260605_offline_pay
Create Date: 2026-06-06
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260606_user_auth"
down_revision = "20260605_offline_pay"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "email_verified_at" not in cols:
        op.add_column("users", sa.Column("email_verified_at", sa.DateTime(), nullable=True))
    if "email_verification_token_hash" not in cols:
        op.add_column(
            "users",
            sa.Column("email_verification_token_hash", sa.String(length=64), nullable=True),
        )
    if "email_verification_sent_at" not in cols:
        op.add_column(
            "users",
            sa.Column("email_verification_sent_at", sa.DateTime(), nullable=True),
        )
    if "password_reset_token_hash" not in cols:
        op.add_column(
            "users",
            sa.Column("password_reset_token_hash", sa.String(length=64), nullable=True),
        )
    if "password_reset_expires_at" not in cols:
        op.add_column(
            "users",
            sa.Column("password_reset_expires_at", sa.DateTime(), nullable=True),
        )
    op.execute(
        sa.text(
            "UPDATE users SET email_verified_at = created_at "
            "WHERE email_verified_at IS NULL AND email_verification_token_hash IS NULL"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("users")}
    for name in (
        "password_reset_expires_at",
        "password_reset_token_hash",
        "email_verification_sent_at",
        "email_verification_token_hash",
        "email_verified_at",
    ):
        if name in cols:
            op.drop_column("users", name)
