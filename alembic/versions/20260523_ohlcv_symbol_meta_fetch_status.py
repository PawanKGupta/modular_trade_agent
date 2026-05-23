"""Add fetch validation status columns to ohlcv_symbol_meta.

Revision ID: 20260523_ohlcv_meta
Revises: 20260522_ohlcv
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260523_ohlcv_meta"
down_revision = "20260522_ohlcv"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "ohlcv_symbol_meta" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("ohlcv_symbol_meta")}
    if "fetch_status" not in cols:
        op.add_column(
            "ohlcv_symbol_meta",
            sa.Column("fetch_status", sa.String(16), server_default="unknown", nullable=False),
        )
    if "coverage_pct" not in cols:
        op.add_column(
            "ohlcv_symbol_meta",
            sa.Column("coverage_pct", sa.Float(), nullable=True),
        )
    if "last_fetch_at" not in cols:
        op.add_column(
            "ohlcv_symbol_meta",
            sa.Column("last_fetch_at", sa.DateTime(), nullable=True),
        )
    if "last_validation_message" not in cols:
        op.add_column(
            "ohlcv_symbol_meta",
            sa.Column("last_validation_message", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "ohlcv_symbol_meta" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("ohlcv_symbol_meta")}
    for name in (
        "last_validation_message",
        "last_fetch_at",
        "coverage_pct",
        "fetch_status",
    ):
        if name in cols:
            op.drop_column("ohlcv_symbol_meta", name)
