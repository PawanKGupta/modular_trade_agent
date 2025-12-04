"""add_entry_rsi_to_positions_and_backfill

Revision ID: d1e2f3a4b5c6
Revises: c38b470b20d1
Create Date: 2025-01-27 12:00:00.000000+00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.dialects import sqlite


# revision identifiers, used by Alembic.
revision = 'd1e2f3a4b5c6'
down_revision = 'c38b470b20d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add entry_rsi column to Positions table and backfill from order metadata"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # Add entry_rsi to Positions table if it doesn't exist
    if "positions" in existing_tables:
        positions_columns = [col["name"] for col in inspector.get_columns("positions")]

        if "entry_rsi" not in positions_columns:
            op.add_column("positions", sa.Column("entry_rsi", sa.Float(), nullable=True))

        # Backfill entry_rsi from Orders.order_metadata.rsi_entry_level
        # Strategy:
        # 1. For each position, find the earliest executed buy order (ONGOING status)
        # 2. Extract rsi_entry_level from order_metadata
        # 3. If not available, try rsi10 from order_metadata
        # 4. If still not available, default to 29.5 (assume entry at RSI < 30)
        
        # SQL for backfilling (works for both SQLite and PostgreSQL)
        if isinstance(conn.dialect, sqlite.dialect):
            # SQLite JSON extraction
            backfill_sql = text("""
                UPDATE positions
                SET entry_rsi = (
                    SELECT 
                        CASE 
                            WHEN json_extract(o.order_metadata, '$.rsi_entry_level') IS NOT NULL 
                                THEN CAST(json_extract(o.order_metadata, '$.rsi_entry_level') AS REAL)
                            WHEN json_extract(o.order_metadata, '$.rsi10') IS NOT NULL 
                                THEN CAST(json_extract(o.order_metadata, '$.rsi10') AS REAL)
                            ELSE 29.5
                        END
                    FROM orders o
                    WHERE o.user_id = positions.user_id
                        AND o.symbol = positions.symbol
                        AND o.side = 'buy'
                        AND o.status = 'ongoing'
                        AND o.order_metadata IS NOT NULL
                    ORDER BY o.execution_time ASC, o.filled_at ASC, o.placed_at ASC
                    LIMIT 1
                )
                WHERE entry_rsi IS NULL
                    AND EXISTS (
                        SELECT 1 
                        FROM orders o
                        WHERE o.user_id = positions.user_id
                            AND o.symbol = positions.symbol
                            AND o.side = 'buy'
                            AND o.status = 'ongoing'
                    )
            """)
        else:
            # PostgreSQL JSON extraction
            backfill_sql = text("""
                UPDATE positions
                SET entry_rsi = COALESCE(
                    (SELECT (o.order_metadata->>'rsi_entry_level')::float
                     FROM orders o
                     WHERE o.user_id = positions.user_id
                         AND o.symbol = positions.symbol
                         AND o.side = 'buy'
                         AND o.status = 'ongoing'
                         AND o.order_metadata IS NOT NULL
                     ORDER BY o.execution_time ASC NULLS LAST, 
                              o.filled_at ASC NULLS LAST, 
                              o.placed_at ASC
                     LIMIT 1),
                    (SELECT (o.order_metadata->>'rsi10')::float
                     FROM orders o
                     WHERE o.user_id = positions.user_id
                         AND o.symbol = positions.symbol
                         AND o.side = 'buy'
                         AND o.status = 'ongoing'
                         AND o.order_metadata IS NOT NULL
                     ORDER BY o.execution_time ASC NULLS LAST, 
                              o.filled_at ASC NULLS LAST, 
                              o.placed_at ASC
                     LIMIT 1),
                    29.5
                )
                WHERE entry_rsi IS NULL
                    AND EXISTS (
                        SELECT 1 
                        FROM orders o
                        WHERE o.user_id = positions.user_id
                            AND o.symbol = positions.symbol
                            AND o.side = 'buy'
                            AND o.status = 'ongoing'
                    )
            """)
        
        try:
            conn.execute(backfill_sql)
            conn.commit()
        except Exception as e:
            # Log error but don't fail migration
            print(f"Warning: Could not backfill entry_rsi: {e}")
            conn.rollback()


def downgrade() -> None:
    """Remove entry_rsi column from Positions table"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "positions" in existing_tables:
        positions_columns = [col["name"] for col in inspector.get_columns("positions")]
        if "entry_rsi" in positions_columns:
            op.drop_column("positions", "entry_rsi")

