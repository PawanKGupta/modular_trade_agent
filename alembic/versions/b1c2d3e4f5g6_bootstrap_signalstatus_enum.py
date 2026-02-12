"""bootstrap signalstatus enum

Revision ID: b1c2d3e4f5g6
Revises: ec709f132d06
Create Date: 2025-12-26 10:15:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5g6"
down_revision = "ec709f132d06"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "postgresql":
        # Ensure the enum type exists early in the graph; CREATE TYPE IF NOT EXISTS is not
        # supported for enums, so we check pg_type/pg_enum and create only if missing.
        with op.get_context().autocommit_block():
            exists = bind.execute(
                text(
                    """
                    SELECT 1
                    FROM pg_type t
                    JOIN pg_enum e ON e.enumtypid = t.oid
                    WHERE t.typname = 'signalstatus'
                    LIMIT 1
                    """
                )
            ).scalar() is not None

            if not exists:
                bind.execute(text("CREATE TYPE signalstatus AS ENUM ('inactive', 'active', 'completed', 'failed')"))
    else:
        # SQLite and others: nothing to do; SQLAlchemy handles enums without server types.
        pass


def downgrade():
    # No-op: dropping the enum type could break existing columns; keep type.
    pass
