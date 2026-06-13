"""User data security schema: token_version, MFA, refresh_tokens, soft delete.

Revision ID: 20260613_user_sec
Revises: 20260610_bal_short
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260613_user_sec"
down_revision = "20260610_bal_short"
branch_labels = None
depends_on = None


def _users_columns(inspector) -> set[str]:
    if "users" not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns("users")}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = _users_columns(inspector)

    if "users" in inspector.get_table_names():
        if "token_version" not in cols:
            op.add_column(
                "users",
                sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
            )
        if "must_change_password" not in cols:
            op.add_column(
                "users",
                sa.Column(
                    "must_change_password",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
            )
        if "mfa_enabled" not in cols:
            op.add_column(
                "users",
                sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            )
        if "mfa_secret_encrypted" not in cols:
            op.add_column("users", sa.Column("mfa_secret_encrypted", sa.LargeBinary(), nullable=True))
        if "mfa_backup_codes_hash" not in cols:
            op.add_column("users", sa.Column("mfa_backup_codes_hash", sa.Text(), nullable=True))
        if "deleted_at" not in cols:
            op.add_column("users", sa.Column("deleted_at", sa.DateTime(), nullable=True))

    if "refresh_tokens" not in inspector.get_table_names():
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("family_id", sa.String(36), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
        op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)
        op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
        op.create_index(
            "ix_refresh_tokens_user_family", "refresh_tokens", ["user_id", "family_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "refresh_tokens" in inspector.get_table_names():
        op.drop_table("refresh_tokens")

    cols = _users_columns(inspector)
    for col in (
        "deleted_at",
        "mfa_backup_codes_hash",
        "mfa_secret_encrypted",
        "mfa_enabled",
        "must_change_password",
        "token_version",
    ):
        if col in cols:
            op.drop_column("users", col)
