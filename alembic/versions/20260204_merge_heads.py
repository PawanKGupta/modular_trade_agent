"""Merge task_exec_ist and uq_sell_only into single head

Revision ID: 20260204_merge_heads
Revises: 20260204_task_exec_ist, 20260202_uq_sell_only
Create Date: 2026-02-04

"""

revision = "20260204_merge_heads"
down_revision = ("20260204_task_exec_ist", "20260202_uq_sell_only")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
