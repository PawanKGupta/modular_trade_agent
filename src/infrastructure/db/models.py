from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .timezone_utils import ist_now


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


class Users(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.USER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, onupdate=ist_now, nullable=False
    )

    settings: Mapped[UserSettings] = relationship(
        "UserSettings", back_populates="user", uselist=False
    )


class TradeMode(str, Enum):
    PAPER = "paper"
    BROKER = "broker"


class UserSettings(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    trade_mode: Mapped[TradeMode] = mapped_column(
        SAEnum(TradeMode), default=TradeMode.PAPER, nullable=False
    )
    broker: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 'kotak-neo' or None
    broker_status: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # Connected/Disconnected/Error
    # Store encrypted credentials blob server-side; do not expose to client
    broker_creds_encrypted: Mapped[bytes | None] = mapped_column(nullable=True)
    # UI preferences (e.g., column selections, view preferences)
    ui_preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, onupdate=ist_now, nullable=False
    )

    user: Mapped[Users] = relationship("Users", back_populates="settings")


class OrderStatus(str, Enum):
    AMO = "amo"
    ONGOING = "ongoing"
    SELL = "sell"
    CLOSED = "closed"


class Orders(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # 'buy'|'sell'
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)  # 'market'|'limit'
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)  # limit price
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus, values_callable=lambda x: [e.value for e in x]),
        index=True,
        nullable=False,
        default=OrderStatus.AMO,
    )
    avg_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    placed_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, index=True, nullable=False
    )
    filled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    orig_source: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # 'signal'|'manual' etc.
    # Broker-specific fields
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # Internal order ID
    broker_order_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # Broker's order ID
    # Metadata JSON field for additional trade information
    order_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True
    )  # Store placed_symbol, signal_type, exit_note, etc.

    __table_args__ = (
        Index("ix_orders_user_status_symbol_time", "user_id", "status", "symbol", "placed_at"),
    )


class Positions(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    avg_price: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, index=True, nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "symbol", name="uq_positions_user_symbol"),)


class Fills(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True, nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime, default=ist_now, index=True, nullable=False)


class PnlDaily(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fees: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_pnl_daily_user_date"),)


class Signals(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # Technical indicators
    rsi10: Mapped[float | None] = mapped_column(Float, nullable=True)
    ema9: Mapped[float | None] = mapped_column(Float, nullable=True)
    ema200: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_to_ema9: Mapped[float | None] = mapped_column(Float, nullable=True)
    clean_chart: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    monthly_support_dist: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Scoring fields
    backtest_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    combined_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    strength_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # ML fields
    ml_verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ml_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ml_probabilities: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Trading parameters
    buy_range: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {low, high}
    target: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Fundamental data
    pe: Mapped[float | None] = mapped_column(Float, nullable=True)
    pb: Mapped[float | None] = mapped_column(Float, nullable=True)
    fundamental_assessment: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fundamental_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Volume data
    avg_vol: Mapped[int | None] = mapped_column(Integer, nullable=True)
    today_vol: Mapped[int | None] = mapped_column(Integer, nullable=True)
    volume_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    volume_pattern: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    volume_description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    vol_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    volume_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Analysis metadata
    verdict: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # buy, avoid, strong_buy, etc.
    signals: Mapped[list | None] = mapped_column(JSON, nullable=True)  # List of signal strings
    justification: Mapped[list | None] = mapped_column(
        JSON, nullable=True
    )  # List of justification strings
    timeframe_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    news_sentiment: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    candle_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    chart_quality: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Timestamp
    ts: Mapped[datetime] = mapped_column(DateTime, default=ist_now, index=True, nullable=False)

    __table_args__ = (Index("ix_signals_symbol_ts", "symbol", "ts"),)


class Activity(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    type: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False
    )  # order_placed, order_filled, error, etc.
    ref_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=ist_now, index=True, nullable=False)


# Phase 1.1: New models for multi-user service architecture


class ServiceStatus(Base):
    """Service status tracking per user"""

    __tablename__ = "service_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True, nullable=False
    )
    service_running: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_task_execution: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, onupdate=ist_now, nullable=False
    )


class ServiceTaskExecution(Base):
    """Task execution history per user"""

    __tablename__ = "service_task_execution"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    task_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), index=True, nullable=False
    )  # 'success', 'failed', 'skipped'
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_service_task_user_name_time", "user_id", "task_name", "executed_at"),
    )


class ServiceLog(Base):
    """Structured service logs (user-scoped)"""

    __tablename__ = "service_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    level: Mapped[str] = mapped_column(
        String(16), index=True, nullable=False
    )  # 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    module: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(String(1024), nullable=False)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, index=True, nullable=False
    )

    __table_args__ = (
        Index("ix_service_logs_user_timestamp_level", "user_id", "timestamp", "level"),
    )


class ErrorLog(Base):
    """Error/exception logs for debugging (user-scoped)"""

    __tablename__ = "error_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    error_type: Mapped[str] = mapped_column(String(128), nullable=False)
    error_message: Mapped[str] = mapped_column(String(1024), nullable=False)
    traceback: Mapped[str | None] = mapped_column(String(8192), nullable=True)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, index=True, nullable=False
    )

    __table_args__ = (
        Index("ix_error_logs_user_occurred_resolved", "user_id", "occurred_at", "resolved"),
    )


class UserTradingConfig(Base):
    """User-specific trading strategy and service configurations"""

    __tablename__ = "user_trading_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True, nullable=False
    )
    # Strategy Parameters
    rsi_period: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    rsi_oversold: Mapped[float] = mapped_column(Float, default=30.0, nullable=False)
    rsi_extreme_oversold: Mapped[float] = mapped_column(Float, default=20.0, nullable=False)
    rsi_near_oversold: Mapped[float] = mapped_column(Float, default=40.0, nullable=False)
    # Capital & Position Management
    user_capital: Mapped[float] = mapped_column(Float, default=200000.0, nullable=False)
    max_portfolio_size: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    max_position_volume_ratio: Mapped[float] = mapped_column(Float, default=0.10, nullable=False)
    min_absolute_avg_volume: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    # Chart Quality Filters
    chart_quality_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    chart_quality_min_score: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    chart_quality_max_gap_frequency: Mapped[float] = mapped_column(
        Float, default=25.0, nullable=False
    )
    chart_quality_min_daily_range_pct: Mapped[float] = mapped_column(
        Float, default=1.0, nullable=False
    )
    chart_quality_max_extreme_candle_frequency: Mapped[float] = mapped_column(
        Float, default=20.0, nullable=False
    )
    # Risk Management (stop loss is optional/future feature)
    default_stop_loss_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    tight_stop_loss_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_stop_loss_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    default_target_pct: Mapped[float] = mapped_column(Float, default=0.10, nullable=False)
    strong_buy_target_pct: Mapped[float] = mapped_column(Float, default=0.12, nullable=False)
    excellent_target_pct: Mapped[float] = mapped_column(Float, default=0.15, nullable=False)
    # Risk-Reward Ratios
    strong_buy_risk_reward: Mapped[float] = mapped_column(Float, default=3.0, nullable=False)
    buy_risk_reward: Mapped[float] = mapped_column(Float, default=2.5, nullable=False)
    excellent_risk_reward: Mapped[float] = mapped_column(Float, default=3.5, nullable=False)
    # Order Defaults
    default_exchange: Mapped[str] = mapped_column(String(8), default="NSE", nullable=False)
    default_product: Mapped[str] = mapped_column(String(8), default="CNC", nullable=False)
    default_order_type: Mapped[str] = mapped_column(String(16), default="MARKET", nullable=False)
    default_variety: Mapped[str] = mapped_column(String(8), default="AMO", nullable=False)
    default_validity: Mapped[str] = mapped_column(String(8), default="DAY", nullable=False)
    # Behavior Toggles
    allow_duplicate_recommendations_same_day: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    exit_on_ema9_or_rsi50: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_combined_score: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    # News Sentiment
    news_sentiment_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    news_sentiment_lookback_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    news_sentiment_min_articles: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    news_sentiment_pos_threshold: Mapped[float] = mapped_column(Float, default=0.25, nullable=False)
    news_sentiment_neg_threshold: Mapped[float] = mapped_column(
        Float, default=-0.25, nullable=False
    )
    # ML Configuration
    ml_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ml_model_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ml_confidence_threshold: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    ml_combine_with_rules: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Scheduling Preferences (JSON field for flexibility)
    task_schedule: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, onupdate=ist_now, nullable=False
    )


class MLTrainingJob(Base):
    """ML training job tracking (admin-only)"""

    __tablename__ = "ml_training_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), index=True, nullable=False
    )  # 'pending', 'running', 'completed', 'failed'
    model_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # 'verdict_classifier', 'price_regressor'
    algorithm: Mapped[str] = mapped_column(String(32), nullable=False)  # 'random_forest', 'xgboost'
    training_data_path: Mapped[str] = mapped_column(String(512), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    model_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    logs: Mapped[str | None] = mapped_column(String(16384), nullable=True)


class MLModel(Base):
    """ML model versioning (admin-only)"""

    __tablename__ = "ml_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    version: Mapped[str] = mapped_column(
        String(16), index=True, nullable=False
    )  # 'v1.0', 'v1.1', etc.
    model_path: Mapped[str] = mapped_column(String(512), nullable=False)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    training_job_id: Mapped[int] = mapped_column(ForeignKey("ml_training_jobs.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (UniqueConstraint("model_type", "version", name="uq_ml_models_type_version"),)


class UserNotificationPreferences(Base):
    """User notification preferences"""

    __tablename__ = "user_notification_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True, nullable=False
    )
    # Notification channels
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Notification types
    notify_service_events: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_trading_events: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_system_events: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_errors: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Quiet hours (optional)
    quiet_hours_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    quiet_hours_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, onupdate=ist_now, nullable=False
    )


class Notification(Base):
    """Notification history"""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    type: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )  # 'service', 'trading', 'system', 'error'
    level: Mapped[str] = mapped_column(
        String(16), index=True, nullable=False
    )  # 'info', 'warning', 'error', 'critical'
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(String(1024), nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, index=True, nullable=False
    )
    # Delivery status
    telegram_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    in_app_delivered: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (Index("ix_notifications_user_read_created", "user_id", "read", "created_at"),)


class AuditLog(Base):
    """Audit trail for all actions"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    action: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )  # 'create', 'update', 'delete', 'login', etc.
    resource_type: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False
    )  # 'order', 'config', 'user', etc.
    resource_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    changes: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # What changed (before/after)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 max length
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, index=True, nullable=False
    )

    __table_args__ = (
        Index("ix_audit_logs_user_timestamp_type", "user_id", "timestamp", "resource_type"),
    )


class ServiceSchedule(Base):
    """Service schedule configuration (admin-editable, applies to all users)"""

    __tablename__ = "service_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_name: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )  # premarket_retry, sell_monitor, position_monitor, analysis, buy_orders, eod_cleanup
    schedule_time: Mapped[time] = mapped_column(Time, nullable=False)  # HH:MM in IST
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_hourly: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )  # For position_monitor (runs hourly at :30)
    is_continuous: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )  # For sell_monitor (runs continuously)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)  # For continuous tasks
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )  # Admin who last updated
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, onupdate=ist_now, nullable=False
    )

    __table_args__ = (UniqueConstraint("task_name", name="uq_service_schedule_task_name"),)


class IndividualServiceStatus(Base):
    """Individual service status tracking per user"""

    __tablename__ = "individual_service_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    task_name: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False
    )  # premarket_retry, sell_monitor, position_monitor, buy_orders, eod_cleanup
    is_running: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_execution_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_execution_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    process_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # OS process ID
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, onupdate=ist_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "task_name", name="uq_individual_service_user_task"),
        Index("ix_individual_service_user_task", "user_id", "task_name"),
    )


class IndividualServiceTaskExecution(Base):
    """Individual service task execution history per user"""

    __tablename__ = "individual_service_task_execution"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    task_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), index=True, nullable=False
    )  # 'success', 'failed', 'skipped', 'running'
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    execution_type: Mapped[str] = mapped_column(
        String(16), default="scheduled", nullable=False
    )  # 'scheduled', 'run_once', 'manual'

    __table_args__ = (
        Index(
            "ix_individual_service_task_user_name_time",
            "user_id",
            "task_name",
            "executed_at",
        ),
    )
