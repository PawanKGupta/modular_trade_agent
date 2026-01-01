"""post-merge repair: ensure columns and enum values exist

Revision ID: aa11bb22cc33
Revises: deadc0de1234
Create Date: 2025-12-28 23:15:00
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "aa11bb22cc33"
down_revision = "deadc0de1234"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = inspect(bind)

    # 1) Orders table guards: ensure expected columns exist
    if "orders" in insp.get_table_names():
        orders_cols = {c["name"] for c in insp.get_columns("orders")}
        # 1a) Ensure orders.rejection_reason exists
        if "rejection_reason" not in orders_cols:
            op.add_column(
                "orders",
                sa.Column("rejection_reason", sa.String(length=512), nullable=True),
            )
        # 1b) Ensure orders.updated_at exists (add as nullable True for safety)
        if "updated_at" not in orders_cols:
            op.add_column(
                "orders",
                sa.Column("updated_at", sa.DateTime(), nullable=True),
            )

    # 2) Positions table guards: ensure exit detail columns exist
    if "positions" in insp.get_table_names():
        pos_cols = {c["name"] for c in insp.get_columns("positions")}
        additions = []
        if "exit_price" not in pos_cols:
            additions.append(sa.Column("exit_price", sa.Float(), nullable=True))
        if "exit_reason" not in pos_cols:
            additions.append(sa.Column("exit_reason", sa.String(length=64), nullable=True))
        if "exit_rsi" not in pos_cols:
            additions.append(sa.Column("exit_rsi", sa.Float(), nullable=True))
        if "realized_pnl" not in pos_cols:
            additions.append(sa.Column("realized_pnl", sa.Float(), nullable=True))
        if "realized_pnl_pct" not in pos_cols:
            additions.append(sa.Column("realized_pnl_pct", sa.Float(), nullable=True))
        if "sell_order_id" not in pos_cols:
            # Add as Integer nullable; FK constraint optional
            additions.append(sa.Column("sell_order_id", sa.Integer(), nullable=True))
        for col in additions:
            op.add_column("positions", col)

    # 3) Normalize enum values to lowercase (PostgreSQL safe guards)
    if bind.dialect.name == "postgresql":
        # First, update existing row data to lowercase (if uppercase values exist)
        op.execute(
            """
            UPDATE orders SET trade_mode = LOWER(trade_mode::text)::trademode
            WHERE trade_mode::text IN ('BROKER', 'PAPER');
            """
        )

        op.execute(
            """
            UPDATE usersettings SET trade_mode = LOWER(trade_mode::text)::trademode
            WHERE trade_mode::text IN ('BROKER', 'PAPER');
            """
        )

        op.execute(
            """
            UPDATE users SET role = LOWER(role::text)::userrole
            WHERE role::text IN ('ADMIN', 'USER');
            """
        )

        # Then rename enum type labels if they still exist as uppercase
        # trademode -> ['paper','broker']
        op.execute(
            """
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_enum e ON e.enumtypid = t.oid
                WHERE t.typname = 'trademode' AND e.enumlabel = 'BROKER'
              ) THEN
                ALTER TYPE trademode RENAME VALUE 'BROKER' TO 'broker';
              END IF;
              IF EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_enum e ON e.enumtypid = t.oid
                WHERE t.typname = 'trademode' AND e.enumlabel = 'PAPER'
              ) THEN
                ALTER TYPE trademode RENAME VALUE 'PAPER' TO 'paper';
              END IF;
            END $$;
            """
        )

        # userrole -> ['admin','user']
        op.execute(
            """
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_enum e ON e.enumtypid = t.oid
                WHERE t.typname = 'userrole' AND e.enumlabel = 'ADMIN'
              ) THEN
                ALTER TYPE userrole RENAME VALUE 'ADMIN' TO 'admin';
              END IF;
              IF EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_enum e ON e.enumtypid = t.oid
                WHERE t.typname = 'userrole' AND e.enumlabel = 'USER'
              ) THEN
                ALTER TYPE userrole RENAME VALUE 'USER' TO 'user';
              END IF;
            END $$;
            """
        )

        # 4) Ensure signalstatus enum exists (bootstrap safety)
        op.execute(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'signalstatus') THEN
                CREATE TYPE signalstatus AS ENUM ('active','inactive','expired');
              END IF;
            END $$;
            """
        )


def downgrade():
    # No-op: repair migration; do not attempt to undo enum renames
    pass
