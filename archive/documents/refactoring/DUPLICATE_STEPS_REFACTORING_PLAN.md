# Duplicate Steps Refactoring Plan

**Status**: Planning
**Date**: 2025-01-28
**Priority**: High
**Estimated Duration**: 6-8 weeks

---

## Executive Summary

This refactoring plan addresses duplicate logic across 6 trading services (Analysis, Buy Orders, Pre-market Retry, EOD Cleanup, Position Monitor, Sell Monitor). The plan consolidates ~500+ lines of duplicate code into shared services, improving maintainability, consistency, and testability.

**Key Benefits:**
- Eliminate 500+ lines of duplicate code
- Ensure consistent behavior across all services
- Reduce maintenance burden by 60%
- Improve testability (test shared services once)
- Reduce API call overhead through caching

---

## Current State Analysis

### Services Affected
1. **Analysis Service** (4:00 PM) - Market analysis and recommendations
2. **Buy Orders Service** (4:05 PM) - Place AMO buy orders
3. **Pre-market Retry Service** (9:00 AM) - Retry failed orders
4. **EOD Cleanup Service** (6:00 PM) - End-of-day cleanup
5. **Position Monitor Service** (9:30 AM hourly) - Monitor positions
6. **Sell Monitor Service** (9:15 AM continuous) - Monitor sell orders

### Duplicate Areas Identified
- Price fetching (6 services)
- Indicators calculation (4 services)
- Holdings/positions checks (4 services)
- Open positions loading (3 services)
- Order status verification (3 services)
- Balance/portfolio validation (2 services)
- EMA9 calculation (2 services)
- History file loading (3 services)
- Live price subscription (2 services)

---

## Refactoring Phases

### Phase 1: Foundation Services (Weeks 1-2)
**Priority**: Critical
**Dependencies**: None
**Risk Level**: Medium

#### 1.1 Create PriceService
**Objective**: Standardize price fetching across all services

**Impact Areas:**
- `modules/kotak_neo_auto_trader/auto_trade_engine.py`
  - `get_daily_indicators()` method
  - Price fetching in `place_new_entries()`
  - Price fetching in `retry_pending_orders_from_db()`
- `modules/kotak_neo_auto_trader/position_monitor.py`
  - `_check_position_status()` method
  - Real-time LTP fetching logic
- `modules/kotak_neo_auto_trader/sell_engine.py`
  - `get_current_ltp()` method
  - Price fetching in `get_current_ema9()`
- `modules/kotak_neo_auto_trader/eod_cleanup.py`
  - Any price fetching for reconciliation
- `modules/kotak_neo_auto_trader/order_status_verifier.py`
  - Price fetching for verification

**New Components:**
- `modules/kotak_neo_auto_trader/services/price_service.py`
  - Unified price fetching interface
  - Support for real-time (LivePriceManager) and historical (yfinance) prices
  - Caching layer for price data
  - Fallback mechanisms

**Changes Required:**
- Replace all `fetch_ohlcv_yf()` calls with `PriceService.get_price()`
- Replace all `LivePriceManager.get_ltp()` calls with `PriceService.get_realtime_price()`
- Update all direct broker API price calls to use `PriceService`
- Maintain backward compatibility during transition

**Testing Strategy:**
- Unit tests for PriceService with mocked price sources
- Integration tests for price fetching fallback logic
- Performance tests for caching effectiveness
- Regression tests for all services using price data

**Rollout Plan:**
- Create PriceService with full test coverage
- Migrate one service at a time (start with Position Monitor)
- Monitor for 2-3 days before migrating next service
- Complete migration within 2 weeks

---

#### 1.2 Create IndicatorService
**Objective**: Centralize indicator calculations (RSI, EMA9, EMA200)

**Impact Areas:**
- `modules/kotak_neo_auto_trader/auto_trade_engine.py`
  - `get_daily_indicators()` method (can be simplified)
  - Indicator calculation in `place_new_entries()`
  - Indicator calculation in `retry_pending_orders_from_db()`
- `modules/kotak_neo_auto_trader/position_monitor.py`
  - `_check_position_status()` method
  - RSI, EMA9, EMA200 calculations
- `modules/kotak_neo_auto_trader/sell_engine.py`
  - `get_current_ema9()` method
  - EMA9 calculation with real-time LTP
- `core/indicators.py`
  - May need to refactor to use IndicatorService

**New Components:**
- `modules/kotak_neo_auto_trader/services/indicator_service.py`
  - `calculate_rsi()` method
  - `calculate_ema()` method (configurable period)
  - `calculate_ema9_realtime()` method (with current LTP)
  - `calculate_all_indicators()` method (batch calculation)
  - Caching for calculated indicators

**Changes Required:**
- Replace all `compute_indicators()` calls with `IndicatorService` methods
- Replace EMA9 calculations in Sell Monitor with `IndicatorService.calculate_ema9_realtime()`
- Update `get_daily_indicators()` to use `IndicatorService`
- Maintain existing indicator calculation logic (no behavior changes)

**Testing Strategy:**
- Unit tests for each indicator calculation method
- Integration tests comparing results with existing `compute_indicators()`
- Performance tests for batch indicator calculations
- Regression tests for all services using indicators

**Rollout Plan:**
- Create IndicatorService with comprehensive tests
- Migrate Position Monitor first (simpler use case)
- Migrate Sell Monitor (EMA9 real-time calculation)
- Migrate Buy Orders and Pre-market Retry
- Complete within 2 weeks

---

### Phase 2: Portfolio & Position Services (Weeks 2-3)
**Priority**: High
**Dependencies**: Phase 1.1 (PriceService)
**Risk Level**: Medium

#### 2.1 Create PortfolioService
**Objective**: Standardize holdings/positions checks across services

**Impact Areas:**
- `modules/kotak_neo_auto_trader/auto_trade_engine.py`
  - `has_holding()` method
  - `current_symbols_in_portfolio()` method
  - Holdings checks in `place_new_entries()`
  - Holdings checks in `retry_pending_orders_from_db()`
- `modules/kotak_neo_auto_trader/position_monitor.py`
  - Implicit holdings check via history loading
- `modules/kotak_neo_auto_trader/sell_engine.py`
  - Implicit holdings check via `get_open_positions()`
- `modules/kotak_neo_auto_trader/eod_cleanup.py`
  - Holdings reconciliation logic

**New Components:**
- `modules/kotak_neo_auto_trader/services/portfolio_service.py`
  - `has_position()` method (unified holdings check)
  - `get_current_positions()` method (broker API + history)
  - `get_portfolio_count()` method
  - `check_portfolio_capacity()` method
  - Caching for holdings data

**Changes Required:**
- Replace `has_holding()` with `PortfolioService.has_position()`
- Replace `current_symbols_in_portfolio()` with `PortfolioService.get_current_positions()`
- Update portfolio limit checks to use `PortfolioService.check_portfolio_capacity()`
- Unify broker API and history file checks

**Testing Strategy:**
- Unit tests for PortfolioService with mocked broker API
- Integration tests for holdings synchronization
- Tests for cache invalidation logic
- Regression tests for all services checking holdings

**Rollout Plan:**
- Create PortfolioService
- Migrate Buy Orders service first
- Migrate Pre-market Retry
- Update Position Monitor and Sell Monitor to use unified service
- Complete within 1 week

---

#### 2.2 Create PositionLoader
**Objective**: Centralize open positions loading from history

**Impact Areas:**
- `modules/kotak_neo_auto_trader/position_monitor.py`
  - `_get_open_positions()` method
- `modules/kotak_neo_auto_trader/sell_engine.py`
  - `get_open_positions()` method
- `modules/kotak_neo_auto_trader/eod_cleanup.py`
  - Any position loading for reconciliation

**New Components:**
- `modules/kotak_neo_auto_trader/services/position_loader.py`
  - `load_open_positions()` method
  - `get_positions_by_symbol()` method
  - Caching for loaded positions
  - File change detection for cache invalidation

**Changes Required:**
- Replace `_get_open_positions()` in Position Monitor
- Replace `get_open_positions()` in Sell Monitor
- Update EOD Cleanup to use PositionLoader
- Add caching to reduce file I/O

**Testing Strategy:**
- Unit tests for PositionLoader with mocked history file
- Tests for cache invalidation on file changes
- Performance tests for large history files
- Regression tests for services using positions

**Rollout Plan:**
- Create PositionLoader
- Migrate all three services simultaneously (low risk)
- Complete within 3 days

---

### Phase 3: Order Validation & Verification (Weeks 3-4)
**Priority**: High
**Dependencies**: Phase 2.1 (PortfolioService)
**Risk Level**: High

#### 3.1 Create OrderValidationService
**Objective**: Consolidate order placement validation logic

**Impact Areas:**
- `modules/kotak_neo_auto_trader/auto_trade_engine.py`
  - Balance checks in `place_new_entries()`
  - Portfolio limit checks in `place_new_entries()`
  - Duplicate order checks in `place_new_entries()`
  - All validation in `retry_pending_orders_from_db()`
  - `get_affordable_qty()` method
  - `get_available_cash()` method
- `src/application/services/paper_trading_service_adapter.py`
  - Similar validation logic for paper trading

**New Components:**
- `modules/kotak_neo_auto_trader/services/order_validation_service.py`
  - `validate_order_placement()` method (comprehensive validation)
  - `check_balance()` method
  - `check_portfolio_capacity()` method
  - `check_duplicate_order()` method
  - `check_volume_ratio()` method
  - Returns structured `ValidationResult` object

**Changes Required:**
- Extract all validation logic from `place_new_entries()`
- Extract all validation logic from `retry_pending_orders_from_db()`
- Replace individual checks with `OrderValidationService.validate_order_placement()`
- Update error messages to use ValidationResult
- Maintain existing validation behavior (no logic changes)

**Testing Strategy:**
- Comprehensive unit tests for each validation check
- Integration tests for full validation flow
- Tests for edge cases (insufficient balance, portfolio limit, etc.)
- Regression tests comparing old vs new validation results

**Rollout Plan:**
- Create OrderValidationService with full test coverage
- Migrate Buy Orders service first (most complex)
- Monitor for 3-4 days
- Migrate Pre-market Retry
- Complete within 1.5 weeks

---

#### 3.2 Consolidate Order Verification
**Objective**: Eliminate redundant order verification

**Impact Areas:**
- `modules/kotak_neo_auto_trader/order_status_verifier.py`
  - Continuous verification logic (keep as primary)
- `modules/kotak_neo_auto_trader/sell_engine.py`
  - `check_order_execution()` method
  - `has_completed_sell_order()` method
  - Should use OrderStatusVerifier results instead
- `modules/kotak_neo_auto_trader/eod_cleanup.py`
  - `_verify_all_pending_orders()` method
  - Should check if OrderStatusVerifier ran recently

**Changes Required:**
- Make Sell Monitor use OrderStatusVerifier results (avoid duplicate API calls)
- Make EOD Cleanup check OrderStatusVerifier last run time
- Skip EOD verification if OrderStatusVerifier ran within last 15 minutes
- Add method to OrderStatusVerifier to get verification results for specific orders

**Testing Strategy:**
- Tests for OrderStatusVerifier result sharing
- Tests for conditional EOD verification
- Performance tests to measure API call reduction
- Regression tests for order status accuracy

**Rollout Plan:**
- Update OrderStatusVerifier to expose results
- Update Sell Monitor to use shared results
- Update EOD Cleanup with conditional verification
- Complete within 1 week

---

### Phase 4: Subscription & Caching (Weeks 4-5)
**Priority**: Medium
**Dependencies**: Phase 1.1 (PriceService)
**Risk Level**: Low

#### 4.1 Centralize Live Price Subscription
**Objective**: Eliminate duplicate subscription logic

**Impact Areas:**
- `modules/kotak_neo_auto_trader/position_monitor.py`
  - `price_manager.subscribe_to_positions()` call
- `modules/kotak_neo_auto_trader/run_trading_service.py`
  - `price_cache.subscribe()` call in `run_sell_monitor()`
- `modules/kotak_neo_auto_trader/auto_trade_engine.py`
  - Any subscription logic

**Changes Required:**
- Move subscription logic to PriceService
- Update all services to use `PriceService.subscribe_to_symbols()`
- Add subscription deduplication (avoid subscribing to same symbol twice)
- Track subscription lifecycle

**Testing Strategy:**
- Tests for subscription deduplication
- Tests for subscription cleanup
- Performance tests for subscription overhead
- Regression tests for price updates

**Rollout Plan:**
- Add subscription methods to PriceService
- Migrate all services
- Complete within 3 days

---

#### 4.2 Implement Caching Strategy
**Objective**: Reduce redundant API calls and file I/O

**Impact Areas:**
- All services using PriceService (cache prices)
- All services using IndicatorService (cache indicators)
- All services using PortfolioService (cache holdings)
- All services using PositionLoader (cache positions)

**Changes Required:**
- Add caching layer to PriceService (TTL: 30 seconds for real-time, 5 minutes for historical)
- Add caching layer to IndicatorService (TTL: 1 minute)
- Add caching layer to PortfolioService (TTL: 2 minutes)
- Add caching layer to PositionLoader (invalidate on file change)
- Add cache warming strategies

**Testing Strategy:**
- Tests for cache hit/miss scenarios
- Tests for cache invalidation
- Performance tests measuring API call reduction
- Load tests for cache memory usage

**Rollout Plan:**
- Implement caching incrementally (one service at a time)
- Monitor cache hit rates
- Adjust TTL values based on usage patterns
- Complete within 1 week

---

### Phase 5: Integration & Cleanup (Weeks 5-6)
**Priority**: Medium
**Dependencies**: All previous phases
**Risk Level**: Low

#### 5.1 Service Integration
**Objective**: Ensure all services use new shared services

**Impact Areas:**
- All 6 trading services
- Paper trading adapter
- Any standalone scripts

**Changes Required:**
- Audit all services for remaining duplicate code
- Update any missed direct calls to use shared services
- Remove deprecated methods (after migration period)
- Update documentation

**Testing Strategy:**
- Full integration tests for all services
- End-to-end tests for complete trading workflows
- Performance benchmarks comparing before/after
- Regression tests for all service combinations

**Rollout Plan:**
- Complete audit of all services
- Fix any remaining issues
- Remove deprecated code
- Complete within 1 week

---

#### 5.2 Code Cleanup
**Objective**: Remove deprecated code and improve documentation

**Impact Areas:**
- All modules with deprecated methods
- Documentation files
- Test files

**Changes Required:**
- Remove deprecated methods (after 2-week deprecation period)
- Update all documentation
- Add usage examples for new services
- Update architecture diagrams

**Testing Strategy:**
- Verify no references to deprecated methods
- Documentation review
- Code review for consistency

**Rollout Plan:**
- Mark methods as deprecated
- Wait 2 weeks for any external usage
- Remove deprecated code
- Update documentation
- Complete within 1 week

---

## Risk Assessment & Mitigation

### High-Risk Areas

**1. Order Validation Changes**
- **Risk**: Changing validation logic could allow invalid orders
- **Mitigation**:
  - Comprehensive test coverage (100% for validation logic)
  - Side-by-side comparison tests (old vs new)
  - Gradual rollout with monitoring
  - Rollback plan ready

**2. Price Service Integration**
- **Risk**: Price fetching failures could break all services
- **Mitigation**:
  - Robust fallback mechanisms
  - Extensive error handling
  - Monitoring and alerting
  - Gradual migration (one service at a time)

**3. Indicator Calculation Changes**
- **Risk**: Different calculation results could affect trading decisions
- **Mitigation**:
  - Comparison tests ensuring identical results
  - No changes to calculation formulas
  - Validation against existing calculations

### Medium-Risk Areas

**1. Portfolio Service Integration**
- **Risk**: Holdings checks might miss positions
- **Mitigation**:
  - Dual-source validation (broker API + history)
  - Comprehensive testing
  - Monitoring for discrepancies

**2. Caching Implementation**
- **Risk**: Stale cache data could cause incorrect decisions
- **Mitigation**:
  - Appropriate TTL values
  - Cache invalidation strategies
  - Monitoring cache hit rates and freshness

---

## Testing Strategy

### Unit Testing
- **Target**: 90%+ code coverage for all new services
- **Focus**: Individual methods, edge cases, error handling
- **Tools**: pytest, unittest.mock

### Integration Testing
- **Target**: All service interactions
- **Focus**: Service-to-service communication, data flow
- **Tools**: pytest with fixtures

### Regression Testing
- **Target**: All existing functionality
- **Focus**: Behavior comparison (before vs after)
- **Tools**: Existing test suite + new comparison tests

### Performance Testing
- **Target**: API call reduction, response times
- **Focus**: Cache effectiveness, service overhead
- **Tools**: pytest-benchmark, custom metrics

### End-to-End Testing
- **Target**: Complete trading workflows
- **Focus**: Full service interactions, real-world scenarios
- **Tools**: Integration test suite

---

## Success Metrics

### Code Quality
- **Duplicate code reduction**: Target 80%+ reduction
- **Code coverage**: Maintain 85%+ for new services
- **Cyclomatic complexity**: Reduce by 30%+

### Performance
- **API call reduction**: Target 40%+ reduction
- **Response time**: No degradation (target 10% improvement)
- **Cache hit rate**: Target 60%+ for frequently accessed data

### Maintainability
- **Lines of code**: Reduce by 500+ lines
- **Service coupling**: Reduce by 50%+
- **Test maintenance**: Reduce by 40%+ (test shared services once)

### Reliability
- **Error rate**: No increase (target 10% reduction)
- **Service uptime**: Maintain 99.9%+
- **Data consistency**: 100% (no discrepancies)

---

## Rollout Schedule

### Week 1-2: Foundation Services
- Day 1-3: Create PriceService, full testing
- Day 4-7: Migrate Position Monitor
- Day 8-10: Migrate Sell Monitor
- Day 11-14: Migrate Buy Orders and Pre-market Retry

### Week 2-3: Portfolio & Position Services
- Day 15-17: Create PortfolioService
- Day 18-20: Migrate Buy Orders and Pre-market Retry
- Day 21-22: Create PositionLoader
- Day 23-24: Migrate all position loading

### Week 3-4: Order Validation & Verification
- Day 25-28: Create OrderValidationService
- Day 29-32: Migrate Buy Orders
- Day 33-35: Migrate Pre-market Retry
- Day 36-38: Consolidate order verification

### Week 4-5: Subscription & Caching
- Day 39-41: Centralize subscriptions
- Day 42-48: Implement caching strategy
- Day 49-50: Performance optimization

### Week 5-6: Integration & Cleanup
- Day 51-53: Service integration audit
- Day 54-56: Code cleanup
- Day 57-60: Documentation and final testing

---

## Dependencies & Prerequisites

### Technical Dependencies
- Existing test infrastructure (pytest)
- Monitoring and logging systems
- Database access for portfolio checks
- Broker API access for testing

### Team Dependencies
- Development team availability
- QA team for testing
- DevOps for deployment support

### External Dependencies
- No external service dependencies
- No breaking changes to external APIs

---

## Post-Refactoring Maintenance

### Monitoring
- Service health metrics
- API call reduction metrics
- Cache performance metrics
- Error rates and types

### Documentation
- Update architecture diagrams
- Update service interaction diagrams
- Update API documentation
- Update runbooks

### Training
- Team training on new service architecture
- Code review guidelines
- Best practices documentation

---

## Appendix: File Impact Summary

### New Files to Create
- `modules/kotak_neo_auto_trader/services/price_service.py`
- `modules/kotak_neo_auto_trader/services/indicator_service.py`
- `modules/kotak_neo_auto_trader/services/portfolio_service.py`
- `modules/kotak_neo_auto_trader/services/position_loader.py`
- `modules/kotak_neo_auto_trader/services/order_validation_service.py`
- `modules/kotak_neo_auto_trader/services/__init__.py`

### Files to Modify
- `modules/kotak_neo_auto_trader/auto_trade_engine.py` (major changes)
- `modules/kotak_neo_auto_trader/position_monitor.py` (moderate changes)
- `modules/kotak_neo_auto_trader/sell_engine.py` (moderate changes)
- `modules/kotak_neo_auto_trader/eod_cleanup.py` (minor changes)
- `modules/kotak_neo_auto_trader/order_status_verifier.py` (minor changes)
- `modules/kotak_neo_auto_trader/run_trading_service.py` (minor changes)
- `src/application/services/paper_trading_service_adapter.py` (moderate changes)

### Files to Deprecate (after migration)
- No files to delete, but methods will be deprecated
- Methods marked for removal after 2-week deprecation period

---

## Conclusion

This refactoring plan addresses duplicate code across all trading services, improving maintainability, consistency, and performance. The phased approach minimizes risk while delivering incremental value. Success depends on comprehensive testing, gradual rollout, and continuous monitoring.

**Next Steps:**
1. Review and approve this plan
2. Allocate resources (developers, QA, DevOps)
3. Set up monitoring and metrics
4. Begin Phase 1 implementation
