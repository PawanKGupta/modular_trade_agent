"""merge signal bootstrap and existing heads

Revision ID: deadc0de1234
Revises: c78fbbb4ba6f
Create Date: 2025-12-26 13:20:00
"""

# revision identifiers, used by Alembic.
revision = "deadc0de1234"
down_revision = "c78fbbb4ba6f"
branch_labels = None
depends_on = None


def upgrade():
    # Merge point only; no schema changes required.
    pass


def downgrade():
    # No automatic downgrade; splitting branches is not supported.
    pass
