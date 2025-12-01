# Kotak Neo Auto Trader - Re-entry Logic Details

## Overview

This document provides detailed explanations of three critical aspects of the Kotak Neo Auto Trader's re-entry logic:

1. **Reset Mechanism**: How RSI level tracking resets when RSI crosses above 30
2. **Daily Cap**: Maximum 1 re-entry per symbol per day
3. **Holdings Protection**: Skips re-entry if already in holdings

## 1. Reset Mechanism: RSI Level Tracking

### Purpose

The reset mechanism allows the system to re-enter positions after they recover. Without this, once all RSI levels (30, 20, 10) are used, the system would never re-enter that stock again.

### How It Works

**Location**: `modules/kotak_neo_auto_trader/auto_trade_engine.py` (lines 1519-1541)

#### Step 1: Track RSI Levels

Each position tracks which RSI levels have been used:
```python
levels = entries[0].get('levels_taken', {"30": True, "20": False, "10": False})
```

**Initial State** (after first entry):
- `levels_taken = {"30": True, "20": False, "10": False}`
- This means RSI < 30 level has been used (initial entry)
- RSI < 20 and RSI < 10 levels are still available

#### Step 2: Mark Reset Ready

When RSI crosses above 30:
```python
if rsi > 30:
    for e in entries:
        e['reset_ready'] = True
```

**What happens**:
- Position is marked as `reset_ready = True`
- This indicates the position has recovered above RSI 30
- The system is now ready to reset levels when RSI drops below 30 again

#### Step 3: Reset Levels on New Cycle

When RSI drops below 30 again (after being > 30):
```python
if rsi < 30 and any(e.get('reset_ready') for e in entries):
    # This is a NEW CYCLE - treat RSI<30 as a fresh reentry opportunity
    for e in entries:
        e['levels_taken'] = {"30": False, "20": False, "10": False}  # Reset all levels
        e['reset_ready'] = False
    levels = entries[0]['levels_taken']
    # Immediately trigger reentry at this RSI<30 level
    next_level = 30
```

**What happens**:
- All levels are reset: `{"30": False, "20": False, "10": False}`
- `reset_ready` is set to `False`
- System immediately triggers re-entry at RSI < 30 level
- This treats it as a **new cycle**, allowing fresh re-entries

#### Step 4: Normal Progression (if not reset)

If reset didn't happen, normal progression through levels:
```python
else:
    # Normal progression through levels
    next_level = None
    if levels.get('30') and not levels.get('20') and rsi < 20:
        next_level = 20  # Re-entry at RSI < 20
    if levels.get('20') and not levels.get('10') and rsi < 10:
        next_level = 10  # Re-entry at RSI < 10
```

### Example Scenario

**Day 1:**
- Entry at RSI 25 (< 30) → `levels_taken = {"30": True, "20": False, "10": False}`
- Position established

**Day 2:**
- RSI drops to 18 (< 20) → Re-entry at RSI < 20
- `levels_taken = {"30": True, "20": True, "10": False}`

**Day 3:**
- RSI drops to 8 (< 10) → Re-entry at RSI < 10
- `levels_taken = {"30": True, "20": True, "10": True}`
- All levels used

**Day 4:**
- RSI rises to 35 (> 30) → `reset_ready = True`
- No re-entry (RSI too high)

**Day 5:**
- RSI drops to 28 (< 30) → **RESET TRIGGERED**
- `levels_taken = {"30": False, "20": False, "10": False}` (all reset)
- Re-entry at RSI < 30 (new cycle)
- `levels_taken = {"30": True, "20": False, "10": False}` (after re-entry)

### Code Reference

```1521:1541:modules/kotak_neo_auto_trader/auto_trade_engine.py
levels = entries[0].get('levels_taken', {"30": True, "20": False, "10": False})
# Reset handling: if RSI>30, allow future cycles (but do not auto-clear past entries; apply for next re-entries)
if rsi > 30:
    for e in entries:
        e['reset_ready'] = True
# If reset_ready and rsi drops below 30 again, trigger NEW CYCLE reentry at RSI<30
if rsi < 30 and any(e.get('reset_ready') for e in entries):
    # This is a NEW CYCLE - treat RSI<30 as a fresh reentry opportunity
    for e in entries:
        e['levels_taken'] = {"30": False, "20": False, "10": False}  # Reset all levels
        e['reset_ready'] = False
    levels = entries[0]['levels_taken']
    # Immediately trigger reentry at this RSI<30 level
    next_level = 30
else:
    # Normal progression through levels
    next_level = None
    if levels.get('30') and not levels.get('20') and rsi < 20:
        next_level = 20
    if levels.get('20') and not levels.get('10') and rsi < 10:
        next_level = 10
```

## 2. Daily Cap: Maximum 1 Re-entry Per Symbol Per Day

### Purpose

Prevents excessive re-entries in a single day, which could:
- Increase risk exposure too quickly
- Consume too much capital in one day
- Create liquidity issues

### How It Works

**Location**: `modules/kotak_neo_auto_trader/auto_trade_engine.py` (lines 1543-1547, 820-847)

#### Implementation

Before placing a re-entry order, the system checks how many re-entries have already been made today:

```python
if next_level is not None:
    # Daily cap: allow max 1 re-entry per symbol per day
    if self.reentries_today(symbol) >= 1:
        logger.info(f"Re-entry daily cap reached for {symbol}; skipping today")
        continue
```

#### Counting Re-entries

The `reentries_today()` method counts re-entries from trade history:

```python
def reentries_today(self, base_symbol: str) -> int:
    """Count successful re-entries recorded today for this symbol (base symbol)."""
    try:
        hist = load_history(self.history_path)
        trades = hist.get('trades') or []
        today = datetime.now().date()
        cnt = 0
        for t in trades:
            if t.get('entry_type') != 'reentry':
                continue
            sym = str(t.get('symbol') or '').upper()
            if sym != base_symbol.upper():
                continue
            ts = t.get('entry_time')
            if not ts:
                continue
            try:
                d = datetime.fromisoformat(ts).date()
            except Exception:
                try:
                    d = datetime.strptime(ts.split('T')[0], '%Y-%m-%d').date()
                except Exception:
                    continue
            if d == today:
                cnt += 1
        return cnt
    except Exception:
        return 0
```

**How it works**:
1. Loads trade history from `data/trades_history.json`
2. Filters for trades with `entry_type == 'reentry'`
3. Filters for the specific symbol
4. Checks if `entry_time` is today
5. Returns count of re-entries made today

#### What Gets Counted

The `reentries_today()` method counts trades with:
- `entry_type == 'reentry'`
- `symbol` matches the symbol being checked
- `entry_time` is today's date

**Important Note**: There appears to be a discrepancy in the implementation:
- **Current re-entry recording** (lines 1626-1643): Re-entries are recorded by **updating the existing trade entry** - adding to the `reentries` array within the original trade entry and updating the total quantity.
- **Daily cap check** (line 1545): The `reentries_today()` method looks for **separate trade entries** with `entry_type == 'reentry'`.

This means the daily cap check may not work as intended if re-entries are only recorded in the `reentries` array. To fix this, the `reentries_today()` method should check the `reentries` array within existing trades:

```python
def reentries_today(self, base_symbol: str) -> int:
    """Count successful re-entries recorded today for this symbol."""
    try:
        hist = load_history(self.history_path)
        trades = hist.get('trades') or []
        today = datetime.now().date()
        cnt = 0
        for t in trades:
            sym = str(t.get('symbol') or '').upper()
            if sym != base_symbol.upper():
                continue
            # Check reentries array within the trade
            reentries = t.get('reentries', [])
            for reentry in reentries:
                reentry_time = reentry.get('time')
                if reentry_time:
                    try:
                        d = datetime.fromisoformat(reentry_time).date()
                        if d == today:
                            cnt += 1
                    except Exception:
                        continue
        return cnt
    except Exception:
        return 0
```

#### Example Scenario

**Day 1 (2024-01-15):**
- 9:00 AM: Initial entry at RSI 25
- 10:00 AM: Re-entry at RSI 18 → `reentries_today("RELIANCE") = 1`
- 11:00 AM: RSI drops to 8 → **SKIPPED** (daily cap reached)
- Result: Only 1 re-entry executed today

**Day 2 (2024-01-16):**
- 9:00 AM: RSI drops to 8 → Re-entry allowed (new day, cap reset)
- `reentries_today("RELIANCE") = 0` (no re-entries today yet)
- Result: Re-entry executed

### Code Reference

```1543:1547:modules/kotak_neo_auto_trader/auto_trade_engine.py
if next_level is not None:
    # Daily cap: allow max 1 re-entry per symbol per day
    if self.reentries_today(symbol) >= 1:
        logger.info(f"Re-entry daily cap reached for {symbol}; skipping today")
        continue
```

```820:847:modules/kotak_neo_auto_trader/auto_trade_engine.py
def reentries_today(self, base_symbol: str) -> int:
    """Count successful re-entries recorded today for this symbol (base symbol)."""
    try:
        hist = load_history(self.history_path)
        trades = hist.get('trades') or []
        today = datetime.now().date()
        cnt = 0
        for t in trades:
            if t.get('entry_type') != 'reentry':
                continue
            sym = str(t.get('symbol') or '').upper()
            if sym != base_symbol.upper():
                continue
            ts = t.get('entry_time')
            if not ts:
                continue
            try:
                d = datetime.fromisoformat(ts).date()
            except Exception:
                try:
                    d = datetime.strptime(ts.split('T')[0], '%Y-%m-%d').date()
                except Exception:
                    continue
            if d == today:
                cnt += 1
        return cnt
    except Exception:
        return 0
```

## 3. Holdings Protection: Skip if Already in Holdings

### Purpose

Prevents duplicate orders when:
- A previous order is already executed but not yet reflected in trade history
- A manual buy was made outside the system
- An order is pending execution

### How It Works

**Location**: `modules/kotak_neo_auto_trader/auto_trade_engine.py` (lines 1564-1567, 786-806)

#### Implementation

Before placing a re-entry order, the system checks if the symbol is already in holdings:

```python
if qty > 0:
    # Re-entry duplicate protection: holdings and active order
    if self.has_holding(symbol) or self.has_active_buy_order(symbol):
        logger.info(f"Re-entry skip {symbol}: already in holdings or pending order exists")
        continue
```

#### Checking Holdings

The `has_holding()` method checks broker holdings:

```python
def has_holding(self, base_symbol: str) -> bool:
    if not self.portfolio:
        return False
    variants = set(self._symbol_variants(base_symbol))
    h = self.portfolio.get_holdings() or {}
    
    # Check for 2FA gate - if detected, force re-login and retry once
    if self._response_requires_2fa(h) and hasattr(self.auth, 'force_relogin'):
        logger.info(f"2FA gate detected in holdings check, attempting re-login...")
        try:
            if self.auth.force_relogin():
                h = self.portfolio.get_holdings() or {}
                logger.debug(f"Holdings re-fetched after re-login")
        except Exception as e:
            logger.warning(f"Re-login failed during holdings check: {e}")
    
    for item in (h.get('data') or []):
        sym = str(item.get('tradingSymbol') or '').upper()
        if sym in variants:
            return True
    return False
```

#### Symbol Variants

The system checks multiple symbol variants to handle different formats:

```python
def _symbol_variants(base: str) -> List[str]:
    base = base.upper()
    return [base, f"{base}-EQ", f"{base}-BE", f"{base}-BL", f"{base}-BZ"]
```

**Variants checked**:
- `RELIANCE` (base symbol)
- `RELIANCE-EQ` (equity segment)
- `RELIANCE-BE` (B group equity)
- `RELIANCE-BL` (B group limited)
- `RELIANCE-BZ` (B group zero)

#### Active Buy Order Check

Also checks for pending buy orders:

```python
def has_active_buy_order(self, base_symbol: str) -> bool:
    if not self.orders:
        return False
    variants = set(self._symbol_variants(base_symbol))
    pend = self.orders.get_pending_orders() or []
    for o in pend:
        txn = str(o.get('transactionType') or '').upper()
        sym = str(o.get('tradingSymbol') or '').upper()
        if txn.startswith('B') and sym in variants:
            return True
    return False
```

**What it checks**:
- Pending orders from broker
- Transaction type starts with 'B' (BUY)
- Symbol matches (with variants)

#### 2FA Handling

If the holdings API requires 2FA authentication:
1. System detects 2FA gate
2. Attempts to force re-login
3. Retries holdings check
4. If re-login fails, returns `False` (assumes no holdings)

### Example Scenarios

**Scenario 1: Order Already Executed**
- 9:00 AM: Re-entry order placed at RSI 18
- 9:15 AM: Order executes (visible in holdings)
- 10:00 AM: RSI drops to 8 → **SKIPPED** (already in holdings)

**Scenario 2: Pending Order**
- 9:00 AM: Re-entry order placed at RSI 18 (pending)
- 9:30 AM: RSI drops to 8 → **SKIPPED** (active buy order exists)

**Scenario 3: Manual Buy**
- 9:00 AM: User manually buys RELIANCE
- 10:00 AM: System evaluates re-entry → **SKIPPED** (already in holdings)

**Scenario 4: Multiple Symbol Formats**
- Holdings contain: `RELIANCE-EQ`
- System checks: `RELIANCE`, `RELIANCE-EQ`, `RELIANCE-BE`, etc.
- Match found → **SKIPPED**

### Code Reference

```1564:1567:modules/kotak_neo_auto_trader/auto_trade_engine.py
# Re-entry duplicate protection: holdings and active order
if self.has_holding(symbol) or self.has_active_buy_order(symbol):
    logger.info(f"Re-entry skip {symbol}: already in holdings or pending order exists")
    continue
```

```786:806:modules/kotak_neo_auto_trader/auto_trade_engine.py
def has_holding(self, base_symbol: str) -> bool:
    if not self.portfolio:
        return False
    variants = set(self._symbol_variants(base_symbol))
    h = self.portfolio.get_holdings() or {}
    
    # Check for 2FA gate - if detected, force re-login and retry once
    if self._response_requires_2fa(h) and hasattr(self.auth, 'force_relogin'):
        logger.info(f"2FA gate detected in holdings check, attempting re-login...")
        try:
            if self.auth.force_relogin():
                h = self.portfolio.get_holdings() or {}
                logger.debug(f"Holdings re-fetched after re-login")
        except Exception as e:
            logger.warning(f"Re-login failed during holdings check: {e}")
    
    for item in (h.get('data') or []):
        sym = str(item.get('tradingSymbol') or '').upper()
        if sym in variants:
            return True
    return False
```

```782:784:modules/kotak_neo_auto_trader/auto_trade_engine.py
def _symbol_variants(base: str) -> List[str]:
    base = base.upper()
    return [base, f"{base}-EQ", f"{base}-BE", f"{base}-BL", f"{base}-BZ"]
```

## Complete Re-entry Flow

Here's the complete flow when evaluating re-entries:

```python
# 1. Get open positions
open_positions = get_open_positions_from_history()

# 2. For each position, check indicators
for symbol, entries in open_positions:
    rsi = get_rsi(symbol)
    price = get_price(symbol)
    ema9 = get_ema9(symbol)
    
    # 3. Check exit conditions first
    if price >= ema9 or rsi > 50:
        exit_position(symbol)
        continue  # Skip re-entry if exited
    
    # 4. Check reset mechanism
    levels = entries[0].get('levels_taken', {"30": True, "20": False, "10": False})
    if rsi > 30:
        entries[0]['reset_ready'] = True
    if rsi < 30 and reset_ready:
        # Reset all levels
        entries[0]['levels_taken'] = {"30": False, "20": False, "10": False}
        next_level = 30
    else:
        # Normal progression
        if levels.get('30') and not levels.get('20') and rsi < 20:
            next_level = 20
        if levels.get('20') and not levels.get('10') and rsi < 10:
            next_level = 10
    
    # 5. Check daily cap
    if next_level is not None:
        if reentries_today(symbol) >= 1:
            skip  # Daily cap reached
        
        # 6. Check holdings protection
        if has_holding(symbol) or has_active_buy_order(symbol):
            skip  # Already in holdings or pending order
        
        # 7. Place re-entry order
        place_reentry_order(symbol, next_level)
        entries[0]['levels_taken'][str(next_level)] = True
```

## Key Differences from Integrated Backtest

| Aspect | Auto Trader | Integrated Backtest |
|--------|-------------|---------------------|
| **Reset Mechanism** | Tracks RSI levels with reset when RSI > 30 | Tracks open positions, no level tracking |
| **Daily Cap** | Max 1 re-entry per symbol per day | No daily cap (processes all signals) |
| **Holdings Check** | Checks broker holdings API | Checks in-memory position objects |
| **Level Tracking** | Tracks which RSI levels used | No level tracking |
| **Re-entry Logic** | Based on RSI level progression | Based on position state (open/closed) |

## Summary

1. **Reset Mechanism**: Allows re-entries after position recovers (RSI > 30, then < 30 again)
2. **Daily Cap**: Limits to 1 re-entry per symbol per day to manage risk
3. **Holdings Protection**: Prevents duplicate orders by checking broker holdings and pending orders

These three mechanisms work together to ensure:
- **Controlled re-entries**: Not too many in one day
- **No duplicates**: Avoids placing orders when position already exists
- **Cycle management**: Allows fresh re-entries after recovery
