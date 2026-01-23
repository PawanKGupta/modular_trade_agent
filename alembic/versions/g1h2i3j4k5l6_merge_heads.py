"""merge_heads

Revision ID: g1h2i3j4k5l6
Revises: f1a2b3c4d5e6, d3afc70a65bb
Create Date: 2025-12-26 12:00:00.000000+00:00
"""

# revision identifiers, used by Alembic.
revision = "g1h2i3j4k5l6"
down_revision = ("f1a2b3c4d5e6", "d3afc70a65bb")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Merge multiple migration branches"""
    pass


def downgrade() -> None:
    """Downgrade"""
    pass
