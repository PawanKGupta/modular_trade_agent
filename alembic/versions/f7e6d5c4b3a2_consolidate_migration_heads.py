"""consolidate multiple migration heads into single head

Revision ID: f7e6d5c4b3a2
Revises: g1h2i3j4k5l6, aa11bb22cc33
Create Date: 2026-01-26 02:00:00
"""

# revision identifiers, used by Alembic.
revision = "f7e6d5c4b3a2"
down_revision = ("g1h2i3j4k5l6", "aa11bb22cc33")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Merge multiple migration branches into single head"""
    pass


def downgrade() -> None:
    """Reverse merge"""
    pass
