"""Merge heads and close all ONGOING orders (one-time data migration)

Resolves multiple heads in production:
- 20260131_add_base_symbol_orders (head)
- a9b8c7d6e5f4 (head)

Also: Filled orders are now stored as CLOSED; 'position ongoing' is tracked in
Positions (closed_at IS NULL). This migration updates existing ONGOING orders to
CLOSED so they no longer count toward uq_orders_user_base_symbol_active and
order status aligns with the new rule: filled = CLOSED.

Works in any environment: run alembic upgrade head from either head to reach
this single head.

Revision ID: 20260202_close_ongoing
Revises: 20260131_add_base_symbol_orders, a9b8c7d6e5f4
Create Date: 2026-02-02

"""

from alembic import op

revision = "20260202_close_ongoing"
down_revision = ("20260131_add_base_symbol_orders", "a9b8c7d6e5f4")
branch_labels = None
depends_on = None


def upgrade():
    # Set closed_at for rows that don't have it (required for CLOSED semantics)
    op.execute(
        """
        UPDATE orders
        SET status = 'closed',
            closed_at = COALESCE(closed_at, placed_at)
        WHERE status = 'ongoing'
        """
    )


def downgrade():
    # Data migration: reversing would set orders back to ongoing and re-introduce
    # the unique-constraint blocking issue. No-op; document only.
    pass
