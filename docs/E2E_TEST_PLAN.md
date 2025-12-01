# End-to-End (E2E) Test Plan

Comprehensive E2E test plan for Rebound — Modular Trade Agent before test environment deployment.

## 📋 Test Coverage Overview

### Test Categories

1. **Authentication & Authorization** (5 test cases)
2. **Dashboard & Navigation** (4 test cases)
3. **Trading Features** (8 test cases)
4. **Settings & Configuration** (7 test cases)
5. **System & Monitoring** (6 test cases)
6. **Notifications** (5 test cases)
7. **Admin Features** (6 test cases)
8. **Error Handling & Edge Cases** (5 test cases)
9. **Data Integrity** (4 test cases)
10. **Performance & Load** (3 test cases)

**Total: 53 E2E test cases**

---

## 1. Authentication & Authorization

### 1.1 User Registration Flow
- **Test**: New user can sign up with valid credentials
- **Steps**:
  1. Navigate to signup page
  2. Fill in email, password, name
  3. Submit form
  4. Verify redirect to dashboard
  5. Verify user is logged in
- **Expected**: User created and logged in successfully

### 1.2 User Login Flow
- **Test**: Existing user can login with correct credentials
- **Steps**:
  1. Navigate to login page
  2. Enter valid email and password
  3. Submit form
  4. Verify redirect to dashboard
  5. Verify user session is active
- **Expected**: Successful login and session creation

### 1.3 Login Failure - Invalid Credentials
- **Test**: Login fails with incorrect password
- **Steps**:
  1. Navigate to login page
  2. Enter valid email and invalid password
  3. Submit form
  4. Verify error message displayed
  5. Verify user remains on login page
- **Expected**: Error message shown, no redirect

### 1.4 Session Persistence
- **Test**: User session persists after page refresh
- **Steps**:
  1. Login as user
  2. Navigate to dashboard
  3. Refresh page
  4. Verify still logged in
  5. Verify dashboard still accessible
- **Expected**: Session maintained after refresh

### 1.5 Logout Flow
- **Test**: User can logout and session is cleared
- **Steps**:
  1. Login as user
  2. Click logout button
  3. Verify redirect to login page
  4. Verify cannot access protected routes
  5. Verify token is cleared from storage
- **Expected**: Complete logout and session cleared

---

## 2. Dashboard & Navigation

### 2.1 Dashboard Overview Load
- **Test**: Dashboard loads with overview data
- **Steps**:
  1. Login as user
  2. Navigate to dashboard
  3. Verify dashboard page loads
  4. Verify key metrics are displayed
  5. Verify navigation menu is visible
- **Expected**: Dashboard renders correctly with data

### 2.2 Menu Navigation
- **Test**: All menu items are accessible and navigate correctly
- **Steps**:
  1. Login as user
  2. Click each menu item:
     - Dashboard
     - Buying Zone
     - Orders
     - Paper Trading
     - PnL
     - Targets
     - Service Status
     - Trading Config
     - Broker Settings
     - Notification Settings
     - System Logs
     - Activity Log
     - Notifications
  3. Verify each page loads correctly
  4. Verify active menu item is highlighted
- **Expected**: All menu items navigate to correct pages

### 2.3 Menu Expand/Collapse
- **Test**: Menu categories can be expanded and collapsed
- **Steps**:
  1. Login as user
  2. Click on "Trading" category header
  3. Verify sub-items are visible
  4. Click again to collapse
  5. Verify sub-items are hidden
  6. Verify state persists on refresh
- **Expected**: Expand/collapse works and persists

### 2.4 Responsive Navigation
- **Test**: Navigation works on mobile viewport
- **Steps**:
  1. Login as user
  2. Resize browser to mobile width (< 768px)
  3. Verify menu is accessible
  4. Navigate between pages
  5. Verify pages render correctly
- **Expected**: Navigation functional on mobile

---

## 3. Trading Features

### 3.1 Buying Zone Page Load
- **Test**: Buying Zone page loads and displays signals
- **Steps**:
  1. Login as user
  2. Navigate to Buying Zone
  3. Verify page loads
  4. Verify signals table is displayed
  5. Verify filters are available
- **Expected**: Buying Zone page displays signals

### 3.2 Buying Zone Filters
- **Test**: Filters work correctly (date, status)
- **Steps**:
  1. Navigate to Buying Zone
  2. Select date filter (Today)
  3. Verify results update
  4. Select status filter (Active)
  5. Verify results filtered correctly
- **Expected**: Filters apply correctly

### 3.3 Reject Signal
- **Test**: User can reject a buying signal
- **Steps**:
  1. Navigate to Buying Zone
  2. Click reject button on a signal
  3. Verify confirmation dialog (if any)
  4. Confirm rejection
  5. Verify signal status changes to "rejected"
  6. Verify signal removed from active list
- **Expected**: Signal rejected successfully

### 3.4 Orders Page Load
- **Test**: Orders page displays order list
- **Steps**:
  1. Navigate to Orders page
  2. Verify page loads
  3. Verify order tabs are visible (Pending, Ongoing, Failed, etc.)
  4. Verify orders are displayed in table
- **Expected**: Orders page displays correctly

### 3.5 Order Status Tabs
- **Test**: Order status tabs filter orders correctly
- **Steps**:
  1. Navigate to Orders page
  2. Click on "Pending" tab
  3. Verify only pending orders shown
  4. Click on "Ongoing" tab
  5. Verify only ongoing orders shown
  6. Repeat for all tabs
- **Expected**: Tabs filter orders correctly

### 3.6 Paper Trading Page
- **Test**: Paper Trading page loads and displays positions
- **Steps**:
  1. Navigate to Paper Trading
  2. Verify page loads
  3. Verify positions table is displayed
  4. Verify current portfolio value shown
- **Expected**: Paper Trading page displays positions

### 3.7 Paper Trading History
- **Test**: Trade History displays past trades
- **Steps**:
  1. Navigate to Paper Trading History
  2. Verify page loads
  3. Verify trade history table is displayed
  4. Verify trade details are shown
- **Expected**: Trade history displays correctly

### 3.8 PnL Page
- **Test**: PnL page displays profit/loss data
- **Steps**:
  1. Navigate to PnL page
  2. Verify page loads
  3. Verify daily PnL chart/table is displayed
  4. Verify summary statistics are shown
- **Expected**: PnL data displays correctly

---

## 4. Settings & Configuration

### 4.1 Trading Config Page Load
- **Test**: Trading Config page loads with current settings
- **Steps**:
  1. Navigate to Trading Config
  2. Verify page loads
  3. Verify all config sections are displayed
  4. Verify current values are pre-filled
- **Expected**: Config page loads with current settings

### 4.2 Update Trading Config
- **Test**: User can update trading configuration
- **Steps**:
  1. Navigate to Trading Config
  2. Change RSI period value
  3. Change user capital value
  4. Click Save
  5. Verify success message
  6. Refresh page and verify values persisted
- **Expected**: Config saved and persists

### 4.3 Reset Trading Config
- **Test**: User can reset config to defaults
- **Steps**:
  1. Navigate to Trading Config
  2. Modify some values
  3. Click Reset button
  4. Verify confirmation dialog
  5. Confirm reset
  6. Verify values reset to defaults
- **Expected**: Config resets to defaults

### 4.4 Broker Settings Page
- **Test**: Broker Settings page loads
- **Steps**:
  1. Navigate to Broker Settings
  2. Verify page loads
  3. Verify credential form is displayed
  4. Verify test connection button is visible
- **Expected**: Broker Settings page displays correctly

### 4.5 Save Broker Credentials
- **Test**: User can save broker credentials (test mode)
- **Steps**:
  1. Navigate to Broker Settings
  2. Fill in API key and secret (test values)
  3. Click Save
  4. Verify success message
  5. Verify credentials are stored (masked)
- **Expected**: Credentials saved securely

### 4.6 Test Broker Connection
- **Test**: User can test broker connection
- **Steps**:
  1. Navigate to Broker Settings
  2. Enter valid credentials
  3. Click "Test Connection"
  4. Verify loading state
  5. Verify connection result (success/failure)
- **Expected**: Connection test works

### 4.7 Notification Settings Page
- **Test**: Notification Settings page loads
- **Steps**:
  1. Navigate to Notification Settings
  2. Verify page loads
  3. Verify all preference sections are displayed
  4. Verify current preferences are shown
- **Expected**: Notification Settings page displays

---

## 5. System & Monitoring

### 5.1 Service Status Page
- **Test**: Service Status page displays service information
- **Steps**:
  1. Navigate to Service Status
  2. Verify page loads
  3. Verify service status indicators
  4. Verify last heartbeat time
  5. Verify service controls are visible
- **Expected**: Service status displays correctly

### 5.2 Start/Stop Service
- **Test**: User can start and stop trading service
- **Steps**:
  1. Navigate to Service Status
  2. Click "Start Service" button
  3. Verify confirmation dialog
  4. Confirm start
  5. Verify service status changes to "Running"
  6. Click "Stop Service"
  7. Verify service stops
- **Expected**: Service can be started and stopped

### 5.3 System Logs Page
- **Test**: System Logs page displays logs
- **Steps**:
  1. Navigate to System Logs
  2. Verify page loads
  3. Verify log table is displayed
  4. Verify log filters (level, module, date)
  5. Verify logs are displayed
- **Expected**: System logs display correctly

### 5.4 System Logs Filters
- **Test**: Log filters work correctly
- **Steps**:
  1. Navigate to System Logs
  2. Select log level filter (ERROR)
  3. Verify only ERROR logs shown
  4. Select module filter
  5. Verify logs filtered by module
  6. Select date range
  7. Verify logs filtered by date
- **Expected**: Filters work correctly

### 5.5 Activity Log Page
- **Test**: Activity Log page displays activity
- **Steps**:
  1. Navigate to Activity Log
  2. Verify page loads
  3. Verify activity table is displayed
  4. Verify activity filters are available
  5. Verify recent activities are shown
- **Expected**: Activity log displays correctly

### 5.6 Error Log Resolution
- **Test**: Admin can resolve error logs
- **Steps**:
  1. Login as admin
  2. Navigate to System Logs
  3. Switch to Error Logs tab
  4. Find an unresolved error
  5. Click "Resolve" button
  6. Add resolution notes
  7. Verify error marked as resolved
- **Expected**: Errors can be resolved

---

## 6. Notifications

### 6.1 Notifications Page Load
- **Test**: Notifications page displays notifications
- **Steps**:
  1. Navigate to Notifications
  2. Verify page loads
  3. Verify notification list is displayed
  4. Verify unread count badge
  5. Verify filters are available
- **Expected**: Notifications page displays correctly

### 6.2 Mark Notification as Read
- **Test**: User can mark notification as read
- **Steps**:
  1. Navigate to Notifications
  2. Find an unread notification
  3. Click "Mark Read" button
  4. Verify notification marked as read
  5. Verify unread count decreases
- **Expected**: Notification marked as read

### 6.3 Mark All Notifications as Read
- **Test**: User can mark all notifications as read
- **Steps**:
  1. Navigate to Notifications
  2. Verify multiple unread notifications
  3. Click "Mark All Read" button
  4. Verify all notifications marked as read
  5. Verify unread count is 0
- **Expected**: All notifications marked as read

### 6.4 Notification Filters
- **Test**: Notification filters work correctly
- **Steps**:
  1. Navigate to Notifications
  2. Select type filter (Service)
  3. Verify only service notifications shown
  4. Select level filter (Error)
  5. Verify only error notifications shown
- **Expected**: Filters work correctly

### 6.5 Notification Preferences Update
- **Test**: User can update notification preferences
- **Steps**:
  1. Navigate to Notification Settings
  2. Toggle "Notify Service Events" off
  3. Toggle "Notify Trading Events" on
  4. Click Save
  5. Verify success message
  6. Verify preferences saved
- **Expected**: Preferences updated successfully

---

## 7. Admin Features

### 7.1 Admin Users Page (Admin Only)
- **Test**: Admin can access Users management page
- **Steps**:
  1. Login as admin
  2. Navigate to Admin > Users
  3. Verify page loads
  4. Verify users table is displayed
  5. Verify user actions are visible
- **Expected**: Admin Users page accessible to admins only

### 7.2 Create New User (Admin)
- **Test**: Admin can create new user
- **Steps**:
  1. Login as admin
  2. Navigate to Admin > Users
  3. Click "Create User" button
  4. Fill in user details (email, name, role)
  5. Submit form
  6. Verify user created
  7. Verify user appears in list
- **Expected**: New user created successfully

### 7.3 Edit User (Admin)
- **Test**: Admin can edit user details
- **Steps**:
  1. Login as admin
  2. Navigate to Admin > Users
  3. Click edit on a user
  4. Change user name
  5. Save changes
  6. Verify changes saved
- **Expected**: User details updated

### 7.4 Deactivate User (Admin)
- **Test**: Admin can deactivate user
- **Steps**:
  1. Login as admin
  2. Navigate to Admin > Users
  3. Find active user
  4. Click deactivate button
  5. Confirm deactivation
  6. Verify user status changed
- **Expected**: User deactivated

### 7.5 ML Training Page (Admin)
- **Test**: Admin can access ML Training page
- **Steps**:
  1. Login as admin
  2. Navigate to Admin > ML Training
  3. Verify page loads
  4. Verify training jobs table
  5. Verify training form is visible
- **Expected**: ML Training page accessible

### 7.6 Start ML Training (Admin)
- **Test**: Admin can start ML model training
- **Steps**:
  1. Login as admin
  2. Navigate to ML Training
  3. Fill in training form (model type, algorithm)
  4. Click "Start Training"
  5. Verify training job created
  6. Verify job appears in jobs table
- **Expected**: ML training job started

---

## 8. Error Handling & Edge Cases

### 8.1 API Error Handling
- **Test**: Application handles API errors gracefully
- **Steps**:
  1. Login as user
  2. Stop API server
  3. Navigate to a page that requires API call
  4. Verify error message is displayed
  5. Verify application doesn't crash
  6. Restart API server
  7. Verify page loads correctly
- **Expected**: Errors handled gracefully

### 8.2 Network Timeout Handling
- **Test**: Application handles network timeouts
- **Steps**:
  1. Login as user
  2. Simulate slow network (throttle)
  3. Navigate to page with API calls
  4. Verify loading indicators shown
  5. Verify timeout handling
- **Expected**: Timeouts handled gracefully

### 8.3 Invalid Data Input
- **Test**: Application validates input and shows errors
- **Steps**:
  1. Navigate to Trading Config
  2. Enter invalid values (negative capital, etc.)
  3. Try to save
  4. Verify validation errors displayed
  5. Verify form doesn't submit
- **Expected**: Input validation works

### 8.4 Empty State Handling
- **Test**: Pages handle empty states correctly
- **Steps**:
  1. Login as new user with no data
  2. Navigate to Buying Zone
  3. Verify empty state message
  4. Navigate to Orders
  5. Verify empty state message
- **Expected**: Empty states displayed correctly

### 8.5 Concurrent User Actions
- **Test**: Application handles concurrent actions
- **Steps**:
  1. Login as user
  2. Open two browser tabs
  3. Make changes in both tabs
  4. Save in first tab
  5. Save in second tab
  6. Verify last change wins or conflict handled
- **Expected**: Concurrent actions handled correctly

---

## 9. Data Integrity

### 9.1 Data Persistence
- **Test**: Data persists after page refresh
- **Steps**:
  1. Login as user
  2. Make configuration changes
  3. Refresh page
  4. Verify changes persisted
- **Expected**: Data persists correctly

### 9.2 Cross-Page Data Consistency
- **Test**: Data is consistent across pages
- **Steps**:
  1. Navigate to Orders page
  2. Note order count
  3. Navigate to Dashboard
  4. Verify order count matches
  5. Navigate to PnL
  6. Verify related data is consistent
- **Expected**: Data consistent across pages

### 9.3 Data Isolation (Multi-User)
- **Test**: Users see only their own data
- **Steps**:
  1. Login as User A
  2. Note some data (orders, config)
  3. Logout
  4. Login as User B
  5. Verify User B doesn't see User A's data
  6. Verify data is isolated
- **Expected**: Data properly isolated

### 9.4 Data Refresh
- **Test**: Data refreshes correctly
- **Steps**:
  1. Navigate to Orders page
  2. Note current orders
  3. Wait for auto-refresh (if enabled)
  4. Verify new orders appear
  5. Manually refresh page
  6. Verify latest data shown
- **Expected**: Data refreshes correctly

---

## 10. Performance & Load

### 10.1 Page Load Performance
- **Test**: Pages load within acceptable time
- **Steps**:
  1. Login as user
  2. Measure time to load Dashboard (< 2s)
  3. Navigate to Buying Zone
  4. Measure load time (< 3s)
  5. Navigate to Orders
  6. Measure load time (< 2s)
- **Expected**: All pages load within 3 seconds

### 10.2 Large Dataset Handling
- **Test**: Pages handle large datasets
- **Steps**:
  1. Create/import large dataset (100+ orders)
  2. Navigate to Orders page
  3. Verify page loads
  4. Verify pagination or virtualization works
  5. Verify performance is acceptable
- **Expected**: Large datasets handled efficiently

### 10.3 Memory Leak Prevention
- **Test**: No memory leaks during extended use
- **Steps**:
  1. Login as user
  2. Navigate between pages repeatedly (50+ times)
  3. Monitor memory usage
  4. Verify no continuous memory increase
  5. Verify application remains responsive
- **Expected**: No memory leaks detected

---

## 🧪 Test Implementation

### Test Framework
- **Web UI**: Playwright (TypeScript)
- **API**: pytest with FastAPI TestClient
- **Database**: In-memory SQLite for tests

### Test Files Structure

```
web/tests/e2e/
├── auth.spec.ts              # Authentication tests
├── dashboard.spec.ts         # Dashboard and navigation
├── trading.spec.ts           # Trading features
├── settings.spec.ts          # Settings and configuration
├── system.spec.ts            # System and monitoring
├── notifications.spec.ts     # Notifications
├── admin.spec.ts             # Admin features
├── errors.spec.ts            # Error handling
├── data-integrity.spec.ts   # Data integrity
└── performance.spec.ts       # Performance tests

tests/e2e/                    # Backend E2E tests
├── test_auth_flow.py
├── test_trading_workflow.py
├── test_notification_flow.py
└── test_admin_workflow.py
```

### Running Tests

```bash
# Web E2E tests (Playwright)
cd web
npm run test:e2e

# Backend E2E tests (pytest)
pytest tests/e2e/ -v

# All E2E tests
npm run test:e2e && pytest tests/e2e/ -v
```

### CI/CD Integration

Tests run automatically in CI/CD pipeline before deployment to test environment.

---

## ✅ Test Completion Criteria

Before deploying to test environment:
- [ ] All 53 test cases implemented
- [ ] All tests passing locally
- [ ] Tests integrated into CI/CD
- [ ] Test documentation complete
- [ ] Coverage report generated (>80% E2E coverage)
- [ ] Performance benchmarks met
- [ ] All critical paths tested
- [ ] Test data cleanup verified

---

## 📊 Test Metrics

### Coverage Goals
- **Critical Paths**: 100% coverage
- **Major Features**: 95%+ coverage
- **Overall E2E**: 80%+ coverage

### Performance Benchmarks
- Page load time: < 3 seconds
- API response time: < 500ms
- Test execution time: < 10 minutes (all tests)

---

## 🔄 Test Maintenance

### Regular Updates
- Update tests when features change
- Add tests for new features
- Remove obsolete tests
- Update test data as needed

### Test Review
- Review test results weekly
- Identify flaky tests
- Optimize slow tests
- Maintain test documentation

---

## 📝 Notes

- Tests should be independent and isolated
- Use test fixtures for consistent setup
- Mock external services (broker APIs, Telegram, etc.)
- Clean up test data after each test
- Use meaningful test names
- Include clear assertions
- Document test dependencies
