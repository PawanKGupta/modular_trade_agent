"""Morning buy schedule + evening margin preview task.

Revision ID: 20260520_morning_buy
Revises: 20260510_ml_price_enabled
Create Date: 2026-05-20
"""

from sqlalchemy import inspect, text

from alembic import op

revision = "20260520_morning_buy"
down_revision = "20260510_ml_price_enabled"
branch_labels = None
depends_on = None

_TABLE = "service_schedules"


def upgrade() -> None:
    conn = op.get_bind()
    if _TABLE not in inspect(conn).get_table_names():
        return

    op.execute(
        text(
            """
            UPDATE service_schedules
            SET schedule_time = '09:01:00',
                description = 'Place REGULAR buy orders at market open (after prior-day analysis)'
            WHERE task_name = 'buy_orders'
            """
        )
    )
    op.execute(
        text(
            """
            UPDATE service_schedules
            SET schedule_time = '09:03:00',
                description = 'Retry failed buy orders (runs after morning buy placement)'
            WHERE task_name = 'premarket_retry'
            """
        )
    )

    existing = conn.execute(
        text("SELECT task_name FROM service_schedules WHERE task_name = 'buy_margin_preview'")
    ).fetchone()
    if not existing:
        conn.execute(
            text(
                """
                INSERT INTO service_schedules (
                    task_name, schedule_time, enabled, is_hourly, is_continuous,
                    schedule_type, description
                ) VALUES (
                    :task_name, :schedule_time, :enabled, :is_hourly, :is_continuous,
                    :schedule_type, :description
                )
                """
            ),
            {
                "task_name": "buy_margin_preview",
                "schedule_time": "16:05:00",
                "enabled": True,
                "is_hourly": False,
                "is_continuous": False,
                "schedule_type": "daily",
                "description": "Evening margin preview for next-morning buys (notify only)",
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _TABLE not in inspect(conn).get_table_names():
        return

    op.execute(
        text(
            """
            UPDATE service_schedules
            SET schedule_time = '16:05:00',
                description = 'Place AMO buy orders for next day'
            WHERE task_name = 'buy_orders'
            """
        )
    )
    op.execute(
        text(
            """
            UPDATE service_schedules
            SET schedule_time = '09:00:00',
                description = 'Retry failed orders from previous day'
            WHERE task_name = 'premarket_retry'
            """
        )
    )
    op.execute(text("DELETE FROM service_schedules WHERE task_name = 'buy_margin_preview'"))
