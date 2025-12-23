# Database Schema Enhancements for v26.1.1

**Date:** 2025-12-22  
**Related Release Plan:** RELEASE_PLAN_V26.1.1.md  
**Status:** Recommendations

---

## 📊 Executive Summary

This document identifies **8 database schema enhancements** that would significantly improve the implementation of v26.1.1 features, particularly for:
- Portfolio Value Chart (Phase 2.2)
- Targets Page (Phase 2.5)
- Broker Trading History (Phase 2.4)
- Performance Analytics (Phase 4.1)
- P&L Calculation Service (Phase 1.2)

**Priority Classification:**
- 🔴 **High Priority** (3 enhancements) - Critical for feature implementation
- 🟡 **Medium Priority** (3 enhancements) - Improves performance/UX
- 🟢 **Low Priority** (2 enhancements) - Nice to have, can be added later

---

## 🔴 High Priority Enhancements

### 1. Portfolio History/Snapshot Table

**Purpose:** Store historical portfolio value snapshots for Portfolio Value Chart (Phase 2.2)

**Current State:**
- ❌ No historical portfolio data storage
- ❌ Portfolio value must be calculated on-demand from positions
- ❌ Cannot show portfolio value trends over time

**Proposed Schema:**
```python
class PortfolioSnapshot(Base):
    """Daily portfolio value snapshots for historical tracking"""
    
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
    total_return: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # Total return %
    daily_return: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # Daily return %
    
    # Metadata
    snapshot_type: Mapped[str] = mapped_column(String(16), default="eod", nullable=False)  # 'eod', 'intraday'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    
    __table_args__ = (
        UniqueConstraint("user_id", "date", "snapshot_type", name="uq_portfolio_snapshot_user_date_type"),
        Index("ix_portfolio_snapshot_user_date", "user_id", "date"),
    )
```

**Benefits:**
- ✅ Enables Portfolio Value Chart without recalculating from positions
- ✅ Fast historical queries (indexed by date)
- ✅ Supports both EOD and intraday snapshots
- ✅ Enables return percentage calculations

**Implementation:**
- Create snapshot during EOD cleanup (Phase 3)
- Or create on-demand when chart is requested (if missing)
- Migration: Create table, backfill from positions table (optional)

**Files to Create/Modify:**
- `src/infrastructure/db/models.py` - Add `PortfolioSnapshot` model
- `alembic/versions/XXXX_add_portfolio_snapshots.py` - Migration
- `src/infrastructure/persistence/portfolio_snapshot_repository.py` - New repository
- `server/app/routers/portfolio.py` - Add historical endpoint

**Effort:** Medium (2-3 days)

---

### 2. Trade Mode Column in Orders Table

**Purpose:** Distinguish paper trading vs. broker trading orders (Phase 2.4: Broker Trading History)

**Current State:**
- ❌ No `trade_mode` column in `orders` table
- ❌ Must query `user_settings.trade_mode` to filter orders
- ❌ Cannot efficiently filter orders by trade mode
- ⚠️ Release plan mentions this (Future Enhancement section)

**Proposed Schema:**
```python
# Add to Orders model:
trade_mode: Mapped[TradeMode] = mapped_column(
    SAEnum(TradeMode), 
    nullable=True,  # NULL for legacy orders
    index=True
)  # 'paper' | 'broker'
```

**Benefits:**
- ✅ Fast filtering of broker vs. paper orders
- ✅ Enables unified reporting across modes
- ✅ Supports future unified DB-only storage migration
- ✅ Better query performance (indexed column)

**Implementation:**
- Add column (nullable for backward compatibility)
- Backfill from `user_settings.trade_mode` for existing orders
- Update order creation to set `trade_mode` from user settings

**Files to Create/Modify:**
- `src/infrastructure/db/models.py` - Add `trade_mode` to `Orders`
- `alembic/versions/XXXX_add_trade_mode_to_orders.py` - Migration
- `src/infrastructure/persistence/orders_repository.py` - Update create methods
- All order creation code - Set `trade_mode` when creating orders

**Effort:** Low-Medium (1-2 days)

---

### 3. Exit Details in Positions Table

**Purpose:** Store exit information when positions are closed (Phase 2.4: Broker Trading History, Phase 4.1: Analytics)

**Current State:**
- ❌ `Positions` table only has `closed_at` timestamp
- ❌ Exit price, exit reason, exit RSI stored in `order_metadata` (JSON)
- ❌ Cannot efficiently query closed positions by exit reason
- ❌ Must join with Orders table to get exit details

**Proposed Schema:**
```python
# Add to Positions model:
exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
exit_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 'EMA9_TARGET', 'RSI_EXIT', 'MANUAL', etc.
exit_rsi: Mapped[float | None] = mapped_column(Float, nullable=True)  # RSI10 at exit
realized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)  # Realized P&L for this position
realized_pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # Realized P&L %
sell_order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)  # Link to sell order
```

**Benefits:**
- ✅ Fast queries for closed positions with exit details
- ✅ Enables analytics by exit reason (Phase 4.1)
- ✅ Better performance for broker trading history (Phase 2.4)
- ✅ Reduces need to query Orders table for exit details

**Implementation:**
- Add columns (nullable for backward compatibility)
- Update `mark_closed()` method to populate exit details
- Backfill from Orders table for existing closed positions (optional)

**Files to Create/Modify:**
- `src/infrastructure/db/models.py` - Add exit fields to `Positions`
- `alembic/versions/XXXX_add_exit_details_to_positions.py` - Migration
- `src/infrastructure/persistence/positions_repository.py` - Update `mark_closed()`
- `modules/kotak_neo_auto_trader/sell_engine.py` - Populate exit details when closing

**Effort:** Medium (2-3 days)

---

## 🟡 Medium Priority Enhancements

### 4. Targets Table

**Purpose:** Store sell order targets in database instead of JSON file (Phase 2.5: Targets Page)

**Current State:**
- ✅ Paper trading: Targets stored in `active_sell_orders.json`
- ❌ Broker trading: Targets must be calculated from positions + EMA9
- ❌ No historical target tracking
- ❌ Cannot query targets efficiently

**Proposed Schema:**
```python
class Targets(Base):
    """Sell order targets for open positions"""
    
    __tablename__ = "targets"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"), index=True, nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    
    # Target information
    target_price: Mapped[float] = mapped_column(Float, nullable=False)  # EMA9 target
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)  # Average entry price
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)  # Current market price
    quantity: Mapped[float] = mapped_column(Float, nullable=False)  # Position quantity
    
    # Distance metrics
    distance_to_target: Mapped[float | None] = mapped_column(Float, nullable=True)  # % distance
    distance_to_target_absolute: Mapped[float | None] = mapped_column(Float, nullable=True)  # Absolute distance
    
    # Target metadata
    target_type: Mapped[str] = mapped_column(String(32), default="ema9", nullable=False)  # 'ema9', 'manual', etc.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # Active target
    trade_mode: Mapped[TradeMode] = mapped_column(SAEnum(TradeMode), nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, onupdate=ist_now, nullable=False)
    achieved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # When target was hit
    
    __table_args__ = (
        Index("ix_targets_user_symbol_active", "user_id", "symbol", "is_active"),
        Index("ix_targets_position", "position_id"),
    )
```

**Benefits:**
- ✅ Unified storage for paper and broker trading
- ✅ Fast queries for Targets page
- ✅ Historical target tracking
- ✅ Supports future unified DB-only storage migration

**Implementation:**
- Create table and migration
- Update sell order placement to create target records
- Migrate existing JSON targets to database (optional)
- Update Targets API to query from database

**Files to Create/Modify:**
- `src/infrastructure/db/models.py` - Add `Targets` model
- `alembic/versions/XXXX_add_targets_table.py` - Migration
- `src/infrastructure/persistence/targets_repository.py` - New repository
- `server/app/routers/targets.py` - Update to query from database
- `modules/kotak_neo_auto_trader/sell_engine.py` - Create target records

**Effort:** Medium (3-4 days)

---

### 5. P&L Calculation Audit Trail

**Purpose:** Track when P&L calculations were run and what data was used (Phase 1.2: PnL Service)

**Current State:**
- ❌ No tracking of calculation runs
- ❌ Cannot verify when last calculation occurred
- ❌ No audit trail for data accuracy

**Proposed Schema:**
```python
class PnlCalculationAudit(Base):
    """Audit trail for P&L calculations"""
    
    __tablename__ = "pnl_calculation_audit"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    
    # Calculation metadata
    calculation_type: Mapped[str] = mapped_column(String(32), nullable=False)  # 'on_demand', 'scheduled', 'backfill'
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
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # 'success', 'failed', 'partial'
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    
    # Metadata
    triggered_by: Mapped[str] = mapped_column(String(32), nullable=False)  # 'user', 'system', 'scheduled'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    
    __table_args__ = (
        Index("ix_pnl_audit_user_created", "user_id", "created_at"),
    )
```

**Benefits:**
- ✅ Audit trail for P&L calculations
- ✅ Debugging calculation issues
- ✅ Performance monitoring
- ✅ Verification of calculation accuracy

**Implementation:**
- Create table and migration
- Update PnL calculation service to log audit records
- Add API endpoint to view calculation history

**Files to Create/Modify:**
- `src/infrastructure/db/models.py` - Add `PnlCalculationAudit` model
- `alembic/versions/XXXX_add_pnl_calculation_audit.py` - Migration
- `server/app/services/pnl_calculation_service.py` - Log audit records
- `server/app/routers/pnl.py` - Add audit history endpoint

**Effort:** Low (1-2 days)

---

### 6. Historical Price Cache

**Purpose:** Cache historical prices for portfolio value calculations and charts (Phase 2.2: Portfolio Chart)

**Current State:**
- ❌ Prices fetched on-demand from yfinance/broker API
- ❌ No caching of historical prices
- ❌ Rate limiting issues with frequent API calls
- ❌ Slow portfolio value calculations

**Proposed Schema:**
```python
class PriceCache(Base):
    """Historical price cache for symbols"""
    
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
    source: Mapped[str] = mapped_column(String(32), default="yfinance", nullable=False)  # 'yfinance', 'broker', 'manual'
    cached_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, nullable=False)
    
    __table_args__ = (
        UniqueConstraint("symbol", "date", name="uq_price_cache_symbol_date"),
        Index("ix_price_cache_symbol_date", "symbol", "date"),
    )
```

**Benefits:**
- ✅ Reduces API calls (rate limiting)
- ✅ Faster portfolio value calculations
- ✅ Enables historical portfolio charts
- ✅ Can be populated during EOD cleanup

**Implementation:**
- Create table and migration
- Update price fetching to check cache first
- Populate cache during EOD cleanup or on-demand
- Add cache invalidation logic (TTL)

**Files to Create/Modify:**
- `src/infrastructure/db/models.py` - Add `PriceCache` model
- `alembic/versions/XXXX_add_price_cache.py` - Migration
- `src/infrastructure/persistence/price_cache_repository.py` - New repository
- `core/data_fetcher.py` or price service - Check cache before API call
- EOD cleanup service - Populate cache for next day

**Effort:** Medium (2-3 days)

---

## 🟢 Low Priority Enhancements

### 7. Export Job Tracking

**Purpose:** Track export operations for monitoring and user feedback (Phase 3.1: CSV Export)

**Current State:**
- ❌ No tracking of export operations
- ❌ Cannot monitor export performance
- ❌ No user feedback for long-running exports

**Proposed Schema:**
```python
class ExportJob(Base):
    """Export job tracking"""
    
    __tablename__ = "export_jobs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    
    # Export metadata
    export_type: Mapped[str] = mapped_column(String(32), nullable=False)  # 'csv', 'pdf'
    data_type: Mapped[str] = mapped_column(String(32), nullable=False)  # 'pnl', 'trades', 'signals', etc.
    date_range_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_range_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # 'pending', 'processing', 'completed', 'failed'
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
```

**Benefits:**
- ✅ Track export performance
- ✅ User feedback for long-running exports
- ✅ Debugging export issues
- ✅ Analytics on export usage

**Implementation:**
- Create table and migration
- Update export service to create job records
- Add progress tracking
- Add API endpoint to check export status

**Files to Create/Modify:**
- `src/infrastructure/db/models.py` - Add `ExportJob` model
- `alembic/versions/XXXX_add_export_jobs.py` - Migration
- `server/app/services/export_service.py` - Track export jobs
- `server/app/routers/export.py` - Add job status endpoint

**Effort:** Low (1-2 days)

---

### 8. Analytics Cache

**Purpose:** Cache expensive analytics calculations (Phase 4.1: Performance Analytics)

**Current State:**
- ❌ Analytics calculated on-demand
- ❌ Expensive calculations repeated on each request
- ❌ Slow analytics page load

**Proposed Schema:**
```python
class AnalyticsCache(Base):
    """Cached analytics calculations"""
    
    __tablename__ = "analytics_cache"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    
    # Cache key
    cache_key: Mapped[str] = mapped_column(String(128), index=True, nullable=False)  # e.g., 'win_rate_2024', 'sharpe_ratio_ytd'
    analytics_type: Mapped[str] = mapped_column(String(32), nullable=False)  # 'win_rate', 'sharpe_ratio', 'drawdown', etc.
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
```

**Benefits:**
- ✅ Faster analytics page load
- ✅ Reduces database load
- ✅ Better user experience
- ✅ Can be invalidated when new trades occur

**Implementation:**
- Create table and migration
- Update analytics service to check cache first
- Invalidate cache when new trades/positions added
- Add TTL for cache expiration

**Files to Create/Modify:**
- `src/infrastructure/db/models.py` - Add `AnalyticsCache` model
- `alembic/versions/XXXX_add_analytics_cache.py` - Migration
- `server/app/services/analytics_service.py` - Use cache
- Cache invalidation on order/position updates

**Effort:** Low (1-2 days)

---

## 📋 Implementation Priority & Timeline

### Phase 1: Critical Blockers (Week 1)
1. ✅ **Trade Mode Column** (1-2 days) - Enables broker trading history
2. ✅ **Exit Details in Positions** (2-3 days) - Enables analytics and history

### Phase 2: Core Features (Week 2-3)
3. ✅ **Portfolio Snapshots** (2-3 days) - Enables portfolio value chart
4. ✅ **Targets Table** (3-4 days) - Enables targets page

### Phase 3: Performance & Monitoring (Week 4-5)
5. ✅ **P&L Calculation Audit** (1-2 days) - Monitoring and debugging
6. ✅ **Historical Price Cache** (2-3 days) - Performance improvement

### Phase 4: Nice to Have (Week 6+)
7. ✅ **Export Job Tracking** (1-2 days) - User experience
8. ✅ **Analytics Cache** (1-2 days) - Performance improvement

**Total Effort:** 13-22 days (2.5-4.5 weeks)

---

## 🎯 Recommendations

### Must Have (v26.1.1)
1. **Trade Mode Column** - Critical for broker trading history
2. **Exit Details in Positions** - Critical for analytics and history
3. **Portfolio Snapshots** - Critical for portfolio value chart

### Should Have (v26.1.1)
4. **Targets Table** - Improves targets page implementation
5. **P&L Calculation Audit** - Helps with debugging and monitoring

### Nice to Have (Future Release)
6. **Historical Price Cache** - Performance optimization
7. **Export Job Tracking** - User experience improvement
8. **Analytics Cache** - Performance optimization

---

## 📝 Migration Strategy

### Backward Compatibility
- All new columns should be **nullable** initially
- Backfill existing data where possible
- Update application code to handle NULL values
- Gradual migration (new records use new fields, old records can be backfilled)

### Rollback Plan
- Keep old code paths (JSON files, existing queries)
- Feature flags to enable/disable new schema usage
- Can rollback migrations if issues occur

---

## 🔗 Integration with Release Plan

### Phase 1.2 (PnL Service)
- **P&L Calculation Audit** - Track calculation runs
- **Exit Details in Positions** - Better realized P&L calculation

### Phase 2.2 (Portfolio Value Chart)
- **Portfolio Snapshots** - Historical data source
- **Historical Price Cache** - Performance improvement

### Phase 2.4 (Broker Trading History)
- **Trade Mode Column** - Efficient filtering
- **Exit Details in Positions** - Better closed position data

### Phase 2.5 (Targets Page)
- **Targets Table** - Unified storage

### Phase 4.1 (Performance Analytics)
- **Exit Details in Positions** - Analytics by exit reason
- **Analytics Cache** - Performance improvement

---

## ✅ Next Steps

1. **Review and prioritize** these enhancements
2. **Create migration scripts** for high-priority items
3. **Update release plan** to include schema changes
4. **Plan backfill strategy** for existing data
5. **Update testing strategy** to cover new schema

---

**Last Updated:** 2025-12-22

