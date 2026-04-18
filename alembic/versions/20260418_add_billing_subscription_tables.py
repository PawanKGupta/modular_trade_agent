# ruff: noqa
"""Add billing / subscription tables and notification billing columns

Revision ID: 20260418_billing_sub
Revises: 20260204_merge_final
Create Date: 2026-04-18
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260418_billing_sub"
down_revision = "20260204_merge_final"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if "subscription_plans" not in tables:
        op.create_table(
            "subscription_plans",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("slug", sa.String(64), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.String(1024), nullable=True),
            sa.Column("plan_tier", sa.String(32), nullable=False),
            sa.Column("billing_interval", sa.String(16), nullable=False),
            sa.Column("base_amount_paise", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(8), nullable=False, server_default="INR"),
            sa.Column("features_json", sa.JSON(), nullable=False),
            sa.Column("razorpay_plan_id", sa.String(128), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_subscription_plans_slug", "subscription_plans", ["slug"], unique=True)
        op.create_index(
            "ix_subscription_plans_razorpay_plan_id", "subscription_plans", ["razorpay_plan_id"]
        )

    if "plan_price_schedules" not in tables:
        op.create_table(
            "plan_price_schedules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "plan_id", sa.Integer(), sa.ForeignKey("subscription_plans.id"), nullable=False
            ),
            sa.Column("amount_paise", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(8), nullable=False, server_default="INR"),
            sa.Column("effective_from", sa.DateTime(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="scheduled"),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_plan_price_schedules_plan_id", "plan_price_schedules", ["plan_id"])
        op.create_index(
            "ix_plan_price_schedules_effective_from", "plan_price_schedules", ["effective_from"]
        )

    if "coupons" not in tables:
        op.create_table(
            "coupons",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("discount_type", sa.String(32), nullable=False),
            sa.Column("discount_value", sa.Integer(), nullable=False),
            sa.Column("max_redemptions", sa.Integer(), nullable=True),
            sa.Column("per_user_max", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("valid_from", sa.DateTime(), nullable=True),
            sa.Column("valid_until", sa.DateTime(), nullable=True),
            sa.Column("allowed_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("allowed_plan_ids", sa.JSON(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_coupons_code", "coupons", ["code"], unique=True)
        op.create_index("ix_coupons_allowed_user_id", "coupons", ["allowed_user_id"])

    if "user_subscriptions" not in tables:
        op.create_table(
            "user_subscriptions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column(
                "plan_id", sa.Integer(), sa.ForeignKey("subscription_plans.id"), nullable=False
            ),
            sa.Column("plan_tier_snapshot", sa.String(32), nullable=False),
            sa.Column("features_snapshot", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("billing_provider", sa.String(32), nullable=False, server_default="razorpay"),
            sa.Column("razorpay_subscription_id", sa.String(128), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("current_period_end", sa.DateTime(), nullable=True),
            sa.Column(
                "cancel_at_period_end",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("trial_end", sa.DateTime(), nullable=True),
            sa.Column("grace_until", sa.DateTime(), nullable=True),
            sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column(
                "pending_plan_id",
                sa.Integer(),
                sa.ForeignKey("subscription_plans.id"),
                nullable=True,
            ),
            sa.Column("last_renewal_reminder_for_period_end", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_user_subscriptions_user_id", "user_subscriptions", ["user_id"])
        op.create_index("ix_user_subscriptions_status", "user_subscriptions", ["status"])
        op.create_index(
            "ix_user_subscriptions_razorpay_subscription_id",
            "user_subscriptions",
            ["razorpay_subscription_id"],
        )
        op.create_index(
            "ix_user_subscriptions_current_period_end", "user_subscriptions", ["current_period_end"]
        )
        op.create_index(
            "ix_user_subscriptions_user_status", "user_subscriptions", ["user_id", "status"]
        )

    if "coupon_redemptions" not in tables:
        op.create_table(
            "coupon_redemptions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("coupon_id", sa.Integer(), sa.ForeignKey("coupons.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column(
                "user_subscription_id",
                sa.Integer(),
                sa.ForeignKey("user_subscriptions.id"),
                nullable=True,
            ),
            sa.Column("redeemed_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_coupon_redemptions_coupon_id", "coupon_redemptions", ["coupon_id"])
        op.create_index("ix_coupon_redemptions_user_id", "coupon_redemptions", ["user_id"])

    if "user_billing_profiles" not in tables:
        op.create_table(
            "user_billing_profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("razorpay_customer_id", sa.String(128), nullable=True),
            sa.Column("default_payment_method_id", sa.String(128), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_user_billing_profiles_user_id", "user_billing_profiles", ["user_id"], unique=True
        )
        op.create_index(
            "ix_user_billing_profiles_razorpay_customer_id",
            "user_billing_profiles",
            ["razorpay_customer_id"],
        )

    if "billing_transactions" not in tables:
        op.create_table(
            "billing_transactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_subscription_id",
                sa.Integer(),
                sa.ForeignKey("user_subscriptions.id"),
                nullable=True,
            ),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("razorpay_payment_id", sa.String(128), nullable=True),
            sa.Column("razorpay_invoice_id", sa.String(128), nullable=True),
            sa.Column("amount_paise", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(8), nullable=False, server_default="INR"),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("failure_reason", sa.String(512), nullable=True),
            sa.Column("idempotency_key", sa.String(128), nullable=True),
            sa.Column("raw_event_digest", sa.String(64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_billing_transactions_user_subscription_id",
            "billing_transactions",
            ["user_subscription_id"],
        )
        op.create_index("ix_billing_transactions_user_id", "billing_transactions", ["user_id"])
        op.create_index(
            "ix_billing_transactions_razorpay_payment_id",
            "billing_transactions",
            ["razorpay_payment_id"],
        )
        op.create_index(
            "ix_billing_transactions_razorpay_invoice_id",
            "billing_transactions",
            ["razorpay_invoice_id"],
        )
        op.create_index("ix_billing_transactions_status", "billing_transactions", ["status"])
        op.create_index(
            "ix_billing_transactions_idempotency_key",
            "billing_transactions",
            ["idempotency_key"],
            unique=True,
        )

    if "billing_refunds" not in tables:
        op.create_table(
            "billing_refunds",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "billing_transaction_id",
                sa.Integer(),
                sa.ForeignKey("billing_transactions.id"),
                nullable=False,
            ),
            sa.Column("razorpay_refund_id", sa.String(128), nullable=True),
            sa.Column("amount_paise", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("reason", sa.String(512), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_billing_refunds_billing_transaction_id",
            "billing_refunds",
            ["billing_transaction_id"],
        )
        op.create_index(
            "ix_billing_refunds_razorpay_refund_id", "billing_refunds", ["razorpay_refund_id"]
        )

    if "billing_admin_settings" not in tables:
        op.create_table(
            "billing_admin_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "payment_card_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
            ),
            sa.Column(
                "payment_upi_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
            ),
            sa.Column("default_trial_days", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("grace_period_days", sa.Integer(), nullable=False, server_default="3"),
            sa.Column(
                "renewal_reminder_days_before", sa.Integer(), nullable=False, server_default="7"
            ),
            sa.Column(
                "dunning_retry_interval_hours", sa.Integer(), nullable=False, server_default="24"
            ),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    if "free_trial_usage" not in tables:
        op.create_table(
            "free_trial_usage",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("trial_key", sa.String(64), nullable=False),
            sa.Column("consumed_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_free_trial_usage_user_id", "free_trial_usage", ["user_id"])
        op.create_unique_constraint(
            "uq_free_trial_user_key", "free_trial_usage", ["user_id", "trial_key"]
        )

    if "razorpay_webhook_events" not in tables:
        op.create_table(
            "razorpay_webhook_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("event_id", sa.String(128), nullable=False),
            sa.Column("event_type", sa.String(128), nullable=False),
            sa.Column("received_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_razorpay_webhook_events_event_id",
            "razorpay_webhook_events",
            ["event_id"],
            unique=True,
        )

    # Seed singleton settings + default plans (idempotent)
    inspector = inspect(conn)
    tables_after = inspector.get_table_names()
    if "billing_admin_settings" in tables_after:
        r = conn.execute(sa.text("SELECT COUNT(*) FROM billing_admin_settings")).scalar()
        if r == 0:
            op.execute(
                sa.text(
                    "INSERT INTO billing_admin_settings (id, payment_card_enabled, payment_upi_enabled, "
                    "default_trial_days, grace_period_days, renewal_reminder_days_before, "
                    "dunning_retry_interval_hours, updated_at) VALUES "
                    "(1, true, true, 0, 3, 7, 24, CURRENT_TIMESTAMP)"
                )
            )

    if "subscription_plans" in tables_after:
        r = conn.execute(sa.text("SELECT COUNT(*) FROM subscription_plans")).scalar()
        if r == 0:
            op.execute(
                sa.text(
                    "INSERT INTO subscription_plans (slug, name, description, plan_tier, billing_interval, "
                    "base_amount_paise, currency, features_json, razorpay_plan_id, is_active, created_at, updated_at) "
                    "VALUES "
                    "('paper-basic', 'Paper Trade (Basic)', 'Stock recommendations and paper trading', "
                    "'paper_basic', 'month', 0, 'INR', "
                    '\'{"stock_recommendations": true, "broker_execution": false, "auto_trade_services": false, "paper_trading": true}\', '
                    "NULL, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP), "
                    "('auto-advanced', 'Auto Trade (Advanced)', 'Auto trade with configured broker', "
                    "'auto_advanced', 'month', 0, 'INR', "
                    '\'{"stock_recommendations": true, "broker_execution": true, "auto_trade_services": true, "paper_trading": true}\', '
                    "NULL, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )

    # Notification preference columns
    prefs_table = "user_notification_preferences"
    inspector = inspect(conn)
    if prefs_table in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns(prefs_table)}
        if "notify_subscription_renewal_reminder" not in cols:
            op.add_column(
                prefs_table,
                sa.Column(
                    "notify_subscription_renewal_reminder",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("true"),
                ),
            )
        if "notify_payment_failed" not in cols:
            op.add_column(
                prefs_table,
                sa.Column(
                    "notify_payment_failed",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("true"),
                ),
            )
        if "notify_subscription_activated" not in cols:
            op.add_column(
                prefs_table,
                sa.Column(
                    "notify_subscription_activated",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("true"),
                ),
            )
        if "notify_subscription_cancelled" not in cols:
            op.add_column(
                prefs_table,
                sa.Column(
                    "notify_subscription_cancelled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("true"),
                ),
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    prefs_table = "user_notification_preferences"
    if prefs_table in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns(prefs_table)}
        if "notify_subscription_cancelled" in cols:
            op.drop_column(prefs_table, "notify_subscription_cancelled")
        if "notify_subscription_activated" in cols:
            op.drop_column(prefs_table, "notify_subscription_activated")
        if "notify_payment_failed" in cols:
            op.drop_column(prefs_table, "notify_payment_failed")
        if "notify_subscription_renewal_reminder" in cols:
            op.drop_column(prefs_table, "notify_subscription_renewal_reminder")

    for t in (
        "razorpay_webhook_events",
        "free_trial_usage",
        "billing_refunds",
        "billing_transactions",
        "coupon_redemptions",
        "user_billing_profiles",
        "user_subscriptions",
        "coupons",
        "plan_price_schedules",
        "billing_admin_settings",
        "subscription_plans",
    ):
        if t in inspector.get_table_names():
            op.drop_table(t)
