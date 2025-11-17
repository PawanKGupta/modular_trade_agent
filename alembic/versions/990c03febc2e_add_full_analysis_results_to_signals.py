"""add_full_analysis_results_to_signals

Revision ID: 990c03febc2e
Revises: 06c37167974d
Create Date: 2025-11-17 18:37:06.901763+00:00
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "990c03febc2e"
down_revision = "06c37167974d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add all analysis result fields to signals table"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "signals" not in existing_tables:
        return

    signals_columns = [col["name"] for col in inspector.get_columns("signals")]

    # Scoring fields
    if "backtest_score" not in signals_columns:
        op.add_column("signals", sa.Column("backtest_score", sa.Float(), nullable=True))
    if "combined_score" not in signals_columns:
        op.add_column("signals", sa.Column("combined_score", sa.Float(), nullable=True))
    if "strength_score" not in signals_columns:
        op.add_column("signals", sa.Column("strength_score", sa.Float(), nullable=True))
    if "priority_score" not in signals_columns:
        op.add_column("signals", sa.Column("priority_score", sa.Float(), nullable=True))

    # ML fields
    if "ml_verdict" not in signals_columns:
        op.add_column("signals", sa.Column("ml_verdict", sa.String(length=32), nullable=True))
    if "ml_confidence" not in signals_columns:
        op.add_column("signals", sa.Column("ml_confidence", sa.Float(), nullable=True))
    if "ml_probabilities" not in signals_columns:
        op.add_column("signals", sa.Column("ml_probabilities", sa.JSON(), nullable=True))

    # Trading parameters
    if "buy_range" not in signals_columns:
        op.add_column("signals", sa.Column("buy_range", sa.JSON(), nullable=True))
    if "target" not in signals_columns:
        op.add_column("signals", sa.Column("target", sa.Float(), nullable=True))
    if "stop" not in signals_columns:
        op.add_column("signals", sa.Column("stop", sa.Float(), nullable=True))
    if "last_close" not in signals_columns:
        op.add_column("signals", sa.Column("last_close", sa.Float(), nullable=True))

    # Fundamental data
    if "pe" not in signals_columns:
        op.add_column("signals", sa.Column("pe", sa.Float(), nullable=True))
    if "pb" not in signals_columns:
        op.add_column("signals", sa.Column("pb", sa.Float(), nullable=True))
    if "fundamental_assessment" not in signals_columns:
        op.add_column(
            "signals", sa.Column("fundamental_assessment", sa.String(length=64), nullable=True)
        )
    if "fundamental_ok" not in signals_columns:
        op.add_column("signals", sa.Column("fundamental_ok", sa.Boolean(), nullable=True))

    # Volume data
    if "avg_vol" not in signals_columns:
        op.add_column("signals", sa.Column("avg_vol", sa.Integer(), nullable=True))
    if "today_vol" not in signals_columns:
        op.add_column("signals", sa.Column("today_vol", sa.Integer(), nullable=True))
    if "volume_analysis" not in signals_columns:
        op.add_column("signals", sa.Column("volume_analysis", sa.JSON(), nullable=True))
    if "volume_pattern" not in signals_columns:
        op.add_column("signals", sa.Column("volume_pattern", sa.JSON(), nullable=True))
    if "volume_description" not in signals_columns:
        op.add_column(
            "signals", sa.Column("volume_description", sa.String(length=512), nullable=True)
        )
    if "vol_ok" not in signals_columns:
        op.add_column("signals", sa.Column("vol_ok", sa.Boolean(), nullable=True))
    if "volume_ratio" not in signals_columns:
        op.add_column("signals", sa.Column("volume_ratio", sa.Float(), nullable=True))

    # Analysis metadata
    if "verdict" not in signals_columns:
        op.add_column("signals", sa.Column("verdict", sa.String(length=32), nullable=True))
    if "signals" not in signals_columns:
        op.add_column("signals", sa.Column("signals", sa.JSON(), nullable=True))
    if "justification" not in signals_columns:
        op.add_column("signals", sa.Column("justification", sa.JSON(), nullable=True))
    if "timeframe_analysis" not in signals_columns:
        op.add_column("signals", sa.Column("timeframe_analysis", sa.JSON(), nullable=True))
    if "news_sentiment" not in signals_columns:
        op.add_column("signals", sa.Column("news_sentiment", sa.JSON(), nullable=True))
    if "candle_analysis" not in signals_columns:
        op.add_column("signals", sa.Column("candle_analysis", sa.JSON(), nullable=True))
    if "chart_quality" not in signals_columns:
        op.add_column("signals", sa.Column("chart_quality", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove analysis result fields from signals table"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "signals" not in existing_tables:
        return

    signals_columns = [col["name"] for col in inspector.get_columns("signals")]

    # Scoring fields
    if "backtest_score" in signals_columns:
        op.drop_column("signals", "backtest_score")
    if "combined_score" in signals_columns:
        op.drop_column("signals", "combined_score")
    if "strength_score" in signals_columns:
        op.drop_column("signals", "strength_score")
    if "priority_score" in signals_columns:
        op.drop_column("signals", "priority_score")

    # ML fields
    if "ml_verdict" in signals_columns:
        op.drop_column("signals", "ml_verdict")
    if "ml_confidence" in signals_columns:
        op.drop_column("signals", "ml_confidence")
    if "ml_probabilities" in signals_columns:
        op.drop_column("signals", "ml_probabilities")

    # Trading parameters
    if "buy_range" in signals_columns:
        op.drop_column("signals", "buy_range")
    if "target" in signals_columns:
        op.drop_column("signals", "target")
    if "stop" in signals_columns:
        op.drop_column("signals", "stop")
    if "last_close" in signals_columns:
        op.drop_column("signals", "last_close")

    # Fundamental data
    if "pe" in signals_columns:
        op.drop_column("signals", "pe")
    if "pb" in signals_columns:
        op.drop_column("signals", "pb")
    if "fundamental_assessment" in signals_columns:
        op.drop_column("signals", "fundamental_assessment")
    if "fundamental_ok" in signals_columns:
        op.drop_column("signals", "fundamental_ok")

    # Volume data
    if "avg_vol" in signals_columns:
        op.drop_column("signals", "avg_vol")
    if "today_vol" in signals_columns:
        op.drop_column("signals", "today_vol")
    if "volume_analysis" in signals_columns:
        op.drop_column("signals", "volume_analysis")
    if "volume_pattern" in signals_columns:
        op.drop_column("signals", "volume_pattern")
    if "volume_description" in signals_columns:
        op.drop_column("signals", "volume_description")
    if "vol_ok" in signals_columns:
        op.drop_column("signals", "vol_ok")
    if "volume_ratio" in signals_columns:
        op.drop_column("signals", "volume_ratio")

    # Analysis metadata
    if "verdict" in signals_columns:
        op.drop_column("signals", "verdict")
    if "signals" in signals_columns:
        op.drop_column("signals", "signals")
    if "justification" in signals_columns:
        op.drop_column("signals", "justification")
    if "timeframe_analysis" in signals_columns:
        op.drop_column("signals", "timeframe_analysis")
    if "news_sentiment" in signals_columns:
        op.drop_column("signals", "news_sentiment")
    if "candle_analysis" in signals_columns:
        op.drop_column("signals", "candle_analysis")
    if "chart_quality" in signals_columns:
        op.drop_column("signals", "chart_quality")
