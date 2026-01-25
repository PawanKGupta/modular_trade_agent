"""consolidate multiple migration heads into single head - step 1

Revision ID: f7e6d5c4b3a2
Revises: 98f30c943faa, g1h2i3j4k5l6
Create Date: 2026-01-26 02:00:00
"""

# revision identifiers, used by Alembic.
revision = "f7e6d5c4b3a2"
down_revision = ("98f30c943faa", "g1h2i3j4k5l6")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Merge multiple migration branches into single head"""
    pass


def downgrade() -> None:
    """Reverse merge"""
    pass
