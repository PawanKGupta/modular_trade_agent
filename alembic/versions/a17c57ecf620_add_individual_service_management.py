"""add_individual_service_management

Revision ID: a17c57ecf620
Revises: 549edc0558e9
Create Date: 2025-11-18 02:30:00.000000+00:00
"""

import sqlalchemy as sa
from sqlalchemy import inspect, text

from alembic import op

# revision identifiers, used by Alembic.
revision = "a17c57ecf620"
down_revision = "549edc0558e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if tables already exist (in case they were created manually)
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # Create service_schedules table
    if "service_schedules" not in existing_tables:
        op.create_table(
            "service_schedules",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("task_name", sa.String(length=64), nullable=False),
            sa.Column("schedule_time", sa.Time(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("is_hourly", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("is_continuous", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("end_time", sa.Time(), nullable=True),
            sa.Column("description", sa.String(length=512), nullable=True),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("task_name", name="uq_service_schedule_task_name"),
        )
        op.create_index(
            "ix_service_schedules_task_name", "service_schedules", ["task_name"], unique=True
        )

    # Create individual_service_status table
    if "individual_service_status" not in existing_tables:
        op.create_table(
            "individual_service_status",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("task_name", sa.String(length=64), nullable=False),
            sa.Column("is_running", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("last_execution_at", sa.DateTime(), nullable=True),
            sa.Column("next_execution_at", sa.DateTime(), nullable=True),
            sa.Column("process_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "task_name", name="uq_individual_service_user_task"),
        )
        op.create_index(
            "ix_individual_service_user_task", "individual_service_status", ["user_id", "task_name"]
        )
        op.create_index(
            "ix_individual_service_status_user_id", "individual_service_status", ["user_id"]
        )

    # Create individual_service_task_execution table
    if "individual_service_task_execution" not in existing_tables:
        op.create_table(
            "individual_service_task_execution",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("task_name", sa.String(length=64), nullable=False),
            sa.Column("executed_at", sa.DateTime(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("duration_seconds", sa.Float(), nullable=False),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column(
                "execution_type", sa.String(length=16), nullable=False, server_default="'scheduled'"
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_individual_service_task_execution_user_id",
            "individual_service_task_execution",
            ["user_id"],
        )
        op.create_index(
            "ix_individual_service_task_execution_task_name",
            "individual_service_task_execution",
            ["task_name"],
        )
        op.create_index(
            "ix_individual_service_task_execution_status",
            "individual_service_task_execution",
            ["status"],
        )
        op.create_index(
            "ix_individual_service_task_user_name_time",
            "individual_service_task_execution",
            ["user_id", "task_name", "executed_at"],
        )

    # Insert default schedules (only if service_schedules table exists and is empty)
    connection = op.get_bind()

    default_schedules = [
        {
            "task_name": "premarket_retry",
            "schedule_time": "09:00:00",
            "enabled": True,
            "is_hourly": False,
            "is_continuous": False,
            "description": "Retry failed orders from previous day",
        },
        {
            "task_name": "sell_monitor",
            "schedule_time": "09:15:00",
            "enabled": True,
            "is_hourly": False,
            "is_continuous": True,
            "end_time": "15:30:00",
            "description": "Place sell orders and monitor continuously",
        },
        {
            "task_name": "position_monitor",
            "schedule_time": "09:30:00",
            "enabled": True,
            "is_hourly": True,
            "is_continuous": False,
            "description": "Monitor positions for reentry/exit signals (hourly)",
        },
        {
            "task_name": "analysis",
            "schedule_time": "16:00:00",
            "enabled": True,
            "is_hourly": False,
            "is_continuous": False,
            "description": "Analyze stocks and generate recommendations (admin-only)",
        },
        {
            "task_name": "buy_orders",
            "schedule_time": "16:05:00",
            "enabled": True,
            "is_hourly": False,
            "is_continuous": False,
            "description": "Place AMO buy orders for next day",
        },
        {
            "task_name": "eod_cleanup",
            "schedule_time": "18:00:00",
            "enabled": True,
            "is_hourly": False,
            "is_continuous": False,
            "description": "End-of-day cleanup and reset for next day",
        },
    ]

    # Only insert if table exists and is empty
    if "service_schedules" in existing_tables:
        result = connection.execute(text("SELECT COUNT(*) FROM service_schedules"))
        count = result.scalar()
        if count == 0:
            for schedule in default_schedules:
                connection.execute(
                    text(
                        """
                        INSERT INTO service_schedules
                        (task_name, schedule_time, enabled, is_hourly, is_continuous,
                         end_time, description, created_at, updated_at)
                        VALUES
                        (:task_name, :schedule_time, :enabled, :is_hourly, :is_continuous,
                         :end_time, :description, datetime('now'), datetime('now'))
                    """
                    ),
                    {
                        "task_name": schedule["task_name"],
                        "schedule_time": schedule["schedule_time"],
                        "enabled": 1 if schedule["enabled"] else 0,
                        "is_hourly": 1 if schedule.get("is_hourly", False) else 0,
                        "is_continuous": 1 if schedule.get("is_continuous", False) else 0,
                        "end_time": schedule.get("end_time"),
                        "description": schedule.get("description"),
                    },
                )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index(
        "ix_individual_service_task_user_name_time", table_name="individual_service_task_execution"
    )
    op.drop_index(
        "ix_individual_service_task_execution_status",
        table_name="individual_service_task_execution",
    )
    op.drop_index(
        "ix_individual_service_task_execution_task_name",
        table_name="individual_service_task_execution",
    )
    op.drop_index(
        "ix_individual_service_task_execution_user_id",
        table_name="individual_service_task_execution",
    )
    op.drop_table("individual_service_task_execution")

    op.drop_index("ix_individual_service_status_user_id", table_name="individual_service_status")
    op.drop_index("ix_individual_service_user_task", table_name="individual_service_status")
    op.drop_table("individual_service_status")

    op.drop_index("ix_service_schedules_task_name", table_name="service_schedules")
    op.drop_table("service_schedules")
