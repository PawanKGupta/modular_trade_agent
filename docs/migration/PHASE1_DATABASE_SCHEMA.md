# Phase 1.1: Database Schema Documentation

**Last Updated**: January 2025
**Status**: ✅ Complete
**Migration**: `0002_phase1`

---

## Overview

This document describes the database schema extensions added in Phase 1.1 of the multi-user migration. These tables support:

- Service status tracking per user
- Task execution history
- Structured logging and error tracking
- User-specific trading configurations
- ML training job management
- Notification preferences and history
- Audit trail

---

## New Tables

### 1. `service_status`

Tracks the running status and health of the trading service for each user.

**Columns**:
- `id` (INTEGER, PRIMARY KEY)
- `user_id` (INTEGER, FOREIGN KEY → `users.id`, UNIQUE, INDEXED)
- `service_running` (BOOLEAN, DEFAULT: false)
- `last_heartbeat` (DATETIME, NULLABLE)
- `last_task_execution` (DATETIME, NULLABLE)
- `error_count` (INTEGER, DEFAULT: 0)
- `last_error` (VARCHAR(512), NULLABLE)
- `created_at` (DATETIME)
- `updated_at` (DATETIME)

**Constraints**:
- One service status record per user (UNIQUE constraint on `user_id`)

**Indexes**:
- `ix_service_status_user_id` (UNIQUE)

**Usage**:
- Track whether a user's trading service is running
- Monitor service health (heartbeat, errors)
- Record last task execution time

---

### 2. `service_task_execution`

Records the execution history of scheduled tasks per user.

**Columns**:
- `id` (INTEGER, PRIMARY KEY)
- `user_id` (INTEGER, FOREIGN KEY → `users.id`, INDEXED)
- `task_name` (VARCHAR(64), INDEXED) - e.g., 'premarket_retry', 'sell_monitor'
- `executed_at` (DATETIME, INDEXED)
- `status` (VARCHAR(16), INDEXED) - 'success', 'failed', 'skipped'
- `duration_seconds` (FLOAT)
- `details` (JSON, NULLABLE) - Task-specific data

**Constraints**:
- None (multiple executions per user/task allowed)

**Indexes**:
- `ix_service_task_execution_user_id`
- `ix_service_task_execution_task_name`
- `ix_service_task_execution_status`
- `ix_service_task_user_name_time` (COMPOSITE: user_id, task_name, executed_at)

**Usage**:
- Track task execution history
- Monitor task performance (duration)
- Debug task failures
- Query recent task executions

---

### 3. `service_logs`

Structured service logs, scoped per user.

**Columns**:
- `id` (INTEGER, PRIMARY KEY)
- `user_id` (INTEGER, FOREIGN KEY → `users.id`, INDEXED)
- `level` (VARCHAR(16), INDEXED) - 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
- `module` (VARCHAR(128)) - Module/component name
- `message` (VARCHAR(1024)) - Log message
- `context` (JSON, NULLABLE) - Additional context (symbol, order_id, etc.)
- `timestamp` (DATETIME, INDEXED)

**Constraints**:
- None (multiple logs per user allowed)

**Indexes**:
- `ix_service_logs_user_id`
- `ix_service_logs_level`
- `ix_service_logs_timestamp`
- `ix_service_logs_user_timestamp_level` (COMPOSITE: user_id, timestamp, level)

**Usage**:
- Structured logging for service operations
- User-scoped log queries
- Filter by level, date range, user
- Search logs by message/keyword

**Retention Policy**:
- Database: Last 30 days
- Files: Last 90 days (per-user log files)

---

### 4. `error_logs`

Error and exception logs for debugging, scoped per user.

**Columns**:
- `id` (INTEGER, PRIMARY KEY)
- `user_id` (INTEGER, FOREIGN KEY → `users.id`, INDEXED)
- `error_type` (VARCHAR(128)) - Exception class name
- `error_message` (VARCHAR(1024)) - Exception message
- `traceback` (VARCHAR(8192), NULLABLE) - Full traceback
- `context` (JSON, NULLABLE) - Request context, user config, etc.
- `resolved` (BOOLEAN, DEFAULT: false, INDEXED)
- `resolved_at` (DATETIME, NULLABLE)
- `resolved_by` (INTEGER, FOREIGN KEY → `users.id`, NULLABLE) - Admin user ID
- `resolution_notes` (VARCHAR(512), NULLABLE)
- `occurred_at` (DATETIME, INDEXED)

**Constraints**:
- None (multiple errors per user allowed)

**Indexes**:
- `ix_error_logs_user_id`
- `ix_error_logs_occurred_at`
- `ix_error_logs_resolved`
- `ix_error_logs_user_occurred_resolved` (COMPOSITE: user_id, occurred_at, resolved)

**Usage**:
- Capture exceptions with full context
- Track error resolution workflow
- Admin error management
- Debug user-specific issues

**Retention Policy**:
- All unresolved errors (kept indefinitely)
- Resolved errors: 90 days

---

### 5. `user_trading_config`

User-specific trading strategy and service configurations.

**Columns**:

**Strategy Parameters**:
- `rsi_period` (INTEGER, DEFAULT: 10)
- `rsi_oversold` (FLOAT, DEFAULT: 30.0)
- `rsi_extreme_oversold` (FLOAT, DEFAULT: 20.0)
- `rsi_near_oversold` (FLOAT, DEFAULT: 40.0)

**Capital & Position Management**:
- `user_capital` (FLOAT, DEFAULT: 200000.0) - Capital per trade
- `max_portfolio_size` (INTEGER, DEFAULT: 6) - Max positions
- `max_position_volume_ratio` (FLOAT, DEFAULT: 0.10) - 10% of daily volume
- `min_absolute_avg_volume` (INTEGER, DEFAULT: 10000)

**Chart Quality Filters**:
- `chart_quality_enabled` (BOOLEAN, DEFAULT: true)
- `chart_quality_min_score` (FLOAT, DEFAULT: 50.0)
- `chart_quality_max_gap_frequency` (FLOAT, DEFAULT: 25.0)
- `chart_quality_min_daily_range_pct` (FLOAT, DEFAULT: 1.0)
- `chart_quality_max_extreme_candle_frequency` (FLOAT, DEFAULT: 20.0)

**Risk Management** (Optional - Future Feature):
- `default_stop_loss_pct` (FLOAT, NULLABLE) - Optional, 8% if enabled
- `tight_stop_loss_pct` (FLOAT, NULLABLE) - Optional, 6% if enabled
- `min_stop_loss_pct` (FLOAT, NULLABLE) - Optional, 3% if enabled
- `default_target_pct` (FLOAT, DEFAULT: 0.10) - 10%
- `strong_buy_target_pct` (FLOAT, DEFAULT: 0.12) - 12%
- `excellent_target_pct` (FLOAT, DEFAULT: 0.15) - 15%

**Risk-Reward Ratios**:
- `strong_buy_risk_reward` (FLOAT, DEFAULT: 3.0)
- `buy_risk_reward` (FLOAT, DEFAULT: 2.5)
- `excellent_risk_reward` (FLOAT, DEFAULT: 3.5)

**Order Defaults**:
- `default_exchange` (VARCHAR(8), DEFAULT: 'NSE')
- `default_product` (VARCHAR(8), DEFAULT: 'CNC')
- `default_order_type` (VARCHAR(16), DEFAULT: 'MARKET')
- `default_variety` (VARCHAR(8), DEFAULT: 'AMO')
- `default_validity` (VARCHAR(8), DEFAULT: 'DAY')

**Behavior Toggles**:
- `allow_duplicate_recommendations_same_day` (BOOLEAN, DEFAULT: false)
- `exit_on_ema9_or_rsi50` (BOOLEAN, DEFAULT: true)
- `min_combined_score` (INTEGER, DEFAULT: 25)

**News Sentiment**:
- `news_sentiment_enabled` (BOOLEAN, DEFAULT: true)
- `news_sentiment_lookback_days` (INTEGER, DEFAULT: 30)
- `news_sentiment_min_articles` (INTEGER, DEFAULT: 2)
- `news_sentiment_pos_threshold` (FLOAT, DEFAULT: 0.25)
- `news_sentiment_neg_threshold` (FLOAT, DEFAULT: -0.25)

**ML Configuration**:
- `ml_enabled` (BOOLEAN, DEFAULT: false)
- `ml_model_version` (VARCHAR(16), NULLABLE) - 'v1.0', 'v1.1', or None for active
- `ml_confidence_threshold` (FLOAT, DEFAULT: 0.5)
- `ml_combine_with_rules` (BOOLEAN, DEFAULT: true)

**Scheduling Preferences**:
- `task_schedule` (JSON, NULLABLE) - Custom task timing per user

**Timestamps**:
- `id` (INTEGER, PRIMARY KEY)
- `user_id` (INTEGER, FOREIGN KEY → `users.id`, UNIQUE, INDEXED)
- `created_at` (DATETIME)
- `updated_at` (DATETIME)

**Constraints**:
- One trading config per user (UNIQUE constraint on `user_id`)

**Indexes**:
- `ix_user_trading_config_user_id` (UNIQUE)

**Usage**:
- Store user-specific trading strategy parameters
- Configure risk management settings
- Enable/disable features (ML, news sentiment, chart quality)
- Customize order defaults
- Custom task scheduling

**Note**: Stop loss fields are optional (NULLABLE) as they are not currently implemented. They can be enabled in the future without breaking existing functionality.

---

### 6. `ml_training_jobs`

ML training job tracking (admin-only).

**Columns**:
- `id` (INTEGER, PRIMARY KEY)
- `started_by` (INTEGER, FOREIGN KEY → `users.id`, INDEXED) - Admin user ID
- `status` (VARCHAR(16), INDEXED) - 'pending', 'running', 'completed', 'failed'
- `model_type` (VARCHAR(64)) - 'verdict_classifier', 'price_regressor'
- `algorithm` (VARCHAR(32)) - 'random_forest', 'xgboost'
- `training_data_path` (VARCHAR(512))
- `started_at` (DATETIME)
- `completed_at` (DATETIME, NULLABLE)
- `model_path` (VARCHAR(512), NULLABLE) - Path to trained model
- `accuracy` (FLOAT, NULLABLE)
- `error_message` (VARCHAR(1024), NULLABLE)
- `logs` (VARCHAR(16384), NULLABLE) - Training logs

**Constraints**:
- None (multiple jobs allowed)

**Indexes**:
- `ix_ml_training_jobs_started_by`
- `ix_ml_training_jobs_status`

**Usage**:
- Track ML training job execution
- Monitor training progress
- Store training results (accuracy, model path)
- Debug training failures

**Access**: Admin-only

---

### 7. `ml_models`

ML model versioning (admin-only).

**Columns**:
- `id` (INTEGER, PRIMARY KEY)
- `model_type` (VARCHAR(64), INDEXED) - 'verdict_classifier', 'price_regressor'
- `version` (VARCHAR(16), INDEXED) - 'v1.0', 'v1.1', etc.
- `model_path` (VARCHAR(512)) - Path to model file
- `accuracy` (FLOAT, NULLABLE)
- `training_job_id` (INTEGER, FOREIGN KEY → `ml_training_jobs.id`)
- `is_active` (BOOLEAN, DEFAULT: false, INDEXED) - Only one active model per type
- `created_at` (DATETIME)
- `created_by` (INTEGER, FOREIGN KEY → `users.id`) - Admin user ID

**Constraints**:
- Unique combination of `model_type` and `version` (UNIQUE constraint)

**Indexes**:
- `ix_ml_models_model_type`
- `ix_ml_models_version`
- `ix_ml_models_is_active`
- `uq_ml_models_type_version` (UNIQUE: model_type, version)

**Usage**:
- Version control for ML models
- Track model accuracy
- Activate/deactivate model versions
- Link models to training jobs

**Access**: Admin-only

**Note**: Only one active model per `model_type` at a time.

---

### 8. `user_notification_preferences`

User notification preferences.

**Columns**:

**Notification Channels**:
- `id` (INTEGER, PRIMARY KEY)
- `user_id` (INTEGER, FOREIGN KEY → `users.id`, UNIQUE, INDEXED)
- `telegram_enabled` (BOOLEAN, DEFAULT: false)
- `telegram_chat_id` (VARCHAR(64), NULLABLE)
- `email_enabled` (BOOLEAN, DEFAULT: false)
- `email_address` (VARCHAR(255), NULLABLE)
- `in_app_enabled` (BOOLEAN, DEFAULT: true) - Always enabled

**Notification Types**:
- `notify_service_events` (BOOLEAN, DEFAULT: true)
- `notify_trading_events` (BOOLEAN, DEFAULT: true)
- `notify_system_events` (BOOLEAN, DEFAULT: true)
- `notify_errors` (BOOLEAN, DEFAULT: true)

**Quiet Hours** (Optional):
- `quiet_hours_start` (TIME, NULLABLE)
- `quiet_hours_end` (TIME, NULLABLE)

**Timestamps**:
- `created_at` (DATETIME)
- `updated_at` (DATETIME)

**Constraints**:
- One notification preferences record per user (UNIQUE constraint on `user_id`)

**Indexes**:
- `ix_user_notification_preferences_user_id` (UNIQUE)

**Usage**:
- Configure notification channels (Telegram, Email, In-app)
- Enable/disable notification types
- Set quiet hours (optional)

---

### 9. `notifications`

Notification history.

**Columns**:
- `id` (INTEGER, PRIMARY KEY)
- `user_id` (INTEGER, FOREIGN KEY → `users.id`, INDEXED)
- `type` (VARCHAR(32), INDEXED) - 'service', 'trading', 'system', 'error'
- `level` (VARCHAR(16), INDEXED) - 'info', 'warning', 'error', 'critical'
- `title` (VARCHAR(255))
- `message` (VARCHAR(1024))
- `read` (BOOLEAN, DEFAULT: false, INDEXED)
- `read_at` (DATETIME, NULLABLE)
- `created_at` (DATETIME, INDEXED)
- `telegram_sent` (BOOLEAN, DEFAULT: false)
- `email_sent` (BOOLEAN, DEFAULT: false)
- `in_app_delivered` (BOOLEAN, DEFAULT: true)

**Constraints**:
- None (multiple notifications per user allowed)

**Indexes**:
- `ix_notifications_user_id`
- `ix_notifications_type`
- `ix_notifications_level`
- `ix_notifications_read`
- `ix_notifications_created_at`
- `ix_notifications_user_read_created` (COMPOSITE: user_id, read, created_at)

**Usage**:
- Store notification history
- Track read/unread status
- Track delivery status across channels
- Query unread notifications

**Notification Types**:
- `service`: Service events (start/stop, errors)
- `trading`: Trading events (orders, positions)
- `system`: System events (broker issues, API limits)
- `error`: Error notifications (critical errors)

---

### 10. `audit_logs`

Audit trail for all actions.

**Columns**:
- `id` (INTEGER, PRIMARY KEY)
- `user_id` (INTEGER, FOREIGN KEY → `users.id`, INDEXED) - Who performed the action
- `action` (VARCHAR(32), INDEXED) - 'create', 'update', 'delete', 'login', 'logout', etc.
- `resource_type` (VARCHAR(64), INDEXED) - 'order', 'config', 'user', 'service', etc.
- `resource_id` (INTEGER, NULLABLE) - ID of affected resource
- `changes` (JSON, NULLABLE) - What changed (before/after)
- `ip_address` (VARCHAR(45), NULLABLE) - IPv6 max length
- `user_agent` (VARCHAR(512), NULLABLE)
- `timestamp` (DATETIME, INDEXED)

**Constraints**:
- None (multiple audit logs allowed)

**Indexes**:
- `ix_audit_logs_user_id`
- `ix_audit_logs_action`
- `ix_audit_logs_resource_type`
- `ix_audit_logs_timestamp`
- `ix_audit_logs_user_timestamp_type` (COMPOSITE: user_id, timestamp, resource_type)

**Usage**:
- Track all user actions
- Track configuration changes
- Track service events
- Compliance and security auditing
- Debug user issues

**Access**: Admin-only (view all), Users (view own)

---

## Modified Tables

### `orders`

**New Columns**:
- `order_id` (VARCHAR(64), NULLABLE) - Internal order ID
- `broker_order_id` (VARCHAR(64), NULLABLE) - Broker's order ID

**Usage**:
- Link orders to broker-specific order IDs
- Track internal vs broker order IDs

---

### `activity`

**New Constraints**:
- Foreign key constraint on `user_id` → `users.id` (ON DELETE SET NULL)
- Index on `user_id`

**Usage**:
- Proper referential integrity
- Improved query performance

---

## Indexes Summary

All new tables include appropriate indexes for:
- **User isolation**: Indexes on `user_id` for efficient user-scoped queries
- **Query performance**: Composite indexes for common query patterns
- **Time-based queries**: Indexes on timestamp fields
- **Status filtering**: Indexes on status/enum fields

---

## Foreign Key Relationships

```
users (1) ──< (N) service_status
users (1) ──< (N) service_task_execution
users (1) ──< (N) service_logs
users (1) ──< (N) error_logs
users (1) ──< (1) user_trading_config
users (1) ──< (N) ml_training_jobs
users (1) ──< (N) ml_models (created_by)
users (1) ──< (N) error_logs (resolved_by)
users (1) ──< (1) user_notification_preferences
users (1) ──< (N) notifications
users (1) ──< (N) audit_logs

ml_training_jobs (1) ──< (N) ml_models
```

---

## Data Isolation

All tables are **user-scoped**:
- Foreign keys to `users.id` ensure data isolation
- Indexes on `user_id` enable efficient user-scoped queries
- Unique constraints on `user_id` for one-to-one relationships

**Query Pattern**:
```sql
SELECT * FROM service_logs WHERE user_id = ? AND timestamp > ?;
```

---

## Migration

**Migration File**: `alembic/versions/0002_phase1_multi_user_schema.py`

**Revision ID**: `0002_phase1`
**Revises**: `0001_initial`
**Create Date**: 2025-01-15

**To Apply**:
```bash
alembic upgrade 0002_phase1
```

**To Rollback**:
```bash
alembic downgrade 0001_initial
```

---

## Testing

Unit tests are available in:
- `tests/unit/infrastructure/test_phase1_models.py`

**Coverage**: >80% for all new models

**Test Coverage**:
- ✅ Model creation and defaults
- ✅ Unique constraints
- ✅ Foreign key relationships
- ✅ Optional fields (NULLABLE)
- ✅ JSON fields
- ✅ Enum/status fields
- ✅ Timestamp fields
- ✅ Index validation

---

## Next Steps

1. ✅ **Phase 1.1 Complete**: Database schema, migration, tests, documentation
2. ✅ **Phase 1.2 Complete**: Data migration scripts (file → database)
3. ✅ **Phase 1.3 Complete**: Repository layer updates
4. ✅ **Phase 1.4 Complete**: User configuration management

**Phase 1 Status**: ✅ **COMPLETE** - See [Phase 1 Completion Report](./PHASE1_COMPLETION_REPORT.md) for details.

---

## References

- [Migration Plan](../migration/UNIFIED_SERVICE_TO_MULTIUSER_MIGRATION_PLAN.md)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
