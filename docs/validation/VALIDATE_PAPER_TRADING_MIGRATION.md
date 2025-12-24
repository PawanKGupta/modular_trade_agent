# How to Validate Paper Trading Migration in UI

This guide explains how to verify that paper trading data has been successfully migrated from files to the database.

## Quick Validation Steps

### 1. Check Orders Page in UI

1. **Open the web application** (usually `http://localhost:8000` or your server URL)
2. **Navigate to Orders page** (from the dashboard menu)
3. **Check for migrated orders:**
   - You should see 10 orders for User 1
   - These orders were migrated from `paper_trading/user_1/orders.json`
   - Orders should show symbols like: APOLLOHOSP, TATASTEEL, etc.

### 2. Check Portfolio/Holdings

1. **Navigate to Portfolio or Broker Portfolio page**
2. **Verify positions:**
   - You should see 6 open positions
   - These correspond to holdings from `paper_trading/user_1/holdings.json`

### 3. Verify via API (Direct Check)

You can also verify directly via API calls:

#### Check Paper Trading Orders
```bash
# Get all orders (should include paper trading orders)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/user/orders/

# Filter by checking response - paper trading orders should have:
# - orig_source: "paper_trading"
# - trade_mode: "paper" (if field is added)
```

#### Check Paper Trading Positions
```bash
# Check positions via portfolio endpoint
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/user/broker/portfolio
```

### 4. Database Query (Advanced)

If you have database access:

```sql
-- Count paper trading orders
SELECT COUNT(*) FROM orders
WHERE trade_mode = 'paper';

-- Expected: 10 orders for User 1

-- Count paper trading positions
SELECT COUNT(*) FROM positions p
WHERE EXISTS (
  SELECT 1 FROM orders o
  WHERE o.user_id = p.user_id
    AND o.symbol = p.symbol
    AND o.trade_mode = 'paper'
    AND o.side = 'buy'
);

-- Expected: 6 positions for User 1
```

## What to Look For

### ✅ Success Indicators:
- **Orders Page**: Shows 10 orders with symbols from paper trading
- **Portfolio Page**: Shows 6 open positions
- **Order Details**: Orders have `orig_source: "paper_trading"` (check via API)
- **No Errors**: UI loads without errors

### ⚠️ Warning Signs:
- **Missing Orders**: If you see fewer than 10 orders, some may not have migrated
- **Missing Positions**: If you see fewer than 6 positions, check holdings migration
- **Empty Pages**: If pages are empty, migration may not have completed

## Troubleshooting

### If orders don't appear:
1. Check if user is logged in as User 1
2. Verify migration completed successfully (check migration script output)
3. Check database directly (see SQL queries above)

### If positions don't appear:
1. Verify holdings.json was migrated
2. Check if positions are linked to orders correctly
3. Ensure positions have `closed_at IS NULL` (open positions)

## Next Steps

After validation:
- ✅ Paper trading data is now in database
- ✅ System will use database for future paper trading operations
- ✅ Original files remain as backup (can be archived)
- ✅ You can now use unified reporting across paper and broker trading
