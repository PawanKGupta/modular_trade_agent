"""merge error_log_gin_index and fills_table_schema

Revision ID: 98f30c943faa
Revises: b9c0cf7b482d, f8a9b0c1d2e3
Create Date: 2026-01-19 19:39:16.712881+00:00
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '98f30c943faa'
down_revision = ('b9c0cf7b482d', 'f8a9b0c1d2e3')
branch_labels = None
depends_on = None

def upgrade() -> None:
	pass

def downgrade() -> None:
	pass
