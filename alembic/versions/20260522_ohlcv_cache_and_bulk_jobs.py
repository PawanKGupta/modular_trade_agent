"""OHLCV cache extensions, corporate actions, bulk analysis jobs.

Revision ID: 20260522_ohlcv
Revises: 20260520_morning_buy
Create Date: 2026-05-22
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260522_ohlcv"
down_revision = "20260520_morning_buy"
branch_labels = None
depends_on = None


def _price_cache_exists(inspector) -> bool:
    return "price_cache" in inspector.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())

    if _price_cache_exists(inspector):
        cols = {c["name"] for c in inspector.get_columns("price_cache")}
        if "interval" not in cols:
            op.add_column(
                "price_cache",
                sa.Column("interval", sa.String(8), server_default="1d", nullable=False),
            )
        if "price_basis" not in cols:
            op.add_column(
                "price_cache",
                sa.Column(
                    "price_basis",
                    sa.String(16),
                    server_default="unadjusted",
                    nullable=False,
                ),
            )
        for name in inspector.get_unique_constraints("price_cache"):
            if name["name"] == "uq_price_cache_symbol_date":
                op.drop_constraint("uq_price_cache_symbol_date", "price_cache", type_="unique")
                break
        uq_names = {u["name"] for u in inspector.get_unique_constraints("price_cache")}
        if "uq_price_cache_symbol_date_interval" not in uq_names:
            op.create_unique_constraint(
                "uq_price_cache_symbol_date_interval",
                "price_cache",
                ["symbol", "date", "interval"],
            )
    else:
        op.create_table(
            "price_cache",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(32), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("interval", sa.String(8), server_default="1d", nullable=False),
            sa.Column("price_basis", sa.String(16), server_default="unadjusted", nullable=False),
            sa.Column("open", sa.Float(), nullable=True),
            sa.Column("high", sa.Float(), nullable=True),
            sa.Column("low", sa.Float(), nullable=True),
            sa.Column("close", sa.Float(), nullable=False),
            sa.Column("volume", sa.Integer(), nullable=True),
            sa.Column("source", sa.String(32), server_default="yfinance", nullable=False),
            sa.Column("cached_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "symbol", "date", "interval", name="uq_price_cache_symbol_date_interval"
            ),
        )
        op.create_index("ix_price_cache_symbol", "price_cache", ["symbol"])
        op.create_index("ix_price_cache_date", "price_cache", ["date"])
        op.create_index(
            "ix_price_cache_symbol_date_interval",
            "price_cache",
            ["symbol", "date", "interval"],
        )

    if "ohlcv_symbol_meta" not in tables:
        op.create_table(
            "ohlcv_symbol_meta",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(32), nullable=False),
            sa.Column("interval", sa.String(8), nullable=False),
            sa.Column("first_date", sa.Date(), nullable=True),
            sa.Column("last_date", sa.Date(), nullable=True),
            sa.Column("row_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("symbol", "interval", name="uq_ohlcv_symbol_meta_symbol_interval"),
        )

    if "corporate_actions" not in tables:
        op.create_table(
            "corporate_actions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(32), nullable=False),
            sa.Column("ex_date", sa.Date(), nullable=False),
            sa.Column("ratio", sa.Float(), nullable=False),
            sa.Column("action_type", sa.String(16), server_default="split", nullable=False),
            sa.Column("source", sa.String(32), server_default="yfinance", nullable=False),
            sa.Column("fetched_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "symbol",
                "ex_date",
                "action_type",
                name="uq_corporate_actions_symbol_ex_type",
            ),
        )
        op.create_index("ix_corporate_actions_symbol", "corporate_actions", ["symbol"])

    if "bulk_analysis_jobs" not in tables:
        op.create_table(
            "bulk_analysis_jobs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("chunk_size", sa.Integer(), server_default="25", nullable=False),
            sa.Column("symbols_json", sa.Text(), nullable=False),
            sa.Column("cursor", sa.Integer(), server_default="0", nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("output_csv", sa.String(512), nullable=True),
            sa.Column("env_snapshot_json", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_bulk_analysis_jobs_status", "bulk_analysis_jobs", ["status"])

    if "bulk_analysis_symbol_status" not in tables:
        op.create_table(
            "bulk_analysis_symbol_status",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("job_id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(32), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("error", sa.String(1024), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("backtest_mode", sa.String(32), nullable=True),
            sa.Column("cache_health", sa.String(32), nullable=True),
            sa.ForeignKeyConstraint(["job_id"], ["bulk_analysis_jobs.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "job_id", "symbol", name="uq_bulk_analysis_symbol_status_job_symbol"
            ),
        )
        op.create_index(
            "ix_bulk_analysis_symbol_status_job_id",
            "bulk_analysis_symbol_status",
            ["job_id"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if "bulk_analysis_symbol_status" in tables:
        op.drop_table("bulk_analysis_symbol_status")
    if "bulk_analysis_jobs" in tables:
        op.drop_table("bulk_analysis_jobs")
    if "corporate_actions" in tables:
        op.drop_table("corporate_actions")
    if "ohlcv_symbol_meta" in tables:
        op.drop_table("ohlcv_symbol_meta")

    if _price_cache_exists(inspector):
        cols = {c["name"] for c in inspector.get_columns("price_cache")}
        try:
            op.drop_constraint("uq_price_cache_symbol_date_interval", "price_cache", type_="unique")
        except Exception:
            pass
        if "interval" in cols:
            op.drop_column("price_cache", "interval")
        if "price_basis" in cols:
            op.drop_column("price_cache", "price_basis")
        try:
            op.create_unique_constraint(
                "uq_price_cache_symbol_date", "price_cache", ["symbol", "date"]
            )
        except Exception:
            pass
