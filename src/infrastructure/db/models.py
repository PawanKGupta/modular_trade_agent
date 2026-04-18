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
from .case_insensitive_enum import CaseInsensitiveEnum
from .timezone_utils import ist_now, ist_now_naive


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


class ScheduleType(str, Enum):
    """Schedule type for service execution"""

    DAILY = "daily"  # Runs every day at scheduled time
    ONCE = "once"  # Runs once at scheduled time and stops


class SignalStatus(str, Enum):
    """Status of a signal in the buying zone"""

    ACTIVE = "active"  # Fresh signal, can be traded
    EXPIRED = "expired"  # Expired (past next analysis run)
    TRADED = "traded"  # Order placed for this signal
    REJECTED = "rejected"  # User manually rejected this signal
    FAILED = "failed"  # Order placed but failed/rejected/cancelled - no position created


class Users(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, values_callable=lambda x: [e.value for e in x]),
        default=UserRole.USER,
        nullable=False,
    )
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
        SAEnum(TradeMode, values_callable=lambda x: [e.value for e in x]),
        default=TradeMode.PAPER,
        nullable=False,
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
    PENDING = "pending"  # Merged: AMO + PENDING_EXECUTION
    ONGOING = "ongoing"
    CLOSED = "closed"
    FAILED = "failed"  # Merged: FAILED + RETRY_PENDING + REJECTED
    CANCELLED = "cancelled"
    # Note: SELL removed - use side='sell' column to identify sell orders


class Orders(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    base_symbol: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # 'buy'|'sell'
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)  # 'market'|'limit'
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)  # limit price
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus, values_callable=lambda x: [e.value for e in x]),
        index=True,
        nullable=False,
        default=OrderStatus.PENDING,  # Changed from AMO
    )
    avg_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    placed_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, index=True, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, onupdate=ist_now, nullable=False
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
    # Failure and retry tracking fields
    # Unified reason field (replaces failure_reason, rejection_reason, cancelled_reason)
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )  # Detailed broker rejection reason (Phase 1)
    first_failed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_retry_attempt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_status_check: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Execution tracking fields
    execution_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    execution_qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    execution_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Reentry tracking
    entry_type: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # 'initial', 'reentry', 'manual'
    # Phase 0.1: Trade mode (paper vs broker)
    trade_mode: Mapped[TradeMode | None] = mapped_column(
        SAEnum(TradeMode, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
        index=True,
    )  # 'paper' | 'broker' | NULL for legacy orders

    __table_args__ = (
        Index("ix_orders_user_status_symbol_time", "user_id", "status", "symbol", "placed_at"),
        Index("ix_orders_status_last_check", "status", "last_status_check"),
        Index("ix_orders_updated_at", "updated_at"),
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
    # Reentry tracking
    reentry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reentries: Mapped[dict | None] = mapped_column(
        "reentries", JSON, nullable=True
    )  # Array of reentry details
    initial_entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_reentry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Entry RSI tracking (for re-entry level progression)
    entry_rsi: Mapped[float | None] = mapped_column(Float, nullable=True)  # RSI10 at entry
    # Phase 0.2: Exit details (all nullable for backward compatibility)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )  # 'EMA9_TARGET', 'RSI_EXIT', 'MANUAL', etc.
    exit_rsi: Mapped[float | None] = mapped_column(Float, nullable=True)  # RSI10 at exit
    realized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)

    __table_args__ = ()


class Fills(Base):
    """
    Order fills/executions table - tracks partial fills for orders (Phase 1)

    When an order executes in multiple parts, each fill is recorded separately.
    The order's executed_qty and execution_price are aggregated from fills.
    """

    __tablename__ = "fills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"), index=True, nullable=False
    )  # Parent order
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )  # Denormalized for queries

    # Fill details
    quantity: Mapped[float] = mapped_column(Float, nullable=False)  # Qty filled in this execution
    price: Mapped[float] = mapped_column(Float, nullable=False)  # Price of this fill
    fill_value: Mapped[float] = mapped_column(Float, nullable=False)  # quantity * price
    charges: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # Brokerage + taxes

    # Timestamps
    filled_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, index=True, nullable=False
    )  # Fill timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, nullable=False
    )  # Record creation

    # Broker details
    broker_fill_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
    )  # Broker's fill ID (for deduplication)

    __table_args__ = (
        Index("ix_fills_order_filled_at", "order_id", "filled_at"),
        Index("ix_fills_user_filled_at", "user_id", "filled_at"),
    )


class PortfolioSnapshot(Base):
    """Daily portfolio value snapshots for historical tracking (Phase 0.3)"""

    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)

    # Portfolio metrics
    total_value: Mapped[float] = mapped_column(Float, nullable=False)  # Total portfolio value
    invested_value: Mapped[float] = mapped_column(Float, nullable=False)  # Capital invested
    available_cash: Mapped[float] = mapped_column(Float, nullable=False)  # Available cash
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Position counts
    open_positions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    closed_positions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Return metrics
    total_return: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )  # Total return %
    daily_return: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )  # Daily return %

    # Metadata
    snapshot_type: Mapped[str] = mapped_column(
        String(16), default="eod", nullable=False
    )  # 'eod', 'intraday'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "user_id", "date", "snapshot_type", name="uq_portfolio_snapshot_user_date_type"
        ),
        Index("ix_portfolio_snapshot_user_date", "user_id", "date"),
    )


class Targets(Base):
    """Sell order targets for positions (Phase 0.4)"""

    __tablename__ = "targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    position_id: Mapped[int | None] = mapped_column(
        ForeignKey("positions.id"), nullable=True
    )  # Link to position
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)

    # Target information
    target_price: Mapped[float] = mapped_column(Float, nullable=False)  # EMA9 target
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)  # Average entry price
    current_price: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # Current market price
    quantity: Mapped[float] = mapped_column(Float, nullable=False)  # Position quantity

    # Distance metrics
    distance_to_target: Mapped[float | None] = mapped_column(Float, nullable=True)  # % distance
    distance_to_target_absolute: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # Absolute distance

    # Target metadata
    target_type: Mapped[str] = mapped_column(
        String(32), default="ema9", nullable=False
    )  # 'ema9', 'manual', etc.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # Active target
    trade_mode: Mapped[TradeMode] = mapped_column(
        SAEnum(TradeMode, values_callable=lambda x: [e.value for e in x]), nullable=False
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, onupdate=ist_now, nullable=False
    )
    achieved_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )  # When target was hit

    __table_args__ = (
        Index("ix_targets_user_symbol_active", "user_id", "symbol", "is_active"),
        Index("ix_targets_position", "position_id"),
    )


class PnlDaily(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fees: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_pnl_daily_user_date"),)


class PnlCalculationAudit(Base):
    """Audit trail for P&L calculations (Phase 0.5)"""

    __tablename__ = "pnl_calculation_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)

    # Calculation metadata
    calculation_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # 'on_demand', 'scheduled', 'backfill'
    date_range_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_range_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Results
    positions_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    orders_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pnl_records_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pnl_records_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Performance
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)

    # Status
    status: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # 'success', 'failed', 'partial'
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Metadata
    triggered_by: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # 'user', 'system', 'scheduled'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)

    __table_args__ = (Index("ix_pnl_audit_user_created", "user_id", "created_at"),)


class PriceCache(Base):
    """Historical price cache for symbols (Phase 0.6)"""

    __tablename__ = "price_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)

    # Price data
    open: Mapped[float | None] = mapped_column(Float, nullable=True)
    high: Mapped[float | None] = mapped_column(Float, nullable=True)
    low: Mapped[float | None] = mapped_column(Float, nullable=True)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Metadata
    source: Mapped[str] = mapped_column(
        String(32), default="yfinance", nullable=False
    )  # 'yfinance', 'broker', 'manual'
    cached_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("symbol", "date", name="uq_price_cache_symbol_date"),
        Index("ix_price_cache_symbol_date", "symbol", "date"),
    )


class ExportJob(Base):
    """Export job tracking (Phase 0.7)"""

    __tablename__ = "export_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)

    # Export metadata
    export_type: Mapped[str] = mapped_column(String(32), nullable=False)  # 'csv', 'pdf', 'json'
    data_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # 'pnl', 'trades', 'signals', 'positions', etc.
    date_range_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_range_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # 'pending', 'processing', 'completed', 'failed'
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0-100

    # Results
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)  # bytes
    records_exported: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Performance
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_export_jobs_user_status_created", "user_id", "status", "created_at"),
    )


class AnalyticsCache(Base):
    """Cached analytics calculations (Phase 0.8)"""

    __tablename__ = "analytics_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)

    # Cache key
    cache_key: Mapped[str] = mapped_column(
        String(128), index=True, nullable=False
    )  # e.g., 'win_rate_2024', 'sharpe_ratio_ytd'
    analytics_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # 'win_rate', 'sharpe_ratio', 'drawdown', etc.
    date_range_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_range_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Cached data
    cached_data: Mapped[dict] = mapped_column(JSON, nullable=False)  # Store calculated metrics

    # Cache metadata
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # TTL
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "cache_key", name="uq_analytics_cache_user_key"),
        Index("ix_analytics_cache_user_type", "user_id", "analytics_type"),
    )


class Signals(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    status: Mapped[SignalStatus] = mapped_column(
        CaseInsensitiveEnum(SignalStatus),
        default=SignalStatus.ACTIVE,
        index=True,
        nullable=False,
    )
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
    # Additional analysis fields
    final_verdict: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # Verdict after backtest reclassification
    rule_verdict: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # Rule-based verdict
    verdict_source: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )  # 'ml' or 'rule_based'
    backtest_confidence: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )  # 'Low', 'Medium', 'High'
    vol_strong: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_above_ema200: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Dip buying features
    dip_depth_from_20d_high_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    consecutive_red_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dip_speed_pct_per_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    decline_rate_slowing: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    volume_green_vs_red_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    support_hold_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Additional metadata
    liquidity_recommendation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trading_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Timestamp
    ts: Mapped[datetime] = mapped_column(DateTime, default=ist_now, index=True, nullable=False)

    __table_args__ = (Index("ix_signals_symbol_ts", "symbol", "ts"),)


class UserSignalStatus(Base):
    """
    Per-user signal status tracking.

    Allows each user to have their own status for signals (TRADED, REJECTED)
    while keeping the base signal data shared across users.
    """

    __tablename__ = "user_signal_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id"), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )  # Denormalized for faster queries
    status: Mapped[SignalStatus] = mapped_column(
        CaseInsensitiveEnum(SignalStatus),
        index=True,
        nullable=False,
    )  # TRADED, REJECTED (per user)
    marked_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "signal_id", name="uq_user_signal_status"),
        Index("ix_user_signal_status_user_symbol", "user_id", "symbol"),
    )


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


class SchedulerLock(Base):
    """
    Table-based lock for scheduler instances.

    Replaces PostgreSQL advisory locks which are problematic with connection pooling.
    This ensures only ONE scheduler instance runs per user across processes/containers.
    """

    __tablename__ = "scheduler_lock"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), primary_key=True, nullable=False
    )
    locked_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    lock_id: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # Unique identifier for this lock instance
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False
    )  # Auto-expire stale locks (e.g., 5 minutes)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)

    __table_args__ = (Index("ix_scheduler_lock_expires_at", "expires_at"),)


class ServiceTaskExecution(Base):
    """Task execution history per user"""

    __tablename__ = "service_task_execution"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    task_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now_naive, index=True, nullable=False
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
    """
    Structured service logs (user-scoped).

    DEPRECATED: Activity logs now use file-based logging (JSONL files).
    This model is kept for backward compatibility with existing data.
    New activity logs are written to files, not this table.
    Error logs continue to use ErrorLog table.
    """

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
    user_capital: Mapped[float] = mapped_column(Float, default=100000.0, nullable=False)
    paper_trading_initial_capital: Mapped[float] = mapped_column(
        Float, default=1000000.0, nullable=False
    )  # Paper trading starting balance (default: Rs 10 Lakh)
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
    # Pre-Market AMO Adjustment
    enable_premarket_amo_adjustment: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )  # Adjust AMO quantities based on pre-market prices to keep capital constant
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
    telegram_bot_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Notification types (legacy - kept for backward compatibility)
    notify_service_events: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_trading_events: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_system_events: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_errors: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Granular order event preferences (Phase 1: Notification Preferences)
    notify_order_placed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_order_rejected: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_order_executed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_order_cancelled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_order_modified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_retry_queue_added: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_retry_queue_updated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_retry_queue_removed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_retry_queue_retried: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_partial_fill: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Granular system event preferences (Phase 1: Notification Preferences)
    notify_system_errors: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_system_warnings: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_system_info: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Granular service event preferences (Service Notifications)
    notify_service_started: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_service_stopped: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_service_execution_completed: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    # Billing / subscription notifications
    notify_subscription_renewal_reminder: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    notify_payment_failed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_subscription_activated: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    notify_subscription_cancelled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
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
    )  # premarket_retry, sell_monitor, analysis, buy_orders, eod_cleanup
    schedule_time: Mapped[time] = mapped_column(Time, nullable=False)  # HH:MM in IST
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_hourly: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )  # For position_monitor (runs hourly at :30)
    is_continuous: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )  # For sell_monitor (runs continuously)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)  # For continuous tasks
    schedule_type: Mapped[str] = mapped_column(
        String(16), default="daily", nullable=False
    )  # "daily" or "once" - daily runs every day, once runs once and stops
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
        DateTime, default=ist_now_naive, index=True, nullable=False
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


# --- Subscription & billing (Razorpay) ---


class PlanTier(str, Enum):
    """Commercial tier mapped to product capabilities."""

    PAPER_BASIC = "paper_basic"  # stock recommendations (+ paper); no live broker automation
    AUTO_ADVANCED = "auto_advanced"  # broker + auto-trade services


class BillingInterval(str, Enum):
    MONTH = "month"
    YEAR = "year"


class PlanPriceScheduleStatus(str, Enum):
    SCHEDULED = "scheduled"
    APPLIED = "applied"
    CANCELLED = "cancelled"


class UserSubscriptionStatus(str, Enum):
    PENDING = "pending"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    GRACE = "grace"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class BillingProvider(str, Enum):
    RAZORPAY = "razorpay"
    MANUAL = "manual"


class CouponDiscountType(str, Enum):
    PERCENT = "percent"
    FIXED = "fixed"


class BillingTransactionStatus(str, Enum):
    CREATED = "created"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"


class SubscriptionPlan(Base):
    """Admin-managed sellable plan (synced to Razorpay plan when configured)."""

    __tablename__ = "subscription_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    plan_tier: Mapped[PlanTier] = mapped_column(
        SAEnum(PlanTier, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    billing_interval: Mapped[BillingInterval] = mapped_column(
        SAEnum(BillingInterval, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    # Default list price in minor units (paise); effective price comes from plan_price_schedules
    base_amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    features_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    razorpay_plan_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, onupdate=ist_now, nullable=False
    )

    price_schedules: Mapped[list[PlanPriceSchedule]] = relationship(
        "PlanPriceSchedule", back_populates="plan", cascade="all, delete-orphan"
    )


class PlanPriceSchedule(Base):
    """Scheduled price change; effective from given instant (IST-naive per project DB convention)."""

    __tablename__ = "plan_price_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("subscription_plans.id"), index=True, nullable=False
    )
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[PlanPriceScheduleStatus] = mapped_column(
        SAEnum(PlanPriceScheduleStatus, values_callable=lambda x: [e.value for e in x]),
        default=PlanPriceScheduleStatus.SCHEDULED,
        nullable=False,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)

    plan: Mapped[SubscriptionPlan] = relationship(
        "SubscriptionPlan", back_populates="price_schedules"
    )


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    discount_type: Mapped[CouponDiscountType] = mapped_column(
        SAEnum(CouponDiscountType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    discount_value: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # percent 1-100 or fixed paise
    max_redemptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    per_user_max: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    allowed_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    allowed_plan_ids: Mapped[list | None] = mapped_column(
        JSON, nullable=True
    )  # list[int] or null = all
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coupon_id: Mapped[int] = mapped_column(ForeignKey("coupons.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    user_subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_subscriptions.id"), nullable=True
    )
    redeemed_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)


class UserBillingProfile(Base):
    __tablename__ = "user_billing_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True, nullable=False
    )
    razorpay_customer_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    default_payment_method_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, onupdate=ist_now, nullable=False
    )


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    plan_id: Mapped[int] = mapped_column(ForeignKey("subscription_plans.id"), nullable=False)
    plan_tier_snapshot: Mapped[PlanTier] = mapped_column(
        SAEnum(PlanTier, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    features_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[UserSubscriptionStatus] = mapped_column(
        SAEnum(UserSubscriptionStatus, values_callable=lambda x: [e.value for e in x]),
        default=UserSubscriptionStatus.PENDING,
        nullable=False,
        index=True,
    )
    billing_provider: Mapped[BillingProvider] = mapped_column(
        SAEnum(BillingProvider, values_callable=lambda x: [e.value for e in x]),
        default=BillingProvider.RAZORPAY,
        nullable=False,
    )
    razorpay_subscription_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trial_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    grace_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    pending_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("subscription_plans.id"), nullable=True
    )
    last_renewal_reminder_for_period_end: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, onupdate=ist_now, nullable=False
    )

    __table_args__ = (Index("ix_user_subscriptions_user_status", "user_id", "status"),)


class BillingTransaction(Base):
    __tablename__ = "billing_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_subscriptions.id"), index=True, nullable=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    razorpay_invoice_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    status: Mapped[BillingTransactionStatus] = mapped_column(
        SAEnum(BillingTransactionStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    raw_event_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)


class BillingRefund(Base):
    __tablename__ = "billing_refunds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    billing_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("billing_transactions.id"), index=True, nullable=False
    )
    razorpay_refund_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)


class BillingAdminSettings(Base):
    """Singleton-style global billing controls (first row id=1 used by app)."""

    __tablename__ = "billing_admin_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_card_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    payment_upi_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_trial_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    grace_period_days: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    renewal_reminder_days_before: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    dunning_retry_interval_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=ist_now, onupdate=ist_now, nullable=False
    )


class FreeTrialUsage(Base):
    __tablename__ = "free_trial_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    trial_key: Mapped[str] = mapped_column(String(64), nullable=False)
    consumed_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "trial_key", name="uq_free_trial_user_key"),)


class RazorpayWebhookEvent(Base):
    __tablename__ = "razorpay_webhook_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
