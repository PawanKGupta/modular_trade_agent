# Order Status Simplification - Performance Testing

## Overview

This document outlines performance testing for the order status simplification changes. The goal is to ensure that the changes do not degrade system performance.

**Test Date**: TBD
**Baseline**: Before order status simplification
**Target**: After order status simplification

---

## Performance Test Scenarios

### 1. Database Query Performance

#### 1.1 Order Status Distribution Query

**Query**:
```sql
SELECT status, COUNT(*) as count
FROM orders
WHERE user_id = :user_id
GROUP BY status
ORDER BY count DESC;
```

**Test**:
- Run query 100 times
- Measure average, min, max, p95, p99 response times
- Compare with baseline

**Target**: < 100ms (p95)

**Status**: ⏳ Pending

---

#### 1.2 Get Retriable Failed Orders Query

**Query**:
```sql
-- Simplified query (uses get_retriable_failed_orders method)
SELECT * FROM orders
WHERE user_id = :user_id
  AND status = 'failed'
  AND (first_failed_at IS NULL OR first_failed_at > :expiry_time)
```

**Test**:
- Run query with varying numbers of failed orders (10, 100, 1000)
- Measure query execution time
- Test with expired vs non-expired orders
- Compare with baseline (old RETRY_PENDING query)

**Target**: < 200ms (p95) for 1000 orders

**Status**: ⏳ Pending

---

#### 1.3 Order List Query with Status Filter

**Query**:
```sql
SELECT * FROM orders
WHERE user_id = :user_id
  AND status = :status
ORDER BY created_at DESC
LIMIT 100;
```

**Test**:
- Test with each new status: `pending`, `ongoing`, `failed`, `closed`, `cancelled`
- Test with large datasets (1000+ orders)
- Measure query execution time
- Compare with baseline (old status queries)

**Target**: < 150ms (p95)

**Status**: ⏳ Pending

---

#### 1.4 Reason Field Query Performance

**Query**:
```sql
SELECT * FROM orders
WHERE user_id = :user_id
  AND reason LIKE :pattern;
```

**Test**:
- Test reason field filtering
- Measure query execution time
- Compare with baseline (old failure_reason queries)

**Target**: < 200ms (p95)

**Status**: ⏳ Pending

---

### 2. API Response Times

#### 2.1 GET /api/v1/user/orders

**Endpoint**: `GET /api/v1/user/orders?status={status}`

**Test Scenarios**:
- Test with each status: `pending`, `ongoing`, `failed`, `closed`, `cancelled`
- Test with date filters
- Test with reason filters
- Test with no filters (all orders)

**Load Test**:
- 100 concurrent requests
- Measure response times (p50, p95, p99)
- Monitor error rates

**Target**:
- p95 < 500ms
- p99 < 1s
- Error rate < 0.1%

**Status**: ⏳ Pending

---

#### 2.2 POST /api/v1/user/orders/{id}/retry

**Endpoint**: `POST /api/v1/user/orders/{id}/retry`

**Test Scenarios**:
- Retry single order
- Retry multiple orders sequentially
- Retry with expired order (should be cancelled)

**Load Test**:
- 50 concurrent retry requests
- Measure response times
- Monitor success/failure rates

**Target**:
- p95 < 300ms
- Success rate > 95%

**Status**: ⏳ Pending

---

#### 2.3 DELETE /api/v1/user/orders/{id}

**Endpoint**: `DELETE /api/v1/user/orders/{id}`

**Test Scenarios**:
- Drop single order
- Drop multiple orders sequentially

**Load Test**:
- 50 concurrent drop requests
- Measure response times

**Target**:
- p95 < 200ms
- Success rate > 95%

**Status**: ⏳ Pending

---

### 3. Frontend Rendering Performance

#### 3.1 OrdersPage Rendering

**Component**: `web/src/routes/dashboard/OrdersPage.tsx`

**Test Scenarios**:
- Render with 10 orders
- Render with 100 orders
- Render with 1000 orders
- Switch between tabs (pending, ongoing, failed, closed, cancelled)
- Filter by reason
- Filter by date range

**Metrics**:
- Initial render time
- Tab switch time
- Filter application time
- Memory usage

**Target**:
- Initial render < 500ms (for 100 orders)
- Tab switch < 200ms
- Filter application < 300ms

**Status**: ⏳ Pending

---

#### 3.2 Order Table Rendering

**Component**: Order table in OrdersPage

**Test Scenarios**:
- Render table with different column counts
- Render with long reason text
- Render with many retry attempts

**Metrics**:
- Table render time
- Scroll performance
- Memory usage

**Target**:
- Table render < 300ms (for 100 rows)
- Smooth scrolling (60fps)

**Status**: ⏳ Pending

---

### 4. Expiry Calculation Performance

#### 4.1 get_next_trading_day_close() Performance

**Function**: `modules/kotak_neo_auto_trader/utils/trading_day_utils.py`

**Test Scenarios**:
- Calculate for weekday failures
- Calculate for Friday failures (weekend skip)
- Calculate for Saturday/Sunday failures
- Calculate for 1000 orders in batch

**Metrics**:
- Function execution time
- Memory usage

**Target**:
- Single calculation < 1ms
- Batch of 1000 < 100ms

**Status**: ⏳ Pending

---

#### 4.2 get_retriable_failed_orders() Performance

**Method**: `OrdersRepository.get_retriable_failed_orders()`

**Test Scenarios**:
- Test with 10 failed orders
- Test with 100 failed orders
- Test with 1000 failed orders
- Test with mix of expired and non-expired orders

**Metrics**:
- Method execution time
- Database query time
- Expiry calculation time

**Target**:
- < 200ms for 100 orders
- < 500ms for 1000 orders

**Status**: ⏳ Pending

---

## Performance Test Results

### Database Query Performance

| Query | Baseline (ms) | After Changes (ms) | Change | Status |
|-------|---------------|-------------------|--------|--------|
| Status distribution | TBD | TBD | TBD | ⏳ Pending |
| Retriable failed orders | TBD | TBD | TBD | ⏳ Pending |
| Order list with status filter | TBD | TBD | TBD | ⏳ Pending |
| Reason field filter | TBD | TBD | TBD | ⏳ Pending |

### API Response Times

| Endpoint | Baseline (ms) | After Changes (ms) | Change | Status |
|----------|---------------|-------------------|--------|--------|
| GET /api/v1/user/orders | TBD | TBD | TBD | ⏳ Pending |
| POST /api/v1/user/orders/{id}/retry | TBD | TBD | TBD | ⏳ Pending |
| DELETE /api/v1/user/orders/{id} | TBD | TBD | TBD | ⏳ Pending |

### Frontend Rendering Performance

| Component | Baseline (ms) | After Changes (ms) | Change | Status |
|-----------|---------------|-------------------|--------|--------|
| OrdersPage initial render | TBD | TBD | TBD | ⏳ Pending |
| Tab switch | TBD | TBD | TBD | ⏳ Pending |
| Filter application | TBD | TBD | TBD | ⏳ Pending |

### Expiry Calculation Performance

| Function | Baseline (ms) | After Changes (ms) | Change | Status |
|----------|---------------|-------------------|--------|--------|
| get_next_trading_day_close() | TBD | TBD | TBD | ⏳ Pending |
| get_retriable_failed_orders() | TBD | TBD | TBD | ⏳ Pending |

---

## Performance Test Scripts

### Database Query Performance Test

```python
# scripts/performance_test_order_status_queries.py
import time
from src.infrastructure.persistence.orders_repository import OrdersRepository

def test_status_distribution_performance(repo: OrdersRepository, user_id: int, iterations: int = 100):
    """Test status distribution query performance"""
    times = []
    for _ in range(iterations):
        start = time.time()
        repo.get_order_status_distribution(user_id)
        times.append((time.time() - start) * 1000)  # Convert to ms

    avg = sum(times) / len(times)
    p95 = sorted(times)[int(len(times) * 0.95)]
    p99 = sorted(times)[int(len(times) * 0.99)]

    return {
        "avg": avg,
        "min": min(times),
        "max": max(times),
        "p95": p95,
        "p99": p99
    }

def test_retriable_orders_performance(repo: OrdersRepository, user_id: int, iterations: int = 100):
    """Test retriable failed orders query performance"""
    times = []
    for _ in range(iterations):
        start = time.time()
        repo.get_retriable_failed_orders(user_id)
        times.append((time.time() - start) * 1000)

    return {
        "avg": sum(times) / len(times),
        "min": min(times),
        "max": max(times),
        "p95": sorted(times)[int(len(times) * 0.95)],
        "p99": sorted(times)[int(len(times) * 0.99)]
    }
```

### API Performance Test

```bash
# scripts/performance_test_api.sh
# Test API endpoints with Apache Bench or similar

# Test GET /api/v1/user/orders
ab -n 1000 -c 10 -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/user/orders?status=pending"

# Test POST /api/v1/user/orders/{id}/retry
ab -n 500 -c 10 -p retry.json -T application/json \
  -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/user/orders/1/retry"
```

---

## Performance Acceptance Criteria

### ✅ Acceptable Performance

- All database queries meet target response times
- All API endpoints meet target response times
- Frontend rendering meets target times
- No significant performance degradation compared to baseline
- Memory usage within acceptable limits

### ❌ Performance Issues

If any of the following occur:
- Query time > 2x baseline
- API response time > 2x baseline
- Frontend render time > 2x baseline
- Memory usage > 2x baseline
- Error rate > 1%

**Action**: Investigate and optimize before production deployment

---

## Performance Optimization Recommendations

### If Performance Issues Detected

1. **Database Optimization**:
   - Add indexes on `status` column if needed
   - Add indexes on `reason` column if filtering frequently
   - Optimize `get_retriable_failed_orders()` query

2. **API Optimization**:
   - Add response caching for status distribution
   - Implement pagination for large order lists
   - Optimize serialization

3. **Frontend Optimization**:
   - Implement virtual scrolling for large order lists
   - Add memoization for expensive calculations
   - Optimize re-renders

---

## Notes

- Performance testing should be done on staging environment with production-like data
- Baseline measurements should be taken before order status simplification changes
- All performance tests should be documented with actual results
- Performance regression should be investigated before production deployment

---

**Last Updated**: November 23, 2025
**Status**: ⏳ Pending Execution
