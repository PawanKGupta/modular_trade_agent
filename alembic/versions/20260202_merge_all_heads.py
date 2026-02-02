"""Merge all heads to single head

After 20260202_close_ongoing_orders merged (20260131_add_base_symbol_orders, a9b8c7d6e5f4),
there remains head b1c2d3e4f5g6 from another branch. This migration merges them so
alembic heads returns a single head in any environment.

Revision ID: 20260202_merge_all
Revises: 20260202_close_ongoing, b1c2d3e4f5g6
Create Date: 2026-02-02

"""

from alembic import op

revision = "20260202_merge_all"
down_revision = ("20260202_close_ongoing", "b1c2d3e4f5g6")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
