"""backfill_exit_details_to_closed_positions

Revision ID: 68601da84070
Revises: 475778eb3e52
Create Date: 2025-12-28 18:46:11.179442+00:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "68601da84070"
down_revision = "475778eb3e52"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Backfill exit details for closed positions that are missing them."""
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        # Match closed positions to their sell orders and populate exit fields
        op.execute(
            """
            UPDATE positions p
            SET
              exit_price = o.execution_price,
              realized_pnl = (o.execution_price - p.avg_price) * p.quantity,
              realized_pnl_pct = ((o.execution_price - p.avg_price) / p.avg_price) * 100,
              sell_order_id = o.id
            FROM orders o
            WHERE p.closed_at IS NOT NULL
              AND p.exit_price IS NULL
              AND o.user_id = p.user_id
              AND o.symbol = p.symbol
              AND o.side = 'sell'
              AND o.execution_time IS NOT NULL
              AND o.execution_price IS NOT NULL
              AND ABS(EXTRACT(EPOCH FROM (o.execution_time - p.closed_at))) < 3600;
            """
        )
    elif bind.dialect.name == "sqlite":
        # SQLite version using julianday for date comparison
        op.execute(
            """
            UPDATE positions
            SET
              exit_price = (
                SELECT o.execution_price
                FROM orders o
                WHERE o.user_id = positions.user_id
                  AND o.symbol = positions.symbol
                  AND o.side = 'sell'
                  AND o.execution_time IS NOT NULL
                  AND o.execution_price IS NOT NULL
                  AND ABS(
                    (julianday(o.execution_time) - julianday(positions.closed_at)) * 86400
                  ) < 3600
                ORDER BY ABS(
                  (julianday(o.execution_time) - julianday(positions.closed_at)) * 86400
                )
                LIMIT 1
              ),
              sell_order_id = (
                SELECT o.id
                FROM orders o
                WHERE o.user_id = positions.user_id
                  AND o.symbol = positions.symbol
                  AND o.side = 'sell'
                  AND o.execution_time IS NOT NULL
                  AND o.execution_price IS NOT NULL
                  AND ABS(
                    (julianday(o.execution_time) - julianday(positions.closed_at)) * 86400
                  ) < 3600
                ORDER BY ABS(
                  (julianday(o.execution_time) - julianday(positions.closed_at)) * 86400
                )
                LIMIT 1
              )
            WHERE closed_at IS NOT NULL
              AND exit_price IS NULL;
            """
        )
        # Calculate realized_pnl and realized_pnl_pct after exit_price is set
        op.execute(
            """
            UPDATE positions
            SET
              realized_pnl = (exit_price - avg_price) * quantity,
              realized_pnl_pct = ((exit_price - avg_price) / avg_price) * 100
            WHERE closed_at IS NOT NULL
              AND exit_price IS NOT NULL
              AND realized_pnl IS NULL;
            """
        )


def downgrade() -> None:
    """No downgrade needed - backfill is permanent."""
    pass
