"""Linear step after close_ongoing (single head)

20260202_close_ongoing already merges the two production heads
(20260131_add_base_symbol_orders, a9b8c7d6e5f4). This revision is a linear
successor so 20260202_uq_sell_only can depend on a single head.

Revision ID: 20260202_merge_all
Revises: 20260202_close_ongoing
Create Date: 2026-02-02

"""

revision = "20260202_merge_all"
down_revision = "20260202_close_ongoing"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
