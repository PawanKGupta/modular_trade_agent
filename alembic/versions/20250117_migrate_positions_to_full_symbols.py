# ruff: noqa
"""migrate_positions_to_full_symbols

Revision ID: a1b2c3d4e5f8
Revises: d1e2f3a4b5c6
Create Date: 2025-01-17 12:00:00.000000+00:00
"""

from sqlalchemy import inspect, text
from sqlalchemy.dialects import sqlite

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f8"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Migrate positions table from base symbols to full symbols.

    Strategy:
    1. For each position with base symbol (e.g., "RELIANCE")
    2. Find matching order(s) to get full symbol (e.g., "RELIANCE-EQ")
    3. Update position.symbol to full symbol
    4. If no matching order found, default to "{base_symbol}-EQ"

    Note: This migration assumes orders table already stores full symbols.
    """
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "positions" not in existing_tables:
        print("Warning: positions table does not exist, skipping migration")
        return

    # Increase symbol column length to 64 to accommodate full symbols like "SYMBOL-EQ"
    positions_columns = [col["name"] for col in inspector.get_columns("positions")]
    if "symbol" in positions_columns:
        # Alter column type to varchar(64) before updating symbols
        if isinstance(conn.dialect, sqlite.dialect):
            # SQLite doesn't support ALTER COLUMN directly
            # Since we are migrating to full symbols, just proceed - SQLite is flexible with types
            pass
        else:
            # PostgreSQL: expand column
            op.execute(text("ALTER TABLE positions ALTER COLUMN symbol TYPE VARCHAR(64)"))

    # Also expand orders.symbol if needed
    if "orders" in existing_tables:
        orders_columns = [col["name"] for col in inspector.get_columns("orders")]
        if "symbol" in orders_columns:
            if not isinstance(conn.dialect, sqlite.dialect):
                op.execute(text("ALTER TABLE orders ALTER COLUMN symbol TYPE VARCHAR(64)"))

    # Also expand signals.symbol if needed
    if "signals" in existing_tables:
        signals_columns = [col["name"] for col in inspector.get_columns("signals")]
        if "symbol" in signals_columns:
            if not isinstance(conn.dialect, sqlite.dialect):
                op.execute(text("ALTER TABLE signals ALTER COLUMN symbol TYPE VARCHAR(64)"))

    if isinstance(conn.dialect, sqlite.dialect):
        # SQLite version
        # Step 1: Update positions from matching orders
        op.execute(
            text(
                """
            UPDATE positions
            SET symbol = (
                SELECT o.symbol
                FROM orders o
                WHERE o.user_id = positions.user_id
                  AND o.side = 'buy'
                  AND o.status = 'ongoing'
                  AND UPPER(SUBSTR(o.symbol, 1, INSTR(o.symbol || '-', '-') - 1)) = \
                      UPPER(positions.symbol)
                ORDER BY o.placed_at DESC
                LIMIT 1
            )
            WHERE positions.symbol NOT LIKE '%-EQ'
              AND positions.symbol NOT LIKE '%-BE'
              AND positions.symbol NOT LIKE '%-BL'
              AND positions.symbol NOT LIKE '%-BZ'
              AND EXISTS (
                  SELECT 1 FROM orders o
                  WHERE o.user_id = positions.user_id
                    AND o.side = 'buy'
                    AND o.status = 'ongoing'
                    AND UPPER(SUBSTR(o.symbol, 1, INSTR(o.symbol || '-', '-') - 1)) = \
                      UPPER(positions.symbol)
              )
        """
            )
        )

        # Step 2: Default remaining base symbols to -EQ
        op.execute(
            text(
                """
            UPDATE positions
            SET symbol = symbol || '-EQ'
            WHERE symbol NOT LIKE '%-EQ'
              AND symbol NOT LIKE '%-BE'
              AND symbol NOT LIKE '%-BL'
              AND symbol NOT LIKE '%-BZ'
        """
            )
        )

        # Step 3: Verify migration (log positions that still don't have suffix)
        result = conn.execute(
            text(
                """
            SELECT user_id, symbol, quantity
            FROM positions
            WHERE symbol NOT LIKE '%-EQ'
              AND symbol NOT LIKE '%-BE'
              AND symbol NOT LIKE '%-BL'
              AND symbol NOT LIKE '%-BZ'
        """
            )
        )

        remaining = result.fetchall()
        if remaining:
            print(f"Warning: {len(remaining)} positions still have base symbols:")
            for row in remaining:
                print(f"  User {row[0]}: {row[1]} (qty: {row[2]})")
    else:
        # PostgreSQL version (not SQLite)
        # Step 1: Update positions from matching orders
        op.execute(
            text(
                """
            UPDATE positions p
            SET symbol = (
                SELECT o.symbol
                FROM orders o
                WHERE o.user_id = p.user_id
                  AND o.side = 'buy'
                  AND o.status = 'ongoing'
                  AND UPPER(SPLIT_PART(o.symbol, '-', 1)) = UPPER(p.symbol)
                ORDER BY o.placed_at DESC
                LIMIT 1
            )
            WHERE p.symbol NOT LIKE '%-EQ'
              AND p.symbol NOT LIKE '%-BE'
              AND p.symbol NOT LIKE '%-BL'
              AND p.symbol NOT LIKE '%-BZ'
              AND EXISTS (
                  SELECT 1 FROM orders o
                  WHERE o.user_id = p.user_id
                    AND o.side = 'buy'
                    AND o.status = 'ongoing'
                    AND UPPER(SPLIT_PART(o.symbol, '-', 1)) = UPPER(p.symbol)
              )
        """
            )
        )

        # Step 2: Default remaining base symbols to -EQ
        op.execute(
            text(
                """
            UPDATE positions
            SET symbol = symbol || '-EQ'
            WHERE symbol NOT LIKE '%-EQ'
              AND symbol NOT LIKE '%-BE'
              AND symbol NOT LIKE '%-BL'
              AND symbol NOT LIKE '%-BZ'
        """
            )
        )

        # Step 3: Verify migration
        result = conn.execute(
            text(
                """
            SELECT user_id, symbol, quantity
            FROM positions
            WHERE symbol NOT LIKE '%-EQ'
              AND symbol NOT LIKE '%-BE'
              AND symbol NOT LIKE '%-BL'
              AND symbol NOT LIKE '%-BZ'
        """
            )
        )

        remaining = result.fetchall()
        if remaining:
            print(f"Warning: {len(remaining)} positions still have base symbols:")
            for row in remaining:
                print(f"  User {row[0]}: {row[1]} (qty: {row[2]})")


def downgrade() -> None:
    """
    Revert to base symbols (extract base from full symbols).

    Note: This is a one-way migration in practice. Downgrade extracts
    base symbol by removing segment suffix.
    """
    conn = op.get_bind()

    if isinstance(conn.dialect, sqlite.dialect):
        # SQLite version
        op.execute(
            text(
                """
            UPDATE positions
            SET symbol = UPPER(SUBSTR(symbol, 1, INSTR(symbol || '-', '-') - 1))
            WHERE symbol LIKE '%-EQ' OR symbol LIKE '%-BE' \
                OR symbol LIKE '%-BL' OR symbol LIKE '%-BZ'
        """
            )
        )
    else:
        # PostgreSQL version
        op.execute(
            text(
                """
            UPDATE positions
            SET symbol = UPPER(SPLIT_PART(symbol, '-', 1))
            WHERE symbol LIKE '%-EQ' OR symbol LIKE '%-BE' \
                OR symbol LIKE '%-BL' OR symbol LIKE '%-BZ'
        """
            )
        )
