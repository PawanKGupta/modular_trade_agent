"""add_status_to_signals

Revision ID: d8bee4599cff
Revises: ec709f132d06
Create Date: 2025-11-26 21:07:22.633714+00:00

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "d8bee4599cff"
down_revision = "ec709f132d06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create SignalStatus enum type (uppercase to match Python enum)
    signal_status_enum = sa.Enum("ACTIVE", "EXPIRED", "TRADED", "REJECTED", name="signalstatus")
    signal_status_enum.create(op.get_bind(), checkfirst=True)

    # Add status column with default value 'ACTIVE'
    op.add_column(
        "signals", sa.Column("status", signal_status_enum, nullable=False, server_default="ACTIVE")
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
