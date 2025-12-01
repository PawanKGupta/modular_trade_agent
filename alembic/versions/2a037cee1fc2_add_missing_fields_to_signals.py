"""add_missing_fields_to_signals

Revision ID: 2a037cee1fc2
Revises: a17c57ecf620
Create Date: 2025-01-18 23:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2a037cee1fc2"
down_revision: str | None = "a17c57ecf620"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_columns = {col["name"] for col in inspector.get_columns("signals")}

    # Add new fields if they don't exist
    if "final_verdict" not in existing_columns:
        op.add_column("signals", sa.Column("final_verdict", sa.String(length=32), nullable=True))

    if "rule_verdict" not in existing_columns:
        op.add_column("signals", sa.Column("rule_verdict", sa.String(length=32), nullable=True))

    if "verdict_source" not in existing_columns:
        op.add_column("signals", sa.Column("verdict_source", sa.String(length=16), nullable=True))

    if "backtest_confidence" not in existing_columns:
        op.add_column(
            "signals", sa.Column("backtest_confidence", sa.String(length=16), nullable=True)
        )

    if "vol_strong" not in existing_columns:
        op.add_column("signals", sa.Column("vol_strong", sa.Boolean(), nullable=True))

    if "is_above_ema200" not in existing_columns:
        op.add_column("signals", sa.Column("is_above_ema200", sa.Boolean(), nullable=True))

    if "dip_depth_from_20d_high_pct" not in existing_columns:
        op.add_column(
            "signals", sa.Column("dip_depth_from_20d_high_pct", sa.Float(), nullable=True)
        )

    if "consecutive_red_days" not in existing_columns:
        op.add_column("signals", sa.Column("consecutive_red_days", sa.Integer(), nullable=True))

    if "dip_speed_pct_per_day" not in existing_columns:
        op.add_column("signals", sa.Column("dip_speed_pct_per_day", sa.Float(), nullable=True))

    if "decline_rate_slowing" not in existing_columns:
        op.add_column("signals", sa.Column("decline_rate_slowing", sa.Boolean(), nullable=True))

    if "volume_green_vs_red_ratio" not in existing_columns:
        op.add_column("signals", sa.Column("volume_green_vs_red_ratio", sa.Float(), nullable=True))

    if "support_hold_count" not in existing_columns:
        op.add_column("signals", sa.Column("support_hold_count", sa.Integer(), nullable=True))

    if "liquidity_recommendation" not in existing_columns:
        op.add_column("signals", sa.Column("liquidity_recommendation", sa.JSON(), nullable=True))

    if "trading_params" not in existing_columns:
        op.add_column("signals", sa.Column("trading_params", sa.JSON(), nullable=True))


def downgrade() -> None:
    # Drop columns in reverse order
    op.drop_column("signals", "trading_params")
    op.drop_column("signals", "liquidity_recommendation")
    op.drop_column("signals", "support_hold_count")
    op.drop_column("signals", "volume_green_vs_red_ratio")
    op.drop_column("signals", "decline_rate_slowing")
    op.drop_column("signals", "dip_speed_pct_per_day")
    op.drop_column("signals", "consecutive_red_days")
    op.drop_column("signals", "dip_depth_from_20d_high_pct")
    op.drop_column("signals", "is_above_ema200")
    op.drop_column("signals", "vol_strong")
    op.drop_column("signals", "backtest_confidence")
    op.drop_column("signals", "verdict_source")
    op.drop_column("signals", "rule_verdict")
    op.drop_column("signals", "final_verdict")
