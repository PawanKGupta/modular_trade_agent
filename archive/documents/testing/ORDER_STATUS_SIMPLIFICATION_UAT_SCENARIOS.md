# Order Status Simplification - UAT Test Scenarios

## Overview

This document provides User Acceptance Testing (UAT) scenarios for the order status simplification changes. These scenarios should be tested by stakeholders before production deployment.

**UAT Date**: TBD
**UAT Participants**: Product Owner, QA Team, End Users
**UAT Duration**: 1-2 days

---

## UAT Test Scenarios

### Scenario 1: Order Placement Flow

**Objective**: Verify that new buy orders are created with the correct status and reason.

**Steps**:
1. Navigate to Trading Configuration page
2. Configure buy order settings
3. Trigger buy order service
4. Navigate to Orders page
5. Check "Pending" tab

**Expected Results**:
- ✅ Order appears in "Pending" tab (not "AMO" tab)
- ✅ Order status is `pending`
- ✅ Order reason is "Order placed - waiting for market open"
- ✅ Order side is `buy`
- ✅ Order details (symbol, quantity, price) are correct

**Status**: ⏳ Pending UAT

---

### Scenario 2: Order Execution Flow

**Objective**: Verify that executed orders transition correctly to "Ongoing" status.

**Steps**:
1. Place a buy order (see Scenario 1)
2. Wait for order execution (or manually trigger execution)
3. Navigate to Orders page
4. Check "Ongoing" tab

**Expected Results**:
- ✅ Order appears in "Ongoing" tab
- ✅ Order status is `ongoing`
- ✅ Order reason is "Order executed at Rs X.XX"
- ✅ Execution price and quantity are displayed
- ✅ Execution time is recorded

**Status**: ⏳ Pending UAT

---

### Scenario 3: Order Failure Flow

**Objective**: Verify that failed orders are handled correctly with unified status.

**Steps**:
1. Place a buy order with insufficient balance (or trigger failure)
2. Navigate to Orders page
3. Check "Failed" tab

**Expected Results**:
- ✅ Order appears in "Failed" tab (not separate "Retry Pending" or "Rejected" tabs)
- ✅ Order status is `failed`
- ✅ Order reason describes the failure (e.g., "Insufficient balance")
- ✅ Retry count is displayed
- ✅ First failed at timestamp is displayed
- ✅ Last retry attempt timestamp is displayed

**Status**: ⏳ Pending UAT

---

### Scenario 4: Order Retry Flow

**Objective**: Verify that failed orders can be retried manually.

**Steps**:
1. Navigate to Orders page
2. Go to "Failed" tab
3. Click "Retry" button on a failed order
4. Confirm retry action
5. Observe order status

**Expected Results**:
- ✅ Retry button is visible for failed orders
- ✅ Retry confirmation dialog appears
- ✅ After retry, order status remains `failed` (until successful)
- ✅ Retry count increments
- ✅ Last retry attempt timestamp updates
- ✅ Order appears in "Pending" tab if retry succeeds

**Status**: ⏳ Pending UAT

---

### Scenario 5: Order Expiry Flow

**Objective**: Verify that expired orders are automatically marked as cancelled.

**Steps**:
1. Create a failed order
2. Set `first_failed_at` to more than 1 day ago (or wait)
3. Run retry job (or wait for scheduled retry)
4. Navigate to Orders page
5. Check "Cancelled" tab

**Expected Results**:
- ✅ Expired order is automatically marked as `cancelled`
- ✅ Order appears in "Cancelled" tab
- ✅ Order reason indicates expiry (e.g., "Order expired - past next trading day market close")
- ✅ Expired order is not retriable

**Status**: ⏳ Pending UAT

---

### Scenario 6: Sell Order Flow

**Objective**: Verify that sell orders use `side='sell'` instead of `SELL` status.

**Steps**:
1. Place a sell order (via sell engine or manual trigger)
2. Navigate to Orders page
3. Check "Pending" tab
4. Filter orders by side (if filter available)

**Expected Results**:
- ✅ Sell order appears in "Pending" tab (not separate "Sell" tab)
- ✅ Order status is `pending`
- ✅ Order side is `sell`
- ✅ Order reason describes sell action (e.g., "Sell order placed at EMA9 target")
- ✅ Sell orders can be distinguished from buy orders using `side` column

**Status**: ⏳ Pending UAT

---

### Scenario 7: Order Status Filtering

**Objective**: Verify that order status filtering works correctly with new statuses.

**Steps**:
1. Navigate to Orders page
2. Click each tab: Pending, Ongoing, Failed, Closed, Cancelled
3. Verify orders appear in correct tabs
4. Test API filtering (if applicable)

**Expected Results**:
- ✅ "Pending" tab shows orders with `status='pending'` (merged AMO + PENDING_EXECUTION)
- ✅ "Ongoing" tab shows orders with `status='ongoing'`
- ✅ "Failed" tab shows orders with `status='failed'` (merged FAILED + RETRY_PENDING + REJECTED)
- ✅ "Closed" tab shows orders with `status='closed'`
- ✅ "Cancelled" tab shows orders with `status='cancelled'`
- ✅ No orders appear in wrong tabs
- ✅ Old status tabs (AMO, Pending Execution, Sell, Retry Pending, Rejected) are removed

**Status**: ⏳ Pending UAT

---

### Scenario 8: Reason Field Display

**Objective**: Verify that the unified reason field displays correctly.

**Steps**:
1. Navigate to Orders page
2. Check "Failed" tab
3. Verify reason column displays failure reasons
4. Check other tabs for reason display

**Expected Results**:
- ✅ Reason field is displayed in Failed tab
- ✅ Reason text is readable and descriptive
- ✅ Reason field shows appropriate message for each status:
  - Pending: "Order placed - waiting for market open"
  - Ongoing: "Order executed at Rs X.XX"
  - Failed: Failure reason (e.g., "Insufficient balance")
  - Closed: "Order completed"
  - Cancelled: Cancellation reason

**Status**: ⏳ Pending UAT

---

### Scenario 9: API Endpoint Testing

**Objective**: Verify that API endpoints work correctly with new statuses.

**Steps**:
1. Test `GET /api/v1/user/orders?status=pending`
2. Test `GET /api/v1/user/orders?status=failed`
3. Test `GET /api/v1/user/orders?status=ongoing`
4. Test `GET /api/v1/user/orders?status=closed`
5. Test `GET /api/v1/user/orders?status=cancelled`
6. Test `POST /api/v1/user/orders/{id}/retry`
7. Test `DELETE /api/v1/user/orders/{id}`

**Expected Results**:
- ✅ All status filters work correctly
- ✅ API returns orders with correct status
- ✅ API returns unified `reason` field
- ✅ Retry endpoint works for failed orders
- ✅ Drop endpoint works for failed orders
- ✅ API response times are acceptable (< 500ms)

**Status**: ⏳ Pending UAT

---

### Scenario 10: Weekend/Holiday Expiry Handling

**Objective**: Verify that expiry calculation correctly skips weekends.

**Steps**:
1. Create a failed order on Friday
2. Verify expiry calculation (should be Monday 3:30 PM)
3. Create a failed order on Saturday
4. Verify expiry calculation (should be Monday 3:30 PM)
5. Create a failed order on Sunday
6. Verify expiry calculation (should be Monday 3:30 PM)

**Expected Results**:
- ✅ Friday failures expire on Monday (skip weekend)
- ✅ Saturday failures expire on Monday (skip Sunday)
- ✅ Sunday failures expire on Monday
- ✅ Expiry time is 3:30 PM IST (market close)

**Status**: ⏳ Pending UAT

---

### Scenario 11: Retry Count Tracking

**Objective**: Verify that retry count increments correctly.

**Steps**:
1. Create a failed order
2. Verify initial retry count is 0 or 1
3. Retry the order manually
4. Verify retry count increments
5. Retry again
6. Verify retry count increments again

**Expected Results**:
- ✅ Retry count starts at appropriate value (0 or 1)
- ✅ Retry count increments on each retry attempt
- ✅ Retry count is displayed in UI
- ✅ Retry count is tracked correctly in database

**Status**: ⏳ Pending UAT

---

### Scenario 12: Legacy Data Compatibility

**Objective**: Verify that legacy orders with old statuses are handled correctly.

**Steps**:
1. Check database for orders with old statuses (if any exist)
2. Run migration script
3. Verify old statuses are migrated correctly
4. Verify reason fields are populated from legacy fields

**Expected Results**:
- ✅ Old statuses (AMO, PENDING_EXECUTION, RETRY_PENDING, REJECTED, SELL) are migrated
- ✅ Legacy reason fields (failure_reason, rejection_reason, cancelled_reason) are migrated to unified `reason` field
- ✅ No data loss during migration
- ✅ Migrated orders display correctly in UI

**Status**: ⏳ Pending UAT (if legacy data exists)

---

## UAT Checklist

### Functional Testing
- [ ] Scenario 1: Order Placement Flow
- [ ] Scenario 2: Order Execution Flow
- [ ] Scenario 3: Order Failure Flow
- [ ] Scenario 4: Order Retry Flow
- [ ] Scenario 5: Order Expiry Flow
- [ ] Scenario 6: Sell Order Flow
- [ ] Scenario 7: Order Status Filtering
- [ ] Scenario 8: Reason Field Display
- [ ] Scenario 9: API Endpoint Testing
- [ ] Scenario 10: Weekend/Holiday Expiry Handling
- [ ] Scenario 11: Retry Count Tracking
- [ ] Scenario 12: Legacy Data Compatibility

### Non-Functional Testing
- [ ] Performance is acceptable
- [ ] UI is responsive
- [ ] Error messages are clear
- [ ] User experience is maintained/improved

### Regression Testing
- [ ] Existing features still work
- [ ] No breaking changes for users
- [ ] Backward compatibility maintained

---

## UAT Sign-off

**UAT Completed By**: _________________

**Date**: _________________

**Sign-off**: ☐ Approved  ☐ Rejected

**Comments**:
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

---

## Issues Found During UAT

| Issue # | Description | Severity | Status | Assigned To |
|---------|-------------|----------|--------|-------------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

---

**Last Updated**: November 23, 2025
**Status**: ⏳ Pending UAT Execution
