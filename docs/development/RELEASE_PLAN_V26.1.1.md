# Release Plan v26.1.1 - Enhanced Dashboard & Analytics

**Target Release Date:** TBD
**Version:** 26.1.1
**Status:** Planning
**Base Version:** 26.1.0

---

## 📋 Quick Summary

### 🎯 Release Focus
Complete all pending dashboard enhancements, visual analytics, and data export capabilities.

### 📦 Key Features by Phase

**Phase 1: Foundation (Week 1)**
- Install Chart Library (Recharts)
- Chart infrastructure setup

**Phase 2: Core Charts (Week 1-2)**
- PnL Data Population Service (prerequisite for charts)
- P&L Trend Chart with time ranges
- Portfolio Value Chart with historical data
- Broker Trading History (parity with paper trading)
- Targets Page Implementation

**Phase 3: Dashboard & Export (Week 2-3)**
- Complete Enhanced Dashboard Metrics (win rate, avg profit, best/worst trades)
- Complete CSV Export UI (connect backend to frontend)
- PDF Report Generation

**Phase 4: Analytics (Week 3-4)**
- Performance Analytics Page
- Risk Metrics Dashboard

**Phase 5: Watchlist (Week 4-5)**
- Watchlist Feature (database + API + UI)
- Watchlist Dashboard Widget

**Phase 6: UX Polish (Week 5-6)**
- Complete Saved Filters & Preferences

### ⏱️ Timeline
**Total Duration:** 6 weeks
**Target Release:** TBD

### 📊 Success Metrics
- Dashboard views ↑ 30%
- Session time ↑ 20%
- Export usage > 50% of users
- Analytics page views > 40% of users
- Dashboard load < 2 seconds
- Charts render < 1 second

---

## 📋 Executive Summary

This release focuses on completing all pending dashboard enhancements, visual analytics, and data export capabilities from the previous release plan. The goal is to provide traders with comprehensive insights into their trading performance through interactive charts, complete data export functionality, and advanced analytics.

**Scope:** All pending features from v2.0 release plan that are not yet implemented.

### Related Infrastructure Work

**Unified DB-Only Storage Migration** (Future Release)
- 📄 **Implementation Plan**: [`../kotak_neo_trader/UNIFIED_DB_IMPLEMENTATION_COMPLETE.md`](../kotak_neo_trader/UNIFIED_DB_IMPLEMENTATION_COMPLETE.md)
- **Goal**: Migrate from hybrid storage (paper=file, real=DB) to unified DB-only approach
- **Timeline**: 6-8 weeks
- **Status**: Planning phase
- **Impact**: This infrastructure improvement will enable unified reporting and better data consistency across paper and real trading modes

---

## 🎯 Release Goals

1. **Visual Analytics**: Implement interactive charts for P&L and portfolio visualization
2. **Data Portability**: Complete CSV export UI and add PDF report generation
3. **Enhanced Dashboard**: Complete dashboard metrics and add advanced analytics
4. **Performance Insights**: Add comprehensive analytics page with performance metrics
5. **User Experience**: Complete saved filters and preferences functionality

---

## 📦 Features Breakdown

### Phase 1: Chart Library & Infrastructure Setup (Foundation)

#### 1.1 Install Chart Library
**Priority:** 🔴 High
**Effort:** Low (0.5 days)
**Dependencies:** None

**Description:**
- Install and configure charting library (Recharts recommended for React)
- Set up chart utilities and helpers
- Configure chart themes to match application design

**Deliverables:**
- [ ] Install `recharts` package in `web/package.json`
- [ ] Create chart theme configuration
- [ ] Create reusable chart wrapper components
- [ ] Add chart styling to match dark theme

**Acceptance Criteria:**
- Chart library installed and configured
- Chart components match application theme
- No bundle size issues

**Files to Modify:**
- `web/package.json` - Add recharts dependency
- `web/src/components/charts/` - Create chart components directory

---

#### 1.2 PnL Data Population Service
**Priority:** 🔴 High
**Effort:** Medium (2-3 days)
**Dependencies:** None (must complete before 2.1 P&L Trend Chart)

**Description:**
- Create service to populate `pnl_daily` table with calculated P&L data
- Calculate daily P&L from positions and orders tables
- Support both paper trading and broker trading modes
- Enable on-demand calculation and scheduled daily updates

**Current State:**
- ✅ `pnl_daily` table exists
- ✅ P&L API endpoints exist (`/api/v1/user/pnl/daily`, `/api/v1/user/pnl/summary`)
- ❌ `pnl_daily` table is empty (no data populated)
- ❌ P&L Page shows "No P&L data available"
- ✅ Positions and orders tables have data but P&L not aggregated

**Deliverables:**
- [ ] PnL calculation service (`server/app/services/pnl_calculation_service.py`)
- [ ] Calculate realized P&L from closed positions
- [ ] Calculate unrealized P&L from open positions
- [ ] Estimate fees from orders (0.1% per transaction, or use actual if available)
- [ ] Daily P&L aggregation logic
- [ ] On-demand calculation endpoint (for immediate updates)
- [ ] Background job/service for daily EOD calculation (optional, can be scheduled later)
- [ ] Support for both paper trading and broker trading modes
- [ ] Historical data backfill capability
- [ ] Error handling and logging

**Acceptance Criteria:**
- P&L data populates correctly in `pnl_daily` table
- Realized P&L calculated from closed positions accurately
- Unrealized P&L calculated from open positions with current prices
- Fees estimated or calculated correctly
- Works for both paper and broker trading modes
- On-demand calculation completes within 5 seconds
- Historical backfill works correctly

**Files to Create/Modify:**
- `server/app/services/pnl_calculation_service.py` - New PnL calculation service
- `server/app/routers/pnl.py` - Add endpoint to trigger calculation/backfill
- `src/infrastructure/persistence/pnl_repository.py` - May need upsert improvements
- `src/infrastructure/persistence/positions_repository.py` - Query positions
- `src/infrastructure/persistence/orders_repository.py` - Query orders for fees

**API Requirements:**
- `POST /api/v1/user/pnl/calculate` - Trigger on-demand P&L calculation
- `POST /api/v1/user/pnl/backfill` - Backfill historical P&L data (optional)

**Implementation Details:**

1. **Realized P&L Calculation:**
   - Query closed positions (`positions` table where `closed_at IS NOT NULL`)
   - Calculate: `(exit_price - avg_price) * quantity` for each closed position
   - Sum by date (using `closed_at` date)
   - Account for fees (estimate or use actual from orders)

2. **Unrealized P&L Calculation:**
   - Query open positions (`positions` table where `closed_at IS NULL`)
   - Get current price (from broker API or yfinance)
   - Calculate: `(current_price - avg_price) * quantity` for each open position
   - Sum by date (using current date)
   - Update daily as prices change

3. **Fees Calculation:**
   - Option 1: Estimate 0.1% per transaction (buy + sell)
   - Option 2: Use actual charges from `order_metadata` if available
   - Sum fees by date

4. **Daily Aggregation:**
   - Group by `user_id` and `date`
   - Store in `pnl_daily` table using `upsert` (handles duplicates)
   - Ensure one record per user per date

**Integration Points:**
- Prerequisite for Phase 2.1 (P&L Trend Chart) - chart needs data
- Prerequisite for Phase 2.3 (Dashboard Metrics) - metrics need P&L data
- Prerequisite for Phase 4.1 (Performance Analytics) - analytics need P&L data
- Can be scheduled as EOD job in future (not required for v26.1.1)

**Testing Requirements:**
- Unit tests for P&L calculation logic
- Unit tests for realized vs unrealized P&L
- Integration tests for calculation service
- Test with both paper and broker trading data
- Test historical backfill

**Future Enhancements (Not in v26.1.1):**
- Scheduled EOD job for automatic daily calculation
- Real-time P&L updates via WebSocket
- More accurate fee calculation from broker API
- P&L breakdown by symbol/strategy

---

### Phase 2: Core Dashboard Enhancements (High Priority)

#### 2.1 P&L Trend Chart
**Priority:** 🔴 High
**Effort:** Medium (3-5 days)
**Dependencies:** 1.1 (Chart Library), 1.2 (PnL Data Population Service)

**Description:**
- Add interactive line chart showing P&L over time
- Support multiple time ranges (7 days, 30 days, 90 days, 1 year)
- Show realized vs unrealized P&L separately
- Display key milestones (best day, worst day, break-even points)

**Current State:**
- ✅ P&L API endpoints exist (`/api/v1/user/pnl/daily`, `/api/v1/user/pnl/summary`)
- ✅ P&L Page exists (`web/src/routes/dashboard/PnlPage.tsx`)
- ❌ P&L data not populated in `pnl_daily` table (blocking chart display)
- ❌ No chart component
- ❌ No time range selector

**Deliverables:**
- [ ] P&L trend chart component using Recharts
- [ ] Time range selector (7d, 30d, 90d, 1y)
- [ ] Realized vs unrealized P&L toggle/overlay
- [ ] Tooltip with detailed information (date, P&L, realized, unrealized)
- [ ] Key milestone markers (best day, worst day, break-even)
- [ ] Mobile-responsive chart
- [ ] Loading states and error handling

**Acceptance Criteria:**
- Chart loads within 2 seconds
- Supports all time ranges
- Works on mobile devices
- Tooltips show accurate data
- Smooth interactions and animations

**Files to Create/Modify:**
- `web/src/components/charts/PnlTrendChart.tsx` - New chart component
- `web/src/routes/dashboard/PnlPage.tsx` - Add chart and time range selector
- `web/src/api/pnl.ts` - Add time range parameter support if needed

**API Requirements:**
- Verify `/api/v1/user/pnl/daily` supports date range parameters
- May need to add endpoint for historical P&L data if not available

---

#### 2.2 Portfolio Value Chart
**Priority:** 🔴 High
**Effort:** Medium (2-3 days)
**Dependencies:** 1.1 (Chart Library), 2.1 (P&L Chart for reference)

**Description:**
- Line chart showing portfolio value over time
- Overlay with initial capital for reference
- Highlight major gains/losses
- Show return percentage trend

**Current State:**
- ✅ Portfolio value displayed as metric card on dashboard
- ✅ Portfolio data API exists (`/api/v1/user/portfolio`)
- ❌ No historical portfolio data API
- ❌ No chart component

**Deliverables:**
- [ ] Historical portfolio data API endpoint
- [ ] Portfolio value chart component
- [ ] Initial capital reference line
- [ ] Return percentage overlay/annotation
- [ ] Major gain/loss markers
- [ ] Time range selector
- [ ] Mobile-responsive chart

**Acceptance Criteria:**
- Chart updates in real-time (when data refreshes)
- Shows accurate portfolio value over time
- Initial capital line clearly visible
- Mobile-responsive
- Smooth animations

**Files to Create/Modify:**
- `server/app/routers/paper_trading.py` or new router - Add historical portfolio endpoint
- `web/src/components/charts/PortfolioValueChart.tsx` - New chart component
- `web/src/routes/dashboard/PaperTradingPage.tsx` - Add chart
- `web/src/api/paper-trading.ts` - Add historical portfolio API call

**API Requirements:**
- Create `/api/v1/user/portfolio/history` endpoint
- Return portfolio value snapshots over time
- Support date range filtering

---

#### 2.3 Complete Enhanced Dashboard Metrics
**Priority:** 🟡 Medium
**Effort:** Low (1-2 days)
**Dependencies:** 1.2 (PnL Data Population Service) - Metrics need P&L data

**Description:**
- Complete missing dashboard metrics
- Win rate percentage
- Average profit per trade
- Best/worst trade
- Ensure all metrics are accurate and performant
- **Note:** Requires P&L data to be populated (from 1.2)

**Current State:**
- ✅ Basic metrics exist (Portfolio Value, Total P&L, Active Signals, Open Orders)
- ✅ Active positions count available
- ✅ Total trades count available
- ❌ Win rate percentage - NOT implemented
- ❌ Average profit per trade - NOT implemented
- ❌ Best/worst trade - NOT implemented

**Deliverables:**
- [ ] Win rate calculation API endpoint
- [ ] Average profit per trade calculation
- [ ] Best/worst trade API endpoint
- [ ] Additional metric cards on dashboard
- [ ] Loading states for new metrics
- [ ] Error handling

**Acceptance Criteria:**
- All metrics display correctly
- Fast loading (< 1 second)
- Mobile-friendly layout
- Accurate calculations

**Files to Create/Modify:**
- `server/app/routers/pnl.py` or new router - Add metrics endpoints
- `web/src/routes/dashboard/DashboardHome.tsx` - Add new metric cards
- `web/src/api/pnl.ts` or new API file - Add metrics API calls

**API Requirements:**
- `/api/v1/user/metrics/win-rate` - Calculate win rate
- `/api/v1/user/metrics/average-profit` - Calculate average profit per trade
- `/api/v1/user/metrics/best-worst-trades` - Get best and worst trades

---

#### 2.4 Broker Trading History
**Priority:** 🔴 High
**Effort:** Medium (3-4 days)
**Dependencies:** None (can be done in parallel with other Phase 2 items)

**Description:**
- Add broker trading history endpoint and UI page
- Provide complete trade history for real broker trades (similar to paper trading history)
- Show all transactions, closed positions with P&L, and statistics
- Address critical edge cases: trade mode filtering, partial fills, symbol normalization, manual trades

**Current State:**
- ✅ Paper trading history exists (`/api/v1/user/paper-trading/history`)
- ✅ Paper trading history page exists (`web/src/routes/dashboard/PaperTradingHistoryPage.tsx`)
- ✅ Broker orders and positions stored in database (`orders` and `positions` tables)
- ❌ No broker trade history endpoint
- ❌ No broker trade history UI page

**Deliverables:**
- [ ] Broker trade history API endpoint (`/api/v1/user/broker/history`)
- [ ] Trade history calculation logic (transactions, closed positions, statistics)
- [ ] Edge case handling:
  - Trade mode validation (ensure user is in broker mode)
  - Partial fill handling (use `execution_qty` when available)
  - Symbol normalization for matching
  - Manual trade filtering/flagging
  - FIFO matching without in-place mutation
  - Timezone-aware timestamp handling
- [ ] Broker trade history UI page (`web/src/routes/dashboard/BrokerTradingHistoryPage.tsx`)
- [ ] Reuse existing `TradeHistory` schema and components where possible
- [ ] Date range filtering support
- [ ] Pagination for large datasets
- [ ] Loading states and error handling
- [ ] Mobile-responsive design

**Acceptance Criteria:**
- API endpoint returns data in same format as paper trading history
- All transactions from `orders` table are included
- Closed positions calculated correctly using FIFO matching
- Statistics (win rate, P&L, etc.) are accurate
- Only broker trades included (no paper trading data leakage)
- Handles partial fills correctly
- Fast response time (< 2 seconds for typical datasets)
- Works on mobile devices
- Error handling for edge cases

**Files to Create/Modify:**
- `server/app/routers/broker.py` - Add `/history` endpoint
- `web/src/routes/dashboard/BrokerTradingHistoryPage.tsx` - New page component
- `web/src/api/broker.ts` - Add `getBrokerTradingHistory()` function
- `web/src/router.tsx` - Add broker history route
- `web/src/routes/AppShell.tsx` - Add navigation link (if needed)

**API Requirements:**
- Endpoint: `GET /api/v1/user/broker/history`
- Query parameters:
  - `from_date` (optional): Filter transactions from date (ISO format)
  - `to_date` (optional): Filter transactions to date (ISO format)
  - `limit` (optional): Limit number of transactions (default: 1000, max: 10000)
- Response: Same `TradeHistory` schema as paper trading
- Validation: Ensure user is in broker mode (return 400 if not)

**Implementation Details:**

1. **Backend Implementation** (`server/app/routers/broker.py`):
   - Add `get_broker_trading_history()` endpoint
   - Query `orders` table for executed orders (status ONGOING or CLOSED with execution details)
   - Query `positions` table for closed positions
   - Convert orders to transactions format
   - Match buy/sell orders using FIFO algorithm (without in-place mutation)
   - Calculate closed positions from matched transactions
   - Calculate statistics (win rate, total P&L, etc.)
   - Filter by trade mode (validate user is in broker mode)
   - Handle partial fills using `execution_qty`
   - Normalize symbols for matching
   - Add date range filtering
   - Add pagination support

2. **Frontend Implementation**:
   - Create `BrokerTradingHistoryPage.tsx` similar to `PaperTradingHistoryPage.tsx`
   - Reuse existing `TradeHistory` type and components
   - Add date range picker
   - Add export button (connects to Phase 3.1 CSV export)
   - Show loading states
   - Handle errors gracefully

3. **Edge Cases to Address**:
   - Trade mode validation: Check `user_settings.trade_mode == TradeMode.BROKER`
   - Partial fills: Use `order.execution_qty` if available, otherwise `order.quantity`
   - Symbol matching: Normalize symbols using `extract_base_symbol()` utility
   - Manual trades: Option to filter or flag (add `is_manual` field to transactions)
   - FIFO matching: Create copies for matching, don't mutate original transaction objects
   - Charges: Use actual charges from `order_metadata` if available, otherwise estimate
   - Exit price: Match sell orders to closed positions by timestamp proximity
   - Timezone: Ensure all timestamps are timezone-aware
   - Performance: Add pagination and date filtering to avoid loading all orders

**Integration Points:**
- Reuses `TradeHistory` schema from `server/app/routers/paper_trading.py`
- Integrates with Phase 3.1 CSV export (add broker history to export list)
- Can be used by Phase 4.1 Performance Analytics (as data source)
- Shares UI components with paper trading history page

**Testing Requirements:**
- Unit tests for FIFO matching algorithm
- Unit tests for statistics calculations
- Integration tests for API endpoint
- Edge case tests (partial fills, manual trades, symbol mismatches)
- Performance tests (large datasets)
- E2E tests for UI page

**Dependencies:**
- `src/infrastructure/persistence/orders_repository.py` - Query orders
- `src/infrastructure/persistence/positions_repository.py` - Query positions
- `src/infrastructure/persistence/settings_repository.py` - Get trade mode
- `modules/kotak_neo_auto_trader/utils/symbol_utils.py` - Symbol normalization

**Future Enhancements (Not in v26.1.1):**
- Add `trade_mode` column to `orders` table (from UNIFIED_DB_IMPLEMENTATION_COMPLETE.md)
- Store actual charges in `order_metadata` for accurate P&L
- Add open positions to history (currently only closed positions)
- Add caching for calculated history
- Real-time updates via WebSocket

---

#### 2.5 Targets Page Implementation
**Priority:** 🟡 Medium
**Effort:** Low (1-2 days)
**Dependencies:** None

**Description:**
- Implement Targets page to display active sell order targets
- Show target prices (EMA9) for open positions
- Display current price and distance to target
- Support both paper trading and broker trading modes

**Current State:**
- ✅ Targets page exists (`web/src/routes/dashboard/TargetsPage.tsx`)
- ❌ Targets endpoint is placeholder (returns empty list)
- ❌ Target prices exist in system but not exposed via API
- ✅ Paper trading: Targets stored in `active_sell_orders.json`
- ✅ Broker trading: Targets can be derived from positions or calculated from EMA9

**Deliverables:**
- [ ] Targets API endpoint implementation (`/api/v1/user/targets`)
- [ ] Query targets from appropriate source:
  - Paper trading: Read from `active_sell_orders.json`
  - Broker trading: Derive from positions or calculate EMA9 for open positions
- [ ] Return target information:
  - Symbol
  - Target price (EMA9)
  - Current price
  - Distance to target (percentage)
  - Entry price (from position)
  - Quantity
- [ ] Update Targets page UI to display data
- [ ] Add current price fetching (broker API or yfinance)
- [ ] Add distance to target calculation
- [ ] Loading states and error handling
- [ ] Mobile-responsive design

**Acceptance Criteria:**
- Targets page displays active targets correctly
- Target prices are accurate (EMA9 values)
- Current prices update correctly
- Distance to target calculated accurately
- Works for both paper and broker trading modes
- Fast loading (< 2 seconds)
- Mobile-responsive

**Files to Create/Modify:**
- `server/app/routers/targets.py` - Implement targets endpoint (currently placeholder)
- `web/src/routes/dashboard/TargetsPage.tsx` - Update to display target data
- `web/src/api/targets.ts` - Verify API client works
- `server/app/services/targets_service.py` - New service for target calculation (optional)

**API Requirements:**
- Endpoint: `GET /api/v1/user/targets`
- Response: List of target items with:
  - `id`: Target ID (or position ID)
  - `symbol`: Stock symbol
  - `target_price`: EMA9 target price
  - `current_price`: Current market price
  - `entry_price`: Average entry price (from position)
  - `quantity`: Position quantity
  - `distance_to_target`: Percentage distance to target
  - `note`: Optional note/description
  - `created_at`: When target was set

**Implementation Details:**

1. **For Paper Trading:**
   - Read `active_sell_orders.json` from user's paper trading directory
   - Extract target prices from sell orders
   - Get current prices from yfinance or stored prices
   - Calculate distance to target

2. **For Broker Trading:**
   - Option A: Query open positions from `positions` table
   - Calculate EMA9 for each position symbol
   - Get current prices from broker API
   - Calculate distance to target
   - Option B: Query active sell orders from broker API (if available)
   - Extract target prices from sell orders

3. **Target Calculation:**
   - Use existing EMA9 calculation logic from `sell_engine.py`
   - Reuse `calculate_ema9()` function or similar
   - Ensure consistency with sell order targets

**Integration Points:**
- Standalone feature providing immediate value
- Can be enhanced in future with manual target creation
- Supports Phase 4.1 (Performance Analytics) - target achievement metrics

**Testing Requirements:**
- Unit tests for target calculation
- Integration tests for targets API
- Test with both paper and broker trading modes
- Test with empty targets (no open positions)
- E2E tests for Targets page

**Future Enhancements (Not in v26.1.1):**
- Manual target creation/editing
- Target alerts (notify when target reached)
- Target history tracking
- Multiple targets per symbol
- Target achievement statistics

---

### Phase 3: Data Export & Reporting (High Priority)

#### 3.1 Complete CSV Export UI
**Priority:** 🔴 High
**Effort:** Low (2-3 days)
**Dependencies:** None

**Description:**
- Connect existing backend CSV export to web UI
- Add export buttons on relevant pages
- Support date range selection
- Add progress indicators for large exports

**Current State:**
- ✅ Backend CSV export exists (`core/csv_exporter.py`)
- ✅ Backend CSV export for paper trading reports
- ❌ No UI export buttons
- ❌ No API endpoints for CSV export from web UI
- ❌ No date range selection

**Deliverables:**
- [ ] CSV export API endpoints for:
  - P&L data
  - Trade history
  - Signals data
  - Orders
  - Portfolio holdings
- [ ] Export button component
- [ ] Date range picker for exports
- [ ] Progress indicator for large exports
- [ ] Error handling and user feedback
- [ ] Export buttons on:
  - P&L page
  - Paper Trading History page
  - Broker Trading History page
  - Orders page
  - Buying Zone (Signals) page
  - Portfolio page

**Acceptance Criteria:**
- Exports complete within 5 seconds for < 1000 records
- CSV format is correct and importable
- All relevant data fields included
- Works on all browsers
- User-friendly error messages

**Files to Create/Modify:**
- `server/app/routers/export.py` - New export router
- `web/src/components/ExportButton.tsx` - Reusable export button
- `web/src/routes/dashboard/PnlPage.tsx` - Add export button
- `web/src/routes/dashboard/PaperTradingHistoryPage.tsx` - Add export button
- `web/src/routes/dashboard/OrdersPage.tsx` - Add export button
- `web/src/routes/dashboard/BuyingZonePage.tsx` - Add export button
- `web/src/api/export.ts` - Export API functions

**Backend Integration:**
- Leverage existing `core/csv_exporter.py`
- Create service layer for export operations
- Add proper error handling and validation

---

#### 3.2 PDF Report Generation
**Priority:** 🟡 Medium
**Effort:** Medium (4-5 days)
**Dependencies:** 3.1 (CSV Export), 2.1 (P&L Chart), 2.2 (Portfolio Chart)

**Description:**
- Generate PDF reports for P&L
- Daily/weekly/monthly summary reports
- Include charts in PDF
- Professional formatting

**Deliverables:**
- [ ] Install PDF generation library (e.g., `reportlab` or `weasyprint`)
- [ ] PDF report templates
- [ ] Chart rendering in PDF (convert charts to images)
- [ ] Report generation API endpoint
- [ ] Download functionality
- [ ] Report types:
  - Daily P&L report
  - Weekly summary report
  - Monthly summary report
  - Custom date range report

**Acceptance Criteria:**
- PDFs generate within 10 seconds
- Charts render correctly in PDF
- Professional formatting
- All data accurate
- Downloadable files

**Files to Create/Modify:**
- `server/app/routers/reports.py` - New reports router
- `server/app/services/pdf_generator.py` - PDF generation service
- `server/app/templates/reports/` - PDF templates
- `web/src/routes/dashboard/PnlPage.tsx` - Add PDF export option
- `web/src/api/reports.ts` - Reports API functions

**Dependencies to Add:**
- `reportlab` or `weasyprint` for Python backend
- Chart-to-image conversion utility

---

### Phase 4: Advanced Analytics (Medium Priority)

#### 4.1 Performance Analytics Page
**Priority:** 🟡 Medium
**Effort:** High (5-7 days)
**Dependencies:** 1.1 (Chart Library), 2.1 (P&L Chart), 1.2 (PnL Data Population Service)

**Description:**
- Comprehensive performance metrics page
- Win rate analysis with charts
- Average profit/loss per trade
- Best/worst trades
- Trade duration analysis
- Strategy performance breakdown
- Can use broker trade history as data source for analytics (from Phase 2.4)
- **Note:** Requires P&L data to be populated (from 1.2)

**Current State:**
- ✅ Backend performance analyzer exists (`backtest/performance_analyzer.py`)
- ❌ No frontend analytics page
- ❌ No performance metrics API for web UI

**Deliverables:**
- [ ] New analytics page route (`/dashboard/analytics`)
- [ ] Performance metrics API endpoints
- [ ] Win rate chart (pie or bar chart)
- [ ] Profit/loss distribution chart
- [ ] Trade duration histogram
- [ ] Best/worst trades table
- [ ] Strategy performance breakdown
- [ ] Filtering options (date range, strategy type)
- [ ] Export functionality (CSV, PDF)

**Acceptance Criteria:**
- All metrics calculate correctly
- Charts render properly
- Fast page load (< 3 seconds)
- Mobile-responsive
- Accurate data

**Files to Create/Modify:**
- `server/app/routers/analytics.py` - New analytics router
- `server/app/services/analytics_service.py` - Analytics calculation service
- `web/src/routes/dashboard/AnalyticsPage.tsx` - New analytics page
- `web/src/components/charts/WinRateChart.tsx` - Win rate visualization
- `web/src/components/charts/ProfitLossDistribution.tsx` - Distribution chart
- `web/src/api/analytics.ts` - Analytics API functions
- `web/src/router.tsx` - Add analytics route

**Backend Integration:**
- Leverage existing `backtest/performance_analyzer.py` logic
- Adapt for live trading data
- Create service layer for analytics calculations

---

#### 4.2 Risk Metrics Dashboard
**Priority:** 🟢 Low
**Effort:** Medium (3-4 days)
**Dependencies:** 4.1 (Performance Analytics)

**Description:**
- Risk metrics calculations and visualization
- Sharpe ratio calculation
- Maximum drawdown
- Volatility metrics
- Risk-reward ratios
- Position concentration analysis

**Current State:**
- ✅ Some risk metrics calculated in backtest analyzer
- ❌ No UI dashboard for risk metrics
- ❌ No real-time risk metrics for live trading

**Deliverables:**
- [ ] Risk metrics calculation API
- [ ] Risk metrics section in analytics page
- [ ] Sharpe ratio display
- [ ] Maximum drawdown chart
- [ ] Volatility metrics visualization
- [ ] Risk-reward ratio chart
- [ ] Position concentration chart
- [ ] Historical risk trends

**Acceptance Criteria:**
- Metrics calculate accurately
- Visual indicators are clear
- Historical data available
- Mobile-responsive

**Files to Create/Modify:**
- `server/app/routers/analytics.py` - Add risk metrics endpoints
- `server/app/services/risk_metrics_service.py` - Risk calculations
- `web/src/routes/dashboard/AnalyticsPage.tsx` - Add risk metrics section
- `web/src/components/charts/RiskMetricsChart.tsx` - Risk visualization

---

### Phase 5: Watchlist Management (Medium Priority)

#### 5.1 Watchlist Feature
**Priority:** 🟡 Medium
**Effort:** Medium (4-5 days)
**Dependencies:** None

**Description:**
- Create/manage custom watchlists
- Add/remove stocks from watchlists
- View watchlist stocks on dashboard
- Quick access to watchlist stocks

**Deliverables:**
- [ ] Watchlist database model (Alembic migration)
- [ ] Watchlist API endpoints (CRUD operations)
- [ ] Watchlist management UI page
- [ ] Add/remove stocks functionality
- [ ] Multiple watchlists support
- [ ] Watchlist persistence

**Acceptance Criteria:**
- Users can create multiple watchlists
- Stocks can be added/removed easily
- Watchlist persists across sessions
- Mobile-friendly interface

**Files to Create/Modify:**
- `src/infrastructure/db/models.py` - Add Watchlist and WatchlistItem models
- `alembic/versions/XXXX_add_watchlist.py` - Database migration
- `server/app/routers/watchlist.py` - Watchlist API router
- `web/src/routes/dashboard/WatchlistPage.tsx` - Watchlist management page
- `web/src/api/watchlist.ts` - Watchlist API functions
- `web/src/router.tsx` - Add watchlist route

**Database Schema:**
```python
class Watchlist(Base):
    id: int
    user_id: int
    name: str
    created_at: datetime
    updated_at: datetime

class WatchlistItem(Base):
    id: int
    watchlist_id: int
    symbol: str
    added_at: datetime
```

---

#### 5.2 Watchlist Dashboard Widget
**Priority:** 🟡 Medium
**Effort:** Low (1-2 days)
**Dependencies:** 5.1 (Watchlist Feature)

**Description:**
- Display watchlist stocks on dashboard
- Show current price and change
- Quick link to buying zone for each stock
- Color-coded price changes

**Deliverables:**
- [ ] Watchlist widget component
- [ ] Price display (if available from API)
- [ ] Quick action buttons
- [ ] Responsive design
- [ ] Integration with dashboard home

**Acceptance Criteria:**
- Widget loads quickly
- Prices update (if real-time available)
- Easy navigation to stock details
- Mobile-responsive

**Files to Create/Modify:**
- `web/src/components/WatchlistWidget.tsx` - Widget component
- `web/src/routes/dashboard/DashboardHome.tsx` - Add widget
- `web/src/api/watchlist.ts` - Add widget data API

---

### Phase 6: User Experience Improvements (Low Priority)

#### 6.1 Complete Saved Filters & Preferences
**Priority:** 🟢 Low
**Effort:** Low (2-3 days)
**Dependencies:** None

**Description:**
- Complete saved filters implementation
- Save filter presets for signals
- Save column preferences
- Remember date range preferences

**Current State:**
- ✅ `ui_preferences` field exists in `UserSettings` model
- ✅ `SettingsRepository.get_ui_preferences()` method exists
- ✅ API endpoint for UI preferences exists
- ❌ No implementation of saved filter presets
- ❌ No implementation of column preferences persistence
- ❌ No implementation of date range preferences

**Deliverables:**
- [ ] Filter preset storage in `ui_preferences`
- [ ] Save/load filter presets UI
- [ ] Column preferences persistence
- [ ] Date range preferences persistence
- [ ] Auto-restore preferences on page load
- [ ] Preset management UI

**Acceptance Criteria:**
- Preferences save correctly
- Restore on page load
- Multiple presets supported
- Works across all filterable pages

**Files to Create/Modify:**
- `web/src/hooks/useSavedFilters.ts` - Custom hook for filter persistence
- `web/src/routes/dashboard/BuyingZonePage.tsx` - Add filter persistence
- `web/src/routes/dashboard/OrdersPage.tsx` - Add filter persistence
- `web/src/api/settings.ts` - Add preferences update functions
- `server/app/routers/user.py` - Verify preferences API works

---

## 🗓️ Timeline & Milestones

### Milestone 1: Foundation & Charts (Week 1-2)
- ✅ Install chart library
- ✅ PnL Data Population Service
- ✅ P&L Trend Chart
- ✅ Portfolio Value Chart
- ✅ Broker Trading History
- ✅ Targets Page Implementation
- **Target:** End of Week 2

### Milestone 2: Dashboard & Export (Week 2-3)
- ✅ Complete Enhanced Dashboard Metrics
- ✅ Complete CSV Export UI
- **Target:** End of Week 3

### Milestone 3: Reports & Analytics (Week 3-4)
- ✅ PDF Report Generation
- ✅ Performance Analytics Page
- **Target:** End of Week 4

### Milestone 4: Advanced Features (Week 4-5)
- ✅ Risk Metrics Dashboard
- ✅ Watchlist Feature
- ✅ Watchlist Dashboard Widget
- **Target:** End of Week 5

### Milestone 5: UX Polish (Week 5-6)
- ✅ Complete Saved Filters
- ✅ Final testing and bug fixes
- **Target:** End of Week 6

**Total Estimated Duration:** 6 weeks

---

## 🧪 Testing Strategy

### Unit Tests
- [ ] Chart components
- [ ] Export utilities
- [ ] PnL calculation service logic
- [ ] Realized vs unrealized P&L calculations
- [ ] Target calculation and distance metrics
- [ ] Broker trading history FIFO matching algorithm
- [ ] Broker trading history statistics calculations
- [ ] Analytics calculations
- [ ] Watchlist API
- [ ] Filter persistence logic

### Integration Tests
- [ ] Export workflows
- [ ] Chart data rendering
- [ ] PnL calculation service integration
- [ ] Targets API endpoint
- [ ] P&L data population workflow
- [ ] Broker trading history API endpoint
- [ ] Watchlist operations
- [ ] Dashboard data loading
- [ ] Analytics API endpoints

### E2E Tests
- [ ] Complete export flow (CSV and PDF)
- [ ] P&L page data display (after population)
- [ ] Targets page data display
- [ ] Broker trading history page navigation and data display
- [ ] Watchlist creation and management
- [ ] Chart interactions
- [ ] Filter persistence
- [ ] Analytics page navigation

### Performance Tests
- [ ] Chart rendering performance
- [ ] Large data export performance
- [ ] Dashboard load time
- [ ] Analytics page load time
- [ ] Mobile page load time

---

## 📊 Success Metrics

### User Engagement
- Dashboard page views increase by 30%
- Average session time increases by 20%
- Export feature usage > 50% of active users
- Analytics page views > 40% of active users

### Performance
- Dashboard loads in < 2 seconds
- Charts render in < 1 second
- Export completes in < 5 seconds for typical datasets
- Analytics page loads in < 3 seconds

### Quality
- Zero critical bugs in production
- < 1% error rate on new features
- 95%+ test coverage for new code
- All acceptance criteria met

---

## 🚀 Deployment Plan

### Pre-Release
1. Complete all features
2. Full test suite passes
3. Code review completed
4. Documentation updated
5. Performance benchmarks met
6. Security review completed

### Release
1. Deploy to staging environment
2. Smoke testing
3. User acceptance testing (if applicable)
4. Deploy to production
5. Monitor for issues

### Post-Release
1. Monitor error rates
2. Collect user feedback
3. Track usage metrics
4. Plan hotfixes if needed

---

## 📝 Documentation Updates

- [ ] Update user guide with new features
- [ ] Add API documentation for new endpoints
- [ ] Update dashboard screenshots
- [ ] Create feature documentation for:
  - Chart usage guide
  - Export functionality guide
  - Analytics page guide
  - Watchlist management guide
- [ ] Update changelog
- [ ] Create release notes

---

## 🔄 Rollback Plan

If critical issues are found:
1. Revert to version 26.1.0
2. Investigate issues
3. Fix and re-test
4. Re-deploy

---

## 📋 Dependencies & Prerequisites

### New Dependencies Required

**Frontend:**
- `recharts` - Chart library for React

**Backend:**
- `reportlab` or `weasyprint` - PDF generation (for Phase 3.2)
- `Pillow` - Image processing for chart-to-PDF conversion (if needed)

### Database Migrations
- Watchlist tables (Phase 5.1)

### API Endpoints to Create
- Historical portfolio data endpoint
- Metrics endpoints (win rate, average profit, best/worst trades)
- P&L calculation endpoints (`POST /api/v1/user/pnl/calculate`, `POST /api/v1/user/pnl/backfill`)
- Targets endpoint (`GET /api/v1/user/targets` - implement existing placeholder)
- Broker trading history endpoint (`/api/v1/user/broker/history`)
- Export endpoints (CSV for various data types)
- PDF report generation endpoint
- Analytics endpoints
- Risk metrics endpoints
- Watchlist CRUD endpoints

---

## 🎯 Future Considerations (Not in v26.1.1)

### UI/UX Features
- WebSocket real-time updates for charts
- Advanced portfolio analytics
- Social features
- Mobile app
- Price alerts for watchlist
- Email delivery for PDF reports

### Infrastructure & Backend
- **Unified DB-Only Storage**: Migrate from hybrid storage (paper=file, real=DB) to unified DB-only approach
  - 📄 **Implementation Plan**: [`../kotak_neo_trader/UNIFIED_DB_IMPLEMENTATION_COMPLETE.md`](../kotak_neo_trader/UNIFIED_DB_IMPLEMENTATION_COMPLETE.md)
  - **Timeline**: 6-8 weeks
  - **Benefits**: Single codebase, consistency, unified reporting, data integrity
  - **Status**: Planning phase
- **Order-Position Reconciliation Job**: Background job to reconcile ONGOING orders for closed positions
  - **Purpose**: Catch any missed order closures when positions are closed (edge case handling)
  - **Implementation**: Periodic job that queries for closed positions with ONGOING buy orders and updates them to CLOSED
  - **Frequency**: Run daily (e.g., during EOD cleanup) or on-demand
  - **Benefits**: Ensures data consistency, handles edge cases where order closure fails after position closure
  - **Timeline**: 1-2 days
  - **Status**: Future improvement
  - **Related Issue**: Fixed in current release - positions now close buy orders, but this provides additional safety net
- Advanced order management
- Multi-broker support

---

## 📋 Implementation Checklist

### Development
- [ ] All features implemented
- [ ] Code reviewed
- [ ] Tests written and passing
- [ ] Performance optimized
- [ ] Security reviewed
- [ ] Accessibility checked

### Testing
- [ ] Unit tests complete
- [ ] Integration tests complete
- [ ] E2E tests complete
- [ ] Manual testing complete
- [ ] Mobile testing complete
- [ ] Performance testing complete

### Documentation
- [ ] User guide updated
- [ ] API docs updated
- [ ] Changelog updated
- [ ] Release notes prepared
- [ ] Feature documentation created

### Deployment
- [ ] Staging deployment successful
- [ ] Production deployment plan ready
- [ ] Rollback plan ready
- [ ] Monitoring configured
- [ ] Database migrations tested

---

## 👥 Team Assignments (if applicable)

- **Frontend Development:** Charts, Export UI, Analytics Page, Watchlist UI
- **Backend Development:** APIs, Export logic, Analytics calculations, Watchlist backend
- **Testing:** All test types
- **DevOps:** Deployment, Monitoring
- **Documentation:** User guides, API docs

---

## 📞 Support & Feedback

- Create GitHub issues for bugs
- Feature requests via GitHub discussions
- User feedback collection mechanism

---

**Last Updated:** 2025-12-04
**Next Review:** Weekly during development
