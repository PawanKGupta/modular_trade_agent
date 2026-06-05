"""Add offline payment settings and online_payments_enabled toggle.

Revision ID: 20260605_offline_pay
Revises: 20260529_drop_activity
Create Date: 2026-06-05
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260605_offline_pay"
down_revision = "20260529_drop_activity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "billing_admin_settings" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("billing_admin_settings")}
    if "online_payments_enabled" not in cols:
        op.add_column(
            "billing_admin_settings",
            sa.Column(
                "online_payments_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if "offline_payment_upi_id" not in cols:
        op.add_column(
            "billing_admin_settings",
            sa.Column("offline_payment_upi_id", sa.String(128), nullable=True),
        )
    if "offline_payment_instructions" not in cols:
        op.add_column(
            "billing_admin_settings",
            sa.Column("offline_payment_instructions", sa.Text(), nullable=True),
        )
    if "offline_payment_qr_image_url" not in cols:
        op.add_column(
            "billing_admin_settings",
            sa.Column("offline_payment_qr_image_url", sa.String(512), nullable=True),
        )
    op.execute(
        sa.text(
            "UPDATE billing_admin_settings SET "
            "offline_payment_upi_id = COALESCE(NULLIF(TRIM(offline_payment_upi_id), ''), '8565859556@apl'), "
            "offline_payment_instructions = COALESCE(NULLIF(TRIM(offline_payment_instructions), ''), "
            "'Pay exact amount; add bill # and email in UPI note.') "
            "WHERE id = 1"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "billing_admin_settings" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("billing_admin_settings")}
    for name in (
        "offline_payment_qr_image_url",
        "offline_payment_instructions",
        "offline_payment_upi_id",
        "online_payments_enabled",
    ):
        if name in cols:
            op.drop_column("billing_admin_settings", name)
