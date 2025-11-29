# Order Status Simplification - Monitoring Guide

## Overview

This document provides monitoring guidelines for the order status simplification deployment. Use this guide to monitor system health, detect issues, and ensure smooth operation after deployment.

---

## Key Metrics to Monitor

### 1. Order Status Distribution

**What to Monitor**: Distribution of orders across the 5 simplified statuses

**Query**:
```sql
SELECT
    status,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM orders
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY status
ORDER BY count DESC;
```

**Expected Distribution** (typical):
- `pending`: 10-30%
- `ongoing`: 5-15%
- `closed`: 40-60%
- `failed`: 5-15%
- `cancelled`: 1-5%

**Alert Threshold**:
- If `failed` > 30% → Investigate
- If `pending` > 50% → Check order processing

---

### 2. Order Placement Success Rate

**What to Monitor**: Percentage of orders successfully placed

**Query**:
```sql
SELECT
    COUNT(*) FILTER (WHERE status IN ('pending', 'ongoing', 'closed')) * 100.0 / COUNT(*) as success_rate,
    COUNT(*) FILTER (WHERE status = 'failed') * 100.0 / COUNT(*) as failure_rate,
    COUNT(*) as total_orders
FROM orders
WHERE created_at > NOW() - INTERVAL '1 hour';
```

**Expected**: Success rate > 80%

**Alert Threshold**:
- Success rate < 70% → Critical alert
- Success rate < 80% → Warning

---

### 3. Retry Logic Performance

**What to Monitor**: Failed orders eligible for retry vs expired

**Query**:
```sql
-- Retriable orders (not expired)
SELECT COUNT(*) as retriable_orders
FROM orders
WHERE status = 'failed'
  AND first_failed_at IS NOT NULL
  AND first_failed_at > NOW() - INTERVAL '1 day';

-- Expired orders (should be cancelled)
SELECT COUNT(*) as expired_orders
FROM orders
WHERE status = 'failed'
  AND first_failed_at IS NOT NULL
  AND first_failed_at < NOW() - INTERVAL '1 day';
```

**Expected**:
- Expired orders should be automatically marked as `cancelled`
- Retriable orders should be < 10% of total failed orders

**Alert Threshold**:
- Expired orders not being cancelled → Investigate expiry logic
- Retriable orders > 20% of failed → Check retry mechanism

---

### 4. Reason Field Usage

**What to Monitor**: Unified reason field population

**Query**:
```sql
SELECT
    COUNT(*) as total_orders,
    COUNT(reason) as orders_with_reason,
    COUNT(*) FILTER (WHERE reason IS NULL) as orders_without_reason,
    ROUND(COUNT(reason) * 100.0 / COUNT(*), 2) as reason_population_rate
FROM orders
WHERE created_at > NOW() - INTERVAL '24 hours';
```

**Expected**: Reason population rate > 90%

**Alert Threshold**:
- Reason population rate < 80% → Investigate

---

### 5. Status Transition Times

**What to Monitor**: Time taken for status transitions

**Query**:
```sql
-- Pending to Ongoing (order execution time)
SELECT
    AVG(EXTRACT(EPOCH FROM (execution_time - placed_at))) as avg_execution_seconds,
    MAX(EXTRACT(EPOCH FROM (execution_time - placed_at))) as max_execution_seconds
FROM orders
WHERE status = 'ongoing'
  AND execution_time IS NOT NULL
  AND placed_at IS NOT NULL
  AND execution_time > NOW() - INTERVAL '24 hours';
```

**Expected**:
- Average execution time: < 5 minutes (for market orders)
- Max execution time: < 30 minutes

**Alert Threshold**:
- Average > 10 minutes → Investigate
- Max > 1 hour → Critical

---

### 6. API Response Times

**What to Monitor**: API endpoint performance

**Endpoints to Monitor**:
- `GET /api/v1/user/orders` - List orders
- `POST /api/v1/user/orders/{id}/retry` - Retry order
- `DELETE /api/v1/user/orders/{id}` - Drop order

**Expected**:
- Response time < 500ms (p95)
- Response time < 1s (p99)

**Alert Threshold**:
- p95 > 1s → Warning
- p99 > 2s → Critical

---

### 7. Error Rates

**What to Monitor**: Application and API error rates

**Query** (Application Logs):
```bash
# Count errors in last hour
grep -i "error\|exception\|failed" logs/application.log | \
  grep "$(date -d '1 hour ago' '+%Y-%m-%d %H')" | wc -l
```

**Query** (API Logs):
```bash
# Count 5xx errors in last hour
grep "HTTP/1.1 [5]" logs/api.log | \
  grep "$(date -d '1 hour ago' '+%Y-%m-%d %H')" | wc -l
```

**Expected**:
- Application errors: < 10 per hour
- API 5xx errors: < 1% of requests

**Alert Threshold**:
- Application errors > 50 per hour → Critical
- API 5xx errors > 5% → Critical

---

## Monitoring Dashboard Queries

### Real-Time Order Status

```sql
SELECT
    status,
    COUNT(*) as count,
    MAX(created_at) as latest_order
FROM orders
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY status
ORDER BY count DESC;
```

### Failed Orders by Reason

```sql
SELECT
    reason,
    COUNT(*) as count,
    AVG(retry_count) as avg_retry_count,
    MAX(retry_count) as max_retry_count
FROM orders
WHERE status = 'failed'
  AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY reason
ORDER BY count DESC
LIMIT 10;
```

### Order Processing Timeline

```sql
SELECT
    DATE_TRUNC('hour', created_at) as hour,
    status,
    COUNT(*) as count
FROM orders
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY hour, status
ORDER BY hour DESC, status;
```

### Retry Success Rate

```sql
SELECT
    COUNT(*) FILTER (WHERE status IN ('pending', 'ongoing', 'closed')) * 100.0 / COUNT(*) as retry_success_rate,
    COUNT(*) as total_retries
FROM orders
WHERE status IN ('pending', 'ongoing', 'closed', 'failed')
  AND retry_count > 0
  AND created_at > NOW() - INTERVAL '24 hours';
```

---

## Alert Configuration

### Critical Alerts (Immediate Action Required)

1. **Order Placement Completely Broken**
   - Condition: Success rate < 50% for 5 minutes
   - Action: Rollback immediately

2. **Data Loss Detected**
   - Condition: Order count drops unexpectedly
   - Action: Rollback and investigate

3. **Database Errors**
   - Condition: Database error rate > 10 per minute
   - Action: Check database health, consider rollback

4. **API Completely Down**
   - Condition: API availability < 90% for 5 minutes
   - Action: Check API server, consider rollback

### Warning Alerts (Investigate)

1. **High Failure Rate**
   - Condition: Failure rate > 20% for 15 minutes
   - Action: Investigate failure reasons

2. **Slow API Response**
   - Condition: p95 response time > 1s for 10 minutes
   - Action: Check API performance

3. **Expired Orders Not Cancelled**
   - Condition: Expired orders not being cancelled
   - Action: Check expiry logic

4. **High Retry Count**
   - Condition: Average retry_count > 3
   - Action: Investigate retry logic

---

## Daily Monitoring Checklist

### Morning (9:00 AM)
- [ ] Check overnight order status distribution
- [ ] Review error logs from previous night
- [ ] Check for any critical alerts
- [ ] Verify retry logic working correctly

### Midday (12:00 PM)
- [ ] Check order placement success rate
- [ ] Review API performance metrics
- [ ] Check for any warnings
- [ ] Verify expiry logic working correctly

### Evening (5:00 PM)
- [ ] Review daily metrics summary
- [ ] Check for any issues
- [ ] Verify all systems functioning
- [ ] Document any anomalies

---

## Weekly Monitoring Summary

### Metrics to Review Weekly

1. **Order Status Distribution** (weekly average)
2. **Order Placement Success Rate** (weekly average)
3. **Retry Success Rate** (weekly average)
4. **API Performance** (weekly p95, p99)
5. **Error Rates** (weekly total)
6. **User Feedback** (weekly summary)

### Weekly Report Template

```
Week of: [Date]

Order Status Distribution:
- Pending: X% (target: 10-30%)
- Ongoing: X% (target: 5-15%)
- Closed: X% (target: 40-60%)
- Failed: X% (target: 5-15%)
- Cancelled: X% (target: 1-5%)

Order Placement Success Rate: X% (target: >80%)
Retry Success Rate: X% (target: >50%)
API p95 Response Time: Xms (target: <500ms)
API p99 Response Time: Xms (target: <1s)

Issues:
- [List any issues encountered]

Actions Taken:
- [List actions taken]

Next Steps:
- [List next steps]
```

---

## Troubleshooting Guide

### Issue: High Failure Rate

**Symptoms**: Failure rate > 20%

**Investigation Steps**:
1. Check failure reasons distribution
2. Check broker API status
3. Check balance/portfolio limits
4. Review error logs

**Common Causes**:
- Broker API issues
- Insufficient balance
- Invalid order parameters
- Network issues

**Resolution**:
- If broker API: Wait for broker to resolve
- If balance: Check user capital settings
- If parameters: Review order creation logic
- If network: Check connectivity

---

### Issue: Expired Orders Not Cancelled

**Symptoms**: Orders with `first_failed_at` > 1 day ago still have status `failed`

**Investigation Steps**:
1. Check `get_retriable_failed_orders()` logic
2. Check `get_next_trading_day_close()` function
3. Check if retry job is running
4. Review expiry calculation

**Common Causes**:
- Retry job not running
- Expiry calculation incorrect
- Weekend/holiday handling issue
- Timezone mismatch

**Resolution**:
- Ensure retry job scheduled correctly
- Verify expiry calculation logic
- Check weekend/holiday handling
- Verify timezone settings

---

### Issue: API Slow Response

**Symptoms**: API response time > 1s

**Investigation Steps**:
1. Check database query performance
2. Check API server resources
3. Check network latency
4. Review API endpoint logic

**Common Causes**:
- Slow database queries
- High server load
- Network issues
- Inefficient API logic

**Resolution**:
- Optimize database queries
- Scale API server if needed
- Check network connectivity
- Review API code for optimizations

---

## Monitoring Tools

### Recommended Tools

1. **Application Logs**: `logs/application.log`
2. **API Logs**: `logs/api.log`
3. **Database Logs**: Database-specific logs
4. **Metrics Dashboard**: Custom dashboard (if available)
5. **Error Tracking**: Error tracking service (if configured)

### Log Locations

- Application logs: `logs/application.log`
- API logs: `logs/api.log`
- Database logs: Database-specific location
- Error logs: `logs/errors.log` (if configured)

---

## Support Contacts

- **Technical Lead**: [Name/Email]
- **Database Admin**: [Name/Email]
- **DevOps Engineer**: [Name/Email]
- **On-Call Engineer**: [Name/Phone]

---

**Last Updated**: November 23, 2025
**Version**: 1.0
