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
- P&L Trend Chart with time ranges
- Portfolio Value Chart with historical data

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
- 📄 **Implementation Plan**: [`documents/kotak_neo_trader/UNIFIED_DB_IMPLEMENTATION_COMPLETE.md`](../documents/kotak_neo_trader/UNIFIED_DB_IMPLEMENTATION_COMPLETE.md)
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

### Phase 2: Core Dashboard Enhancements (High Priority)

#### 2.1 P&L Trend Chart
**Priority:** 🔴 High
**Effort:** Medium (3-5 days)
**Dependencies:** 1.1 (Chart Library)

**Description:**
- Add interactive line chart showing P&L over time
- Support multiple time ranges (7 days, 30 days, 90 days, 1 year)
- Show realized vs unrealized P&L separately
- Display key milestones (best day, worst day, break-even points)

**Current State:**
- ✅ P&L API endpoints exist (`/api/v1/user/pnl/daily`, `/api/v1/user/pnl/summary`)
- ✅ P&L Page exists (`web/src/routes/dashboard/PnlPage.tsx`)
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
**Dependencies:** None

**Description:**
- Complete missing dashboard metrics
- Win rate percentage
- Average profit per trade
- Best/worst trade
- Ensure all metrics are accurate and performant

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
**Dependencies:** 1.1 (Chart Library), 2.1 (P&L Chart)

**Description:**
- Comprehensive performance metrics page
- Win rate analysis with charts
- Average profit/loss per trade
- Best/worst trades
- Trade duration analysis
- Strategy performance breakdown

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
- ✅ P&L Trend Chart
- ✅ Portfolio Value Chart
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
- [ ] Analytics calculations
- [ ] Watchlist API
- [ ] Filter persistence logic

### Integration Tests
- [ ] Export workflows
- [ ] Chart data rendering
- [ ] Watchlist operations
- [ ] Dashboard data loading
- [ ] Analytics API endpoints

### E2E Tests
- [ ] Complete export flow (CSV and PDF)
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
  - 📄 **Implementation Plan**: [`documents/kotak_neo_trader/UNIFIED_DB_IMPLEMENTATION_COMPLETE.md`](../documents/kotak_neo_trader/UNIFIED_DB_IMPLEMENTATION_COMPLETE.md)
  - **Timeline**: 6-8 weeks
  - **Benefits**: Single codebase, consistency, unified reporting, data integrity
  - **Status**: Planning phase
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
