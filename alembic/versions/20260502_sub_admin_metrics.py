# ruff: noqa
"""No-op placeholder for removed subscription admin-metrics migration.

Revision ID: 20260502_sub_admin_metrics
Revises: 20260501_drop_sub_catalog
Create Date: 2026-05-02

Some environments have ``alembic_version`` set to this revision after an older
migration file was deleted from the repo. Re-introducing this revision id as an
empty migration restores a linear graph through
``20260503_rm_sub_billing`` (which drops the related columns when present).
"""

revision = "20260502_sub_admin_metrics"
down_revision = "20260501_drop_sub_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
