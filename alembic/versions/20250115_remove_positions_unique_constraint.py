"""remove_positions_unique_constraint

Revision ID: 20250115_remove_positions_unique_constraint
Revises: 566893623349
Create Date: 2025-01-15 00:00:00.000000+00:00
"""

from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "20250115_remove_positions_unique_constraint"
down_revision = "566893623349"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove unique constraint on (user_id, symbol) to allow multiple positions per symbol."""
    # Detect database dialect
    bind = op.get_bind()
    inspector = inspect(bind)
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        # SQLite: Cannot drop constraints directly, so we recreate the table
        # Step 1: Create new table without the unique constraint
        op.execute(
            """
            CREATE TABLE positions_new (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                symbol VARCHAR(32) NOT NULL,
                quantity FLOAT NOT NULL,
                avg_price FLOAT NOT NULL DEFAULT 0.0,
                unrealized_pnl FLOAT NOT NULL DEFAULT 0.0,
                opened_at DATETIME NOT NULL,
                closed_at DATETIME,
                reentry_count INTEGER NOT NULL DEFAULT 0,
                reentries TEXT,
                initial_entry_price FLOAT,
                last_reentry_price FLOAT,
                entry_rsi FLOAT,
                FOREIGN KEY(user_id) REFERENCES users (id)
            )
            """
        )

        # Step 2: Copy all data from old table to new table
        op.execute(
            """
            INSERT INTO positions_new
            SELECT * FROM positions
            """
        )

        # Step 3: Drop old table
        op.execute("DROP TABLE positions")

        # Step 4: Rename new table to original name
        op.execute("ALTER TABLE positions_new RENAME TO positions")

        # Step 5: Recreate indexes (they were dropped with the old table)
        op.create_index("ix_positions_user_id", "positions", ["user_id"])
        op.create_index("ix_positions_symbol", "positions", ["symbol"])
        op.create_index("ix_positions_opened_at", "positions", ["opened_at"])

        # Step 6: Add performance index
        op.create_index(
            "idx_positions_user_symbol_closed_at",
            "positions",
            ["user_id", "symbol", "closed_at"],
            unique=False,
        )
    else:
        # PostgreSQL and other databases: Drop constraint and add partial unique index
        # Step 1: Drop the unique constraint
        op.drop_constraint("uq_positions_user_symbol", "positions", type_="unique")

        # Step 2: Add partial unique index for open positions only
        # This ensures only one open position per (user_id, symbol)
        op.create_index(
            "uq_positions_user_symbol_open",
            "positions",
            ["user_id", "symbol"],
            unique=True,
            postgresql_where=op.text("closed_at IS NULL"),
        )

        # Step 3: Add performance index
        op.create_index(
            "idx_positions_user_symbol_closed_at",
            "positions",
            ["user_id", "symbol", "closed_at"],
            unique=False,
        )


def downgrade() -> None:
    """Restore unique constraint on (user_id, symbol)."""
    bind = op.get_bind()
    inspector = inspect(bind)
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        # SQLite: Recreate table with unique constraint
        # Step 1: Create new table with unique constraint
        op.execute(
            """
            CREATE TABLE positions_old (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                symbol VARCHAR(32) NOT NULL,
                quantity FLOAT NOT NULL,
                avg_price FLOAT NOT NULL DEFAULT 0.0,
                unrealized_pnl FLOAT NOT NULL DEFAULT 0.0,
                opened_at DATETIME NOT NULL,
                closed_at DATETIME,
                reentry_count INTEGER NOT NULL DEFAULT 0,
                reentries TEXT,
                initial_entry_price FLOAT,
                last_reentry_price FLOAT,
                entry_rsi FLOAT,
                FOREIGN KEY(user_id) REFERENCES users (id),
                UNIQUE(user_id, symbol)
            )
            """
        )

        # Step 2: Copy data (keep only most recent position per symbol if duplicates exist)
        op.execute(
            """
            INSERT INTO positions_old
            SELECT id, user_id, symbol, quantity, avg_price, unrealized_pnl,
                   opened_at, closed_at, reentry_count, reentries,
                   initial_entry_price, last_reentry_price, entry_rsi
            FROM positions
            WHERE id IN (
                SELECT MAX(id) FROM positions GROUP BY user_id, symbol
            )
            """
        )

        # Step 3: Drop current table
        op.execute("DROP TABLE positions")

        # Step 4: Rename new table
        op.execute("ALTER TABLE positions_old RENAME TO positions")

        # Step 5: Recreate indexes
        op.create_index("ix_positions_user_id", "positions", ["user_id"])
        op.create_index("ix_positions_symbol", "positions", ["symbol"])
        op.create_index("ix_positions_opened_at", "positions", ["opened_at"])

        # Step 6: Drop performance index
        op.drop_index("idx_positions_user_symbol_closed_at", "positions")
    else:
        # PostgreSQL and other databases: Drop partial index and restore unique constraint
        # Step 1: Drop partial unique index
        op.drop_index("uq_positions_user_symbol_open", "positions")

        # Step 2: Drop performance index
        op.drop_index("idx_positions_user_symbol_closed_at", "positions")

        # Step 3: Restore unique constraint
        op.create_unique_constraint("uq_positions_user_symbol", "positions", ["user_id", "symbol"])
