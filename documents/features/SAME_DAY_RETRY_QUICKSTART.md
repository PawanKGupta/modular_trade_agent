# Pre-Market Retry Mechanism - Quick Reference

## Problem Solved
AMO orders that fail due to insufficient balance now automatically retry **until 9:15 AM next day** (before market opens) when you add funds.

## How It Works

### Timeline Example
```
Monday 4:05 PM  → Analysis runs, finds RELIANCE (RSI=28, strong buy)
                → Order fails: need ₹25,000, have ₹15,000
                → Order saved to retry queue
                → Telegram notification sent

Monday 7:00 PM  → You transfer ₹15,000 to trading account (after work)

Tuesday 8:00 AM → Scheduled retry task runs automatically
                → System retries RELIANCE order from yesterday
                → Balance now sufficient
                → Order placed successfully ✅
                → Will execute at 9:15 AM market open
                → Removed from retry queue
```

## Key Features

✅ **Retry until market open** - Orders valid until 9:15 AM next day (AMO orders execute at open anyway)  
✅ **Overnight window** - You have whole night to arrange funds  
✅ **8 AM automatic retry** - Scheduled task retries before market opens  
✅ **Smart** - Fetches fresh market data on each retry  
✅ **Safe** - Prevents duplicates and respects portfolio limits

## Manual Retry Command

After adding balance, run:
```powershell
python -m modules.kotak_neo_auto_trader.run_place_amo --env modules/kotak_neo_auto_trader/kotak_neo.env
```

## Notification Format

When order fails:
```
⚠️ Insufficient balance for RELIANCE AMO BUY.
Needed: ₹24,505 for 10 @ ₹2,450.50.
Available: ₹19,505. Shortfall: ₹5,000.

🔁 Order saved for retry until 9:15 AM tomorrow (before market opens).
Add balance & run script, or wait for 8 AM scheduled retry.
```

## Why Retry Until Market Open?

**AMO orders execute at market open anyway:**
- Placing AMO at 4 PM today = executes at 9:15 AM tomorrow
- Placing AMO at 8 AM tomorrow = also executes at 9:15 AM tomorrow
- **No difference in execution time!**

**Analysis from 4 PM yesterday is still valid at 8 AM:**
- Market closed since 3:30 PM - no new price action
- Technical indicators (RSI, EMA) unchanged
- Signal generated at 4 PM is still relevant at 8 AM

**Gives you overnight to arrange funds:**
- More realistic timeline to transfer money
- No rush to add balance same day
- Can add funds after work or next morning

## What Happens at Market Open?

```
Monday 4:05 PM   → Order fails, saved to queue
Tuesday 8:00 AM  → Retry task runs (you haven't added balance yet)
                 → Still insufficient funds
                 → Order remains in queue

Tuesday 9:15 AM  → Market opens
                 → Order expires and is deleted automatically
                 → Too late to place AMO for today's open
                 
Tuesday 4:05 PM  → Fresh analysis runs with new data
                 → New recommendations generated (if still valid)
```

## Scheduled Retry Times

Retry happens automatically at:
- **8:00 AM next day** (pre-market retry for yesterday's failed orders)
- **4:05 PM daily** (for same-day failed orders)
- **Manual run anytime** (immediate retry)

## Configuration

Failed orders are stored in: `trades_history.json`

```json
{
  "failed_orders": [
    {
      "symbol": "RELIANCE",
      "first_failed_at": "2025-10-27T16:05:00",
      "retry_count": 2,
      "shortfall": 5000,
      "reason": "insufficient_balance"
    }
  ]
}
```

## FAQ

**Q: Can I disable the 9:15 AM expiry?**  
A: Not recommended. Once market opens, the AMO window closes and yesterday's signals are outdated.

**Q: What if I add balance at 9:00 AM?**  
A: Run the script manually immediately! You have only 15 minutes before market opens at 9:15 AM.

**Q: Will it retry if market has already closed?**  
A: Yes, for AMO orders (After Market Orders) which execute next trading day at market open.

**Q: How many times will it retry same day?**  
A: Every time you run the script or scheduled task runs. No limit within the same day.

**Q: What if price moved a lot since the failed order?**  
A: Good question! The retry fetches FRESH indicators (RSI, EMA, price). So if conditions changed significantly, you can manually check before adding balance.

## Best Practices

1. **Act quickly** - Add balance within a few hours of notification
2. **Manual trigger** - After adding balance, run script immediately instead of waiting
3. **Monitor prices** - If price moved significantly, check if signal is still valid
4. **Maintain buffer** - Keep extra ₹10-20k in account to avoid balance issues

## Related Commands

```powershell
# Manual retry after adding balance
python -m modules.kotak_neo_auto_trader.run_place_amo --env modules/kotak_neo_auto_trader/kotak_neo.env

# Check current portfolio
python -m modules.kotak_neo_auto_trader.trader --positions

# View scheduled tasks
Get-ScheduledTask | Where-Object {$_.TaskName -like "TradingBot*"}
```
