"""phase1 multi-user schema extensions

Revision ID: 0002_phase1
Revises: 0001_initial
Create Date: 2025-01-15
"""

import sqlalchemy as sa

from alembic import op

revision = "0002_phase1"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add broker-specific fields to orders table (only if they don't exist)
    from sqlalchemy import inspect

    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    orders_columns = (
        [col["name"] for col in inspector.get_columns("orders")]
        if "orders" in existing_tables
        else []
    )

    if "order_id" not in orders_columns:
        op.add_column("orders", sa.Column("order_id", sa.String(length=64), nullable=True))
    if "broker_order_id" not in orders_columns:
        op.add_column("orders", sa.Column("broker_order_id", sa.String(length=64), nullable=True))

    # Fix activity table: add foreign key constraint for user_id
    # SQLite doesn't support ALTER TABLE for foreign keys, so we use batch mode
    # Check if index/constraint already exist - skip if they do
    try:
        activity_indexes = [idx["name"] for idx in inspector.get_indexes("activity")]
        activity_fks = [fk["name"] for fk in inspector.get_foreign_keys("activity")]

        if (
            "ix_activity_user_id" not in activity_indexes
            or "fk_activity_user_id" not in activity_fks
        ):
            with op.batch_alter_table("activity", schema=None) as batch_op:
                if "fk_activity_user_id" not in activity_fks:
                    batch_op.create_foreign_key(
                        "fk_activity_user_id", "users", ["user_id"], ["id"], ondelete="SET NULL"
                    )
                if "ix_activity_user_id" not in activity_indexes:
                    batch_op.create_index("ix_activity_user_id", ["user_id"])
    except Exception:
        # If activity table doesn't exist or constraints already exist, skip
        pass

    # ServiceStatus table (only if it doesn't exist)
    if "service_status" not in existing_tables:
        op.create_table(
            "service_status",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("service_running", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("last_heartbeat", sa.DateTime(), nullable=True),
            sa.Column("last_task_execution", sa.DateTime(), nullable=True),
            sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error", sa.String(length=512), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_service_status_user_id", "service_status", ["user_id"], unique=True)

    # ServiceTaskExecution table
    if "service_task_execution" not in existing_tables:
        op.create_table(
            "service_task_execution",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("task_name", sa.String(length=64), nullable=False),
            sa.Column("executed_at", sa.DateTime(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("duration_seconds", sa.Float(), nullable=False),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_service_task_execution_user_id", "service_task_execution", ["user_id"])
        op.create_index(
            "ix_service_task_execution_task_name", "service_task_execution", ["task_name"]
        )
        op.create_index("ix_service_task_execution_status", "service_task_execution", ["status"])
        op.create_index(
            "ix_service_task_user_name_time",
            "service_task_execution",
            ["user_id", "task_name", "executed_at"],
        )

    # ServiceLog table
    if "service_logs" not in existing_tables:
        op.create_table(
            "service_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("level", sa.String(length=16), nullable=False),
            sa.Column("module", sa.String(length=128), nullable=False),
            sa.Column("message", sa.String(length=1024), nullable=False),
            sa.Column("context", sa.JSON(), nullable=True),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_service_logs_user_id", "service_logs", ["user_id"])
        op.create_index("ix_service_logs_level", "service_logs", ["level"])
        op.create_index("ix_service_logs_timestamp", "service_logs", ["timestamp"])
        op.create_index(
            "ix_service_logs_user_timestamp_level",
            "service_logs",
            ["user_id", "timestamp", "level"],
        )

    # ErrorLog table
    if "error_logs" not in existing_tables:
        op.create_table(
            "error_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("error_type", sa.String(length=128), nullable=False),
            sa.Column("error_message", sa.String(length=1024), nullable=False),
            sa.Column("traceback", sa.String(length=8192), nullable=True),
            sa.Column("context", sa.JSON(), nullable=True),
            sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("resolved_by", sa.Integer(), nullable=True),
            sa.Column("resolution_notes", sa.String(length=512), nullable=True),
            sa.Column("occurred_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_error_logs_user_id", "error_logs", ["user_id"])
        op.create_index("ix_error_logs_occurred_at", "error_logs", ["occurred_at"])
        op.create_index("ix_error_logs_resolved", "error_logs", ["resolved"])
        op.create_index(
            "ix_error_logs_user_occurred_resolved",
            "error_logs",
            ["user_id", "occurred_at", "resolved"],
        )

    # UserTradingConfig table
    if "user_trading_config" not in existing_tables:
        op.create_table(
            "user_trading_config",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            # Strategy Parameters
            sa.Column("rsi_period", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("rsi_oversold", sa.Float(), nullable=False, server_default="30.0"),
            sa.Column("rsi_extreme_oversold", sa.Float(), nullable=False, server_default="20.0"),
            sa.Column("rsi_near_oversold", sa.Float(), nullable=False, server_default="40.0"),
            # Capital & Position Management
            sa.Column("user_capital", sa.Float(), nullable=False, server_default="200000.0"),
            sa.Column("max_portfolio_size", sa.Integer(), nullable=False, server_default="6"),
            sa.Column(
                "max_position_volume_ratio", sa.Float(), nullable=False, server_default="0.10"
            ),
            sa.Column(
                "min_absolute_avg_volume", sa.Integer(), nullable=False, server_default="10000"
            ),
            # Chart Quality Filters
            sa.Column(
                "chart_quality_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column("chart_quality_min_score", sa.Float(), nullable=False, server_default="50.0"),
            sa.Column(
                "chart_quality_max_gap_frequency", sa.Float(), nullable=False, server_default="25.0"
            ),
            sa.Column(
                "chart_quality_min_daily_range_pct",
                sa.Float(),
                nullable=False,
                server_default="1.0",
            ),
            sa.Column(
                "chart_quality_max_extreme_candle_frequency",
                sa.Float(),
                nullable=False,
                server_default="20.0",
            ),
            # Risk Management (stop loss is optional/future feature)
            sa.Column("default_stop_loss_pct", sa.Float(), nullable=True),
            sa.Column("tight_stop_loss_pct", sa.Float(), nullable=True),
            sa.Column("min_stop_loss_pct", sa.Float(), nullable=True),
            sa.Column("default_target_pct", sa.Float(), nullable=False, server_default="0.10"),
            sa.Column("strong_buy_target_pct", sa.Float(), nullable=False, server_default="0.12"),
            sa.Column("excellent_target_pct", sa.Float(), nullable=False, server_default="0.15"),
            # Risk-Reward Ratios
            sa.Column("strong_buy_risk_reward", sa.Float(), nullable=False, server_default="3.0"),
            sa.Column("buy_risk_reward", sa.Float(), nullable=False, server_default="2.5"),
            sa.Column("excellent_risk_reward", sa.Float(), nullable=False, server_default="3.5"),
            # Order Defaults
            sa.Column(
                "default_exchange", sa.String(length=8), nullable=False, server_default="NSE"
            ),
            sa.Column("default_product", sa.String(length=8), nullable=False, server_default="CNC"),
            sa.Column(
                "default_order_type", sa.String(length=16), nullable=False, server_default="MARKET"
            ),
            sa.Column("default_variety", sa.String(length=8), nullable=False, server_default="AMO"),
            sa.Column(
                "default_validity", sa.String(length=8), nullable=False, server_default="DAY"
            ),
            # Behavior Toggles
            sa.Column(
                "allow_duplicate_recommendations_same_day",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "exit_on_ema9_or_rsi50", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column("min_combined_score", sa.Integer(), nullable=False, server_default="25"),
            # News Sentiment
            sa.Column(
                "news_sentiment_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column(
                "news_sentiment_lookback_days", sa.Integer(), nullable=False, server_default="30"
            ),
            sa.Column(
                "news_sentiment_min_articles", sa.Integer(), nullable=False, server_default="2"
            ),
            sa.Column(
                "news_sentiment_pos_threshold", sa.Float(), nullable=False, server_default="0.25"
            ),
            sa.Column(
                "news_sentiment_neg_threshold", sa.Float(), nullable=False, server_default="-0.25"
            ),
            # ML Configuration
            sa.Column("ml_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("ml_model_version", sa.String(length=16), nullable=True),
            sa.Column("ml_confidence_threshold", sa.Float(), nullable=False, server_default="0.5"),
            sa.Column(
                "ml_combine_with_rules", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            # Scheduling Preferences
            sa.Column("task_schedule", sa.JSON(), nullable=True),
            # Timestamps
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_user_trading_config_user_id", "user_trading_config", ["user_id"], unique=True
        )

    # MLTrainingJob table
    if "ml_training_jobs" not in existing_tables:
        op.create_table(
            "ml_training_jobs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("started_by", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("model_type", sa.String(length=64), nullable=False),
            sa.Column("algorithm", sa.String(length=32), nullable=False),
            sa.Column("training_data_path", sa.String(length=512), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("model_path", sa.String(length=512), nullable=True),
            sa.Column("accuracy", sa.Float(), nullable=True),
            sa.Column("error_message", sa.String(length=1024), nullable=True),
            sa.Column("logs", sa.String(length=16384), nullable=True),
            sa.ForeignKeyConstraint(["started_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_ml_training_jobs_started_by", "ml_training_jobs", ["started_by"])
        op.create_index("ix_ml_training_jobs_status", "ml_training_jobs", ["status"])

    # MLModel table
    if "ml_models" not in existing_tables:
        op.create_table(
            "ml_models",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("model_type", sa.String(length=64), nullable=False),
            sa.Column("version", sa.String(length=16), nullable=False),
            sa.Column("model_path", sa.String(length=512), nullable=False),
            sa.Column("accuracy", sa.Float(), nullable=True),
            sa.Column("training_job_id", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["training_job_id"], ["ml_training_jobs.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_ml_models_model_type", "ml_models", ["model_type"])
        op.create_index("ix_ml_models_version", "ml_models", ["version"])
        op.create_index("ix_ml_models_is_active", "ml_models", ["is_active"])
        op.create_unique_constraint(
            "uq_ml_models_type_version", "ml_models", ["model_type", "version"]
        )

    # UserNotificationPreferences table
    if "user_notification_preferences" not in existing_tables:
        op.create_table(
            "user_notification_preferences",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            # Notification channels
            sa.Column("telegram_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("telegram_chat_id", sa.String(length=64), nullable=True),
            sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("email_address", sa.String(length=255), nullable=True),
            sa.Column("in_app_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            # Notification types
            sa.Column(
                "notify_service_events", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column(
                "notify_trading_events", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column(
                "notify_system_events", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column("notify_errors", sa.Boolean(), nullable=False, server_default=sa.true()),
            # Quiet hours (optional)
            sa.Column("quiet_hours_start", sa.Time(), nullable=True),
            sa.Column("quiet_hours_end", sa.Time(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_user_notification_preferences_user_id",
            "user_notification_preferences",
            ["user_id"],
            unique=True,
        )

    # Notification table
    if "notifications" not in existing_tables:
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("type", sa.String(length=32), nullable=False),
            sa.Column("level", sa.String(length=16), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("message", sa.String(length=1024), nullable=False),
            sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            # Delivery status
            sa.Column("telegram_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("email_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("in_app_delivered", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
        op.create_index("ix_notifications_type", "notifications", ["type"])
        op.create_index("ix_notifications_level", "notifications", ["level"])
        op.create_index("ix_notifications_read", "notifications", ["read"])
        op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
        op.create_index(
            "ix_notifications_user_read_created",
            "notifications",
            ["user_id", "read", "created_at"],
        )

    # AuditLog table
    if "audit_logs" not in existing_tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column("resource_type", sa.String(length=64), nullable=False),
            sa.Column("resource_id", sa.Integer(), nullable=True),
            sa.Column("changes", sa.JSON(), nullable=True),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column("user_agent", sa.String(length=512), nullable=True),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
        op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
        op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
        op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
        op.create_index(
            "ix_audit_logs_user_timestamp_type",
            "audit_logs",
            ["user_id", "timestamp", "resource_type"],
        )


def downgrade() -> None:
    # Drop new tables in reverse order
    op.drop_index("ix_audit_logs_user_timestamp_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_timestamp", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_notifications_user_read_created", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_read", table_name="notifications")
    op.drop_index("ix_notifications_level", table_name="notifications")
    op.drop_index("ix_notifications_type", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index(
        "ix_user_notification_preferences_user_id", table_name="user_notification_preferences"
    )
    op.drop_table("user_notification_preferences")

    op.drop_constraint("uq_ml_models_type_version", "ml_models", type_="unique")
    op.drop_index("ix_ml_models_is_active", table_name="ml_models")
    op.drop_index("ix_ml_models_version", table_name="ml_models")
    op.drop_index("ix_ml_models_model_type", table_name="ml_models")
    op.drop_table("ml_models")

    op.drop_index("ix_ml_training_jobs_status", table_name="ml_training_jobs")
    op.drop_index("ix_ml_training_jobs_started_by", table_name="ml_training_jobs")
    op.drop_table("ml_training_jobs")

    op.drop_index("ix_user_trading_config_user_id", table_name="user_trading_config")
    op.drop_table("user_trading_config")

    op.drop_index("ix_error_logs_user_occurred_resolved", table_name="error_logs")
    op.drop_index("ix_error_logs_resolved", table_name="error_logs")
    op.drop_index("ix_error_logs_occurred_at", table_name="error_logs")
    op.drop_index("ix_error_logs_user_id", table_name="error_logs")
    op.drop_table("error_logs")

    op.drop_index("ix_service_logs_user_timestamp_level", table_name="service_logs")
    op.drop_index("ix_service_logs_timestamp", table_name="service_logs")
    op.drop_index("ix_service_logs_level", table_name="service_logs")
    op.drop_index("ix_service_logs_user_id", table_name="service_logs")
    op.drop_table("service_logs")

    op.drop_index("ix_service_task_user_name_time", table_name="service_task_execution")
    op.drop_index("ix_service_task_execution_status", table_name="service_task_execution")
    op.drop_index("ix_service_task_execution_task_name", table_name="service_task_execution")
    op.drop_index("ix_service_task_execution_user_id", table_name="service_task_execution")
    op.drop_table("service_task_execution")

    op.drop_index("ix_service_status_user_id", table_name="service_status")
    op.drop_table("service_status")

    # Fix activity table: remove foreign key and index
    # SQLite doesn't support ALTER TABLE for foreign keys, so we use batch mode
    with op.batch_alter_table("activity", schema=None) as batch_op:
        batch_op.drop_index("ix_activity_user_id")
        batch_op.drop_constraint("fk_activity_user_id", type_="foreignkey")

    # Remove broker-specific fields from orders table
    op.drop_column("orders", "broker_order_id")
    op.drop_column("orders", "order_id")
