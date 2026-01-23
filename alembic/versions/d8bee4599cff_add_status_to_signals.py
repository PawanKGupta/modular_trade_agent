# ruff: noqa
"""add_status_to_signals

Revision ID: d8bee4599cff
Revises: ec709f132d06
Create Date: 2025-11-26 21:07:22.633714+00:00

"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "d8bee4599cff"
down_revision = "ec709f132d06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "signals" not in existing_tables:
        return

    signals_columns = [col["name"] for col in inspector.get_columns("signals")]

    # Only add status column if it doesn't exist
    if "status" not in signals_columns:
        # Ensure enum type exists on Postgres, using autocommit and pg_enum check
        if op.get_bind().dialect.name == "postgresql":
            try:
                with op.get_context().autocommit_block():
                    exists = (
                        op.get_bind()
                        .execute(
                            sa.text(
                                """
                            SELECT EXISTS (
                                SELECT 1 FROM pg_enum e
                                JOIN pg_type t ON e.enumtypid = t.oid
                                WHERE t.typname = 'signalstatus'
                            )
                            """
                            )
                        )
                        .scalar()
                    )
                    if not exists:
                        op.execute(
                            sa.text(
                                "CREATE TYPE signalstatus AS ENUM ('ACTIVE', 'EXPIRED', 'TRADED', 'REJECTED')"
                            )
                        )
            except Exception:
                # If it already exists or creation fails, continue — column add will reference existing type
                pass

        # Reference existing enum type without implicit CREATE TYPE during column add
        signal_status_enum = sa.Enum(
            "ACTIVE", "EXPIRED", "TRADED", "REJECTED", name="signalstatus", create_type=False
        )

        # Add status column with default value 'ACTIVE'
        op.add_column(
            "signals",
            sa.Column("status", signal_status_enum, nullable=False, server_default="ACTIVE"),
        )

        # Create index on status column for faster filtering
        op.create_index("ix_signals_status", "signals", ["status"])


def downgrade() -> None:
    # Drop index
    op.drop_index("ix_signals_status", "signals")

    # Drop status column
    op.drop_column("signals", "status")

    # Drop enum type
    signal_status_enum = sa.Enum("ACTIVE", "EXPIRED", "TRADED", "REJECTED", name="signalstatus")
    signal_status_enum.drop(op.get_bind(), checkfirst=True)
