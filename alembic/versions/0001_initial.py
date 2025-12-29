# ruff: noqa
"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2025-11-16
"""

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Insert system user (user_id=1) if not exists
    op.execute(
        """
        INSERT INTO users (id, email, name, password_hash, role, is_active, created_at, updated_at)
        SELECT 1, 'system@tradeagent.local', 'System User', '!', 'admin', TRUE, NOW(), NOW()
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE id = 1)
        """
    )
    bind = op.get_bind()
    inspector = inspect(bind)

    # Ensure enum types exist without raising on duplicates; avoid dropping in case tables already reference them.
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid WHERE t.typname = 'userrole') THEN
                        CREATE TYPE userrole AS ENUM ('admin', 'user');
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid WHERE t.typname = 'trademode') THEN
                        CREATE TYPE trademode AS ENUM ('paper', 'broker');
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid WHERE t.typname = 'orderstatus') THEN
                        CREATE TYPE orderstatus AS ENUM ('amo', 'ongoing', 'sell', 'closed');
                    END IF;
                END$$;
                """
            )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("admin", "user", name="userrole", create_type=False),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)

    op.create_table(
        "usersettings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "trade_mode",
            postgresql.ENUM("paper", "broker", name="trademode", create_type=False),
            nullable=False,
        ),
        sa.Column("broker", sa.String(length=64), nullable=True),
        sa.Column("broker_status", sa.String(length=64), nullable=True),
        sa.Column("broker_creds_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_unique_constraint("uq_usersettings_user_id", "usersettings", ["user_id"])

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("order_type", sa.String(length=16), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "amo",
                "ongoing",
                "sell",
                "closed",
                name="orderstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("avg_price", sa.Float(), nullable=True),
        sa.Column("placed_at", sa.DateTime(), nullable=False),
        sa.Column("filled_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("orig_source", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_orders_user_status_symbol_time", "orders", ["user_id", "status", "symbol", "placed_at"]
    )

    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("avg_price", sa.Float(), nullable=False),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_unique_constraint("uq_positions_user_symbol", "positions", ["user_id", "symbol"])

    op.create_table(
        "fills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "pnldaily",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False),
        sa.Column("fees", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_unique_constraint("uq_pnl_daily_user_date", "pnldaily", ["user_id", "date"])

    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("rsi10", sa.Float(), nullable=True),
        sa.Column("ema9", sa.Float(), nullable=True),
        sa.Column("ema200", sa.Float(), nullable=True),
        sa.Column("distance_to_ema9", sa.Float(), nullable=True),
        sa.Column("clean_chart", sa.Boolean(), nullable=True),
        sa.Column("monthly_support_dist", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signals_symbol_ts", "signals", ["symbol", "ts"])

    op.create_table(
        "activity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("ref_id", sa.String(length=64), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("activity")
    op.drop_index("ix_signals_symbol_ts", table_name="signals")
    op.drop_table("signals")
    op.drop_constraint("uq_pnl_daily_user_date", "pnldaily", type_="unique")
    op.drop_table("pnldaily")
    op.drop_table("fills")
    op.drop_constraint("uq_positions_user_symbol", "positions", type_="unique")
    op.drop_table("positions")
    op.drop_index("ix_orders_user_status_symbol_time", table_name="orders")
    op.drop_table("orders")
    op.drop_constraint("uq_usersettings_user_id", "usersettings", type_="unique")
    op.drop_table("usersettings")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS trademode")
    op.execute("DROP TYPE IF EXISTS orderstatus")
