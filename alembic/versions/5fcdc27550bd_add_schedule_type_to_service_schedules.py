"""add_schedule_type_to_service_schedules

Revision ID: 5fcdc27550bd
Revises: 2a037cee1fc2
Create Date: 2025-11-18 21:24:54.946659+00:00
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "5fcdc27550bd"
down_revision = "2a037cee1fc2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if column already exists
    conn = op.get_bind()
    inspector = inspect(conn)

    if "service_schedules" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("service_schedules")]
        if "schedule_type" not in columns:
            op.add_column(
                "service_schedules",
                sa.Column(
                    "schedule_type", sa.String(length=16), nullable=False, server_default="daily"
                ),
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if "service_schedules" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("service_schedules")]
        if "schedule_type" in columns:
            op.drop_column("service_schedules", "schedule_type")
