"""add_error_log_gin_index

Revision ID: f8a9b0c1d2e3
Revises: d1e2f3a4b5c6
Create Date: 2026-01-19 00:00:00.000000+00:00
"""

import sqlalchemy as sa
from sqlalchemy import inspect, text

from alembic import op

# revision identifiers, used by Alembic.
revision = "f8a9b0c1d2e3"
down_revision = "d1e2f3a4b5c6"  # Points to latest in chain that includes c9d8e7f6g5h6
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add GIN index for error_log.error_message to optimize ilike queries"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "error_logs" not in existing_tables:
        return

    # Get existing indexes
    existing_indexes = [idx["name"] for idx in inspector.get_indexes("error_logs")]

    # Check if pg_trgm extension is available (required for GIN index with gin_trgm_ops)
    # If not available, we'll create a simpler btree index as fallback
    try:
        # Try to enable pg_trgm extension
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.commit()
        use_gin = True
    except Exception:
        # Extension not available or permission denied - use btree index instead
        use_gin = False

    # Add GIN index for error_message (optimizes ilike queries)
    if "idx_error_log_error_message_gin" not in existing_indexes and "idx_error_log_error_message_btree" not in existing_indexes:
        try:
            if use_gin:
                # GIN index with trigram support (best for ilike queries)
                # Use raw SQL since op.create_index doesn't support GIN with gin_trgm_ops
                op.execute(
                    text(
                        """
                        CREATE INDEX IF NOT EXISTS idx_error_log_error_message_gin
                        ON error_logs USING gin(error_message gin_trgm_ops)
                        """
                    )
                )
            else:
                # Fallback: B-tree index (less efficient for ilike but still helps)
                op.create_index(
                    "idx_error_log_error_message_btree",
                    "error_logs",
                    ["error_message"],
                    unique=False,
                )
        except Exception as e:
            # Index creation might fail - log but continue
            print(f"Warning: Failed to create error_message index: {e}")

    # Ensure index on occurred_at exists (for ordering queries)
    # This should already exist from migration 0002, but check anyway
    if "ix_error_logs_occurred_at" not in existing_indexes:
        try:
            op.create_index(
                "ix_error_logs_occurred_at",
                "error_logs",
                ["occurred_at"],
                unique=False,
            )
        except Exception:
            # Index might already exist - continue
            pass


def downgrade() -> None:
    """Remove GIN index for error_log.error_message"""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "error_logs" not in existing_tables:
        return

    existing_indexes = [idx["name"] for idx in inspector.get_indexes("error_logs")]

    # Remove GIN index if it exists
    if "idx_error_log_error_message_gin" in existing_indexes:
        try:
            conn = op.get_bind()
            conn.execute(text("DROP INDEX IF EXISTS idx_error_log_error_message_gin"))
            conn.commit()
        except Exception:
            pass

    # Remove btree index if it exists (fallback)
    if "idx_error_log_error_message_btree" in existing_indexes:
        try:
            op.drop_index("idx_error_log_error_message_btree", table_name="error_logs")
        except Exception:
            pass

