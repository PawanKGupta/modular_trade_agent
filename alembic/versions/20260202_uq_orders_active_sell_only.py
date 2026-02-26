"""Restrict uq_orders_user_base_symbol_active to sell orders only

The original index applied to all active (pending/ongoing) orders, so a pending or
ongoing buy for a symbol could block placing a sell. Intent was one active *sell*
per (user_id, base_symbol). This migration recreates the index with side = 'sell'.

Revision ID: 20260202_uq_sell_only
Revises: 20260202_merge_all
Create Date: 2026-02-02

"""

from alembic import op

revision = "20260202_uq_sell_only"
down_revision = "20260202_merge_all"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP INDEX IF EXISTS uq_orders_user_base_symbol_active")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_user_base_symbol_active "
        "ON orders (user_id, base_symbol) "
        "WHERE status IN ('pending', 'ongoing') AND side = 'sell'"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_orders_user_base_symbol_active")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_user_base_symbol_active "
        "ON orders (user_id, base_symbol) WHERE status IN ('pending', 'ongoing')"
    )
