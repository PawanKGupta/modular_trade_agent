# Broker Trading History API - Quick Reference Guide

## API Endpoint

**Base URL:** `http://localhost:8000/api/v1/user/broker/history`

## Authentication

All requests require a valid JWT Bearer token in the `Authorization` header:
```
Authorization: Bearer <your_jwt_token>
```

## Request Parameters

| Parameter | Type | Required | Default | Range | Description |
|-----------|------|----------|---------|-------|-------------|
| `from_date` | string | No | - | ISO format | Start date for filtering (e.g., "2025-01-01T00:00:00") |
| `to_date` | string | No | - | ISO format | End date for filtering (e.g., "2025-12-31T23:59:59") |
| `raw` | boolean | No | false | true/false | If true, returns only transactions without FIFO matching |
| `limit` | integer | No | 1000 | 1-10000 | Maximum number of transactions to return |

## Request Examples

### Basic Request (All transactions with FIFO matching)
```bash
curl -X GET "http://localhost:8000/api/v1/user/broker/history" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### With Date Range
```bash
curl -X GET "http://localhost:8000/api/v1/user/broker/history?from_date=2025-01-01T00:00:00&to_date=2025-12-31T23:59:59" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Raw Mode (Transactions Only)
```bash
curl -X GET "http://localhost:8000/api/v1/user/broker/history?raw=true" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Limited Results
```bash
curl -X GET "http://localhost:8000/api/v1/user/broker/history?limit=100" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Response Format

### Success Response (200 OK)
```json
{
  "transactions": [
    {
      "order_id": "ORD-001",
      "symbol": "AAPL",
      "transaction_type": "BUY",
      "quantity": 100,
      "price": 150.00,
      "order_value": 15000.00,
      "charges": 0.0,
      "timestamp": "2025-01-15T10:30:00"
    },
    {
      "order_id": "ORD-002",
      "symbol": "AAPL",
      "transaction_type": "SELL",
      "quantity": 80,
      "price": 155.00,
      "order_value": 12400.00,
      "charges": 0.0,
      "timestamp": "2025-01-20T14:15:00"
    }
  ],
  "closed_positions": [
    {
      "symbol": "AAPL",
      "quantity": 80,
      "entry_price": 150.00,
      "exit_price": 155.00,
      "buy_date": "2025-01-15T10:30:00",
      "sell_date": "2025-01-20T14:15:00",
      "holding_days": 5,
      "realized_pnl": 400.00,
      "pnl_percentage": 3.33,
      "charges": 0.0
    }
  ],
  "statistics": {
    "total_trades": 1,
    "profitable_trades": 1,
    "losing_trades": 0,
    "breakeven_trades": 0,
    "win_rate": 100.0,
    "total_profit": 400.00,
    "total_loss": 0.0,
    "net_pnl": 400.00,
    "avg_profit_per_trade": 400.00,
    "avg_loss_per_trade": 0.0
  }
}
```

### Error Response (400 Bad Request)
```json
{
  "detail": "Broker history is only available in broker mode. Current mode: paper"
}
```

### Error Response (404 Not Found)
```json
{
  "detail": "User settings not found. Please configure your account."
}
```

## Response Schema

### Transaction Object
| Field | Type | Description |
|-------|------|-------------|
| order_id | string | Unique order identifier |
| symbol | string | Trading symbol (e.g., "AAPL", "GOOGL") |
| transaction_type | string | "BUY" or "SELL" |
| quantity | integer | Number of shares |
| price | float | Execution price per share |
| order_value | float | quantity × price |
| charges | float | Trading charges (fees, commissions) |
| timestamp | string | ISO format timestamp |

### ClosedPosition Object
| Field | Type | Description |
|-------|------|-------------|
| symbol | string | Trading symbol |
| quantity | integer | Number of shares in position |
| entry_price | float | Average entry price |
| exit_price | float | Average exit price |
| buy_date | string | Date position was opened |
| sell_date | string | Date position was closed |
| holding_days | integer | Number of days held |
| realized_pnl | float | Profit/Loss in currency |
| pnl_percentage | float | Profit/Loss percentage |
| charges | float | Trading charges (fees, commissions) |

### Statistics Object
| Field | Type | Description |
|-------|------|-------------|
| total_trades | integer | Total closed positions |
| profitable_trades | integer | Number of winning trades |
| losing_trades | integer | Number of losing trades |
| breakeven_trades | integer | Number of breakeven trades |
| win_rate | float | Percentage of winning trades (0-100) |
| total_profit | float | Sum of all profits |
| total_loss | float | Sum of all losses |
| net_pnl | float | total_profit + total_loss |
| avg_profit_per_trade | float | average profitable trade P&L |
| avg_loss_per_trade | float | average losing trade P&L |

## FIFO Matching Logic

The endpoint uses First-In-First-Out (FIFO) matching to calculate closed positions:

1. **Per-Symbol Tracking:** Each symbol is tracked independently
2. **Chronological Order:** Transactions are matched in chronological order (oldest first)
3. **Automatic Matching:** Buy orders create inventory; sell orders consume inventory oldest-first
4. **Partial Fills:** Sell orders can consume parts of multiple buy orders
5. **P&L Calculation:** Profit/Loss = (exit_price - entry_price) × quantity

### Example FIFO Scenario
```
Transaction 1: Buy 100 AAPL @ $150  → Inventory: [100@$150]
Transaction 2: Buy 50 AAPL @ $152   → Inventory: [100@$150, 50@$152]
Transaction 3: Sell 80 AAPL @ $155  → Match: 80 from first lot
                                      → Closed: 80@$150→$155 = +$400
                                      → Inventory: [20@$150, 50@$152]
```

## Filtering Examples

### Get Last 7 Days of Trading
```python
from datetime import datetime, timedelta

now = datetime.now()
week_ago = now - timedelta(days=7)

params = {
    "from_date": week_ago.isoformat(),
    "to_date": now.isoformat()
}
```

### Get Only January 2025 Trading
```python
params = {
    "from_date": "2025-01-01T00:00:00",
    "to_date": "2025-01-31T23:59:59"
}
```

### Get Top 50 Most Recent Transactions
```python
params = {
    "limit": 50
}
```

## Status Codes

| Code | Meaning | When |
|------|---------|------|
| 200 | OK | Successfully retrieved trading history |
| 400 | Bad Request | Not in broker mode or invalid date format |
| 404 | Not Found | User settings not found |
| 500 | Server Error | Unexpected server error |

## Error Handling

### Common Errors

**"Broker history is only available in broker mode"**
- Solution: Switch to broker mode in user settings before calling this endpoint

**"User settings not found"**
- Solution: Complete account setup and broker configuration

**Invalid date format**
- Use ISO format: "YYYY-MM-DDTHH:MM:SS"
- Example: "2025-01-15T14:30:00"

**Limit out of range**
- Limit must be between 1 and 10000
- Default is 1000

## Frontend Integration

### React Example
```typescript
import { useQuery } from '@tanstack/react-query';
import { getBrokerHistory } from '@/api/broker';

export function BrokerTradingHistoryPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['brokerHistory'],
    queryFn: () => getBrokerHistory(),
  });

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;
  if (!data) return <div>No data</div>;

  return (
    <div>
      <h2>Broker Trading History</h2>
      <p>Total Trades: {data.statistics.total_trades}</p>
      <p>Win Rate: {data.statistics.win_rate.toFixed(2)}%</p>
      <p>Net P&L: ${data.statistics.net_pnl.toFixed(2)}</p>

      <h3>Transactions ({data.transactions.length})</h3>
      {data.transactions.map(tx => (
        <div key={tx.order_id}>
          {tx.symbol} {tx.transaction_type} {tx.quantity} @ {tx.price}
        </div>
      ))}

      <h3>Closed Positions ({data.closed_positions.length})</h3>
      {data.closed_positions.map((cp, idx) => (
        <div key={idx}>
          {cp.symbol}: {cp.quantity} shares, P&L: ${cp.realized_pnl}
        </div>
      ))}
    </div>
  );
}
```

## Performance Notes

- **Typical Response Time:** 100-500ms (depending on dataset size)
- **Max Transactions:** 10,000 per request
- **Caching:** Recommended to cache results for 60+ seconds
- **Large Datasets:** For 1000+ transactions, consider pagination

## Rate Limiting

- No explicit rate limiting implemented
- Recommended: Don't exceed 1 request per second per user

## API Documentation

Full OpenAPI/Swagger documentation available at:
```
http://localhost:8000/docs
```

## Support

For issues or questions:
1. Check the test files in `tests/unit/phase2/test_broker_e2e_integration.py`
2. Review FIFO algorithm in `server/app/routers/broker_history_impl.py`
3. Check response schemas in `server/app/routers/paper_trading.py`
