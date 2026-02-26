"""Convert task execution executed_at from UTC to IST (naive clock time)

Task execution tables use TIMESTAMP WITHOUT TIME ZONE. When the app wrote
timezone-aware IST (e.g. 16:00+05:30), psycopg2 converted to UTC before storing
(10:30), so DB showed 10:30 instead of 4:00 PM IST. New code writes naive IST.
This migration converts existing UTC values to IST clock time (add 5h 30m) so
all rows display correctly (e.g. 6:00 PM, 4:05 PM, 4:00 PM).

PostgreSQL only; SQLite stores without conversion so no change needed there.
"""

from sqlalchemy import text

from alembic import op

revision = "20260204_task_exec_ist"
down_revision = "20260202_merge_all"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    dialect_name = conn.dialect.name
    if dialect_name != "postgresql":
        return
    # Convert stored UTC to IST clock time (add 5 hours 30 minutes)
    conn.execute(
        text(
            "UPDATE service_task_execution SET executed_at = executed_at + INTERVAL '5 hours 30 minutes'"
        )
    )
    conn.execute(
        text(
            "UPDATE individual_service_task_execution SET executed_at = executed_at + INTERVAL '5 hours 30 minutes'"
        )
    )


def downgrade():
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return
    conn.execute(
        text(
            "UPDATE service_task_execution SET executed_at = executed_at - INTERVAL '5 hours 30 minutes'"
        )
    )
    conn.execute(
        text(
            "UPDATE individual_service_task_execution SET executed_at = executed_at - INTERVAL '5 hours 30 minutes'"
        )
    )
