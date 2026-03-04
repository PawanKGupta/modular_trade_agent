# Debug: Why closed_at Was Not Set When Position Was Closed

This doc helps find the **actual root cause** when positions are closed at the broker but remain open in the DB (`closed_at` IS NULL). No fix is applied here—only steps to confirm which failure mode occurred.

---

## 1. Code paths that set `closed_at`

Only these paths write `closed_at`:

| Path | When it runs | What it uses to find the position |
|------|----------------|------------------------------------|
| **A. Reconciliation** | 9:15 AM (run_at_market_open) and 4:05 PM (before re-entry) | Loops over all open positions; for each, if `broker_qty == 0`, calls `mark_closed(user_id, symbol)` |
| **B. Sell order executed** | When a sell order **fills** (monitor sees executed) | Calls `mark_closed(user_id, full_symbol)` for that symbol |
| **C. Manual sell from orders** | When we detect a completed sell in orders (e.g. get_orders) | Calls `mark_closed(user_id, full_symbol)` |

Important: **mark_closed(user_id, symbol)** does **not** take a position id. It uses `get_by_symbol_for_update(user_id, symbol)`, which returns **exactly one row**: the most recent **open** position for that symbol (`closed_at IS NULL`, ordered by `opened_at DESC`, limit 1). So each call closes **one** row per symbol. If there are multiple open rows for the same symbol, reconciliation must call `mark_closed` once per row (it does—it iterates each open position).

---

## 2. Why closed_at might not get set (hypotheses)

- **H1. Reconciliation never ran**
  Holdings API failed or returned invalid (None, or no `"data"` key), so we return before building the broker map or looping. No `mark_closed` calls.

- **H2. Reconciliation ran but skipped closing**
  For each position we require `broker_qty == 0`. If the broker returns holdings with a **different symbol format** than the DB (e.g. `INDIAGLYCO` vs `INDIAGLYCO-EQ`), the lookup can fail and we use `broker_qty = 0` from `.get(base_symbol, 0)`. So symbol mismatch can still lead to close. But if we **skip** when `_has_recent_executed_buy_order(symbol, minutes=5)` is true, we never call `mark_closed` for that row.

- **H3. Sell orders were rejected, not executed**
  Path B only runs when a sell **fills**. If the broker **rejects** the sell (e.g. "No Holdings Present"), the executed path never runs, so no `mark_closed` from Path B. Then only reconciliation (Path A) can set `closed_at`.

- **H4. Wrong row closed when multiple per symbol**
  Each `mark_closed(symbol)` closes a single row (the one returned by `get_by_symbol_for_update`). If we only call it once per symbol in some path (e.g. one sell execution), one row gets closed and other open rows for the same symbol can stay open.

- **H5. mark_closed failed**
  `get_by_symbol_for_update` returns None (e.g. position already closed by another flow), so we log "Position not found for {symbol}" and return without updating. Or commit failed.

---

## 3. Commands to run (find which hypothesis is true)

Run these on the **same host/container** where the trading service runs (e.g. Ubuntu server or API container).

### 3.1 Did reconciliation run at all?

```bash
# Broader time window (e.g. 3 days) to catch 9:15 and 16:05 runs
docker logs tradeagent-api --since 72h 2>&1 | grep -iE "Reconciling [0-9]+ open positions|Holdings API returned|Failed to fetch holdings for reconciliation|Skipping reconciliation|missing 'data' key"
```

- If you see **"Holdings API returned None"** or **"Failed to fetch holdings"** or **"missing 'data' key"** → **H1**: reconciliation ran but exited early; no positions updated.
- If you see **"Reconciling N open positions"** with N > 0 → reconciliation reached the loop. Then check 3.2 and 3.3.
- If you see **no** reconciliation lines → either reconciliation runs in another process (check that process’s logs) or the task never ran.

### 3.2 Did reconciliation try to close positions?

```bash
docker logs tradeagent-api --since 72h 2>&1 | grep -iE "Manual full sell detected for|Position marked as closed|Position .* marked as closed due to manual full sell|Skipping reconciliation for .* Recent executed buy"
```

- **"Manual full sell detected for SYMBOL"** → we detected broker_qty=0 and attempted `mark_closed`.
- **"Position marked as closed"** (from positions_repository) → `mark_closed` ran and committed.
- **"Skipping reconciliation for SYMBOL: Recent executed buy"** → we did **not** call `mark_closed` for that symbol (H2 skip).

### 3.3 Did mark_closed fail (position not found)?

```bash
docker logs tradeagent-api --since 72h 2>&1 | grep -i "Position not found for"
```

- If you see **"Position not found for SYMBOL"** → `get_by_symbol_for_update` returned None (e.g. already closed or wrong user). That supports **H5**.

### 3.4 Sell orders: executed vs rejected

```bash
# Rejected (no fill → Path B never runs)
docker logs tradeagent-api --since 72h 2>&1 | grep -iE "Status: rejected|No Holdings Present" | head -20

# Executed (Path B should run)
docker logs tradeagent-api --since 72h 2>&1 | grep -iE "Status: executed|Status: complete|Position marked as closed in database" | head -20
```

- If sells are only **rejected** → Path B never runs; only reconciliation can set `closed_at` (**H3**).

### 3.5 DB: multiple open positions per symbol

For user_id 2, list open positions and count by symbol:

```bash
docker exec -it tradeagent-db psql -U trader -d tradeagent -c "
SELECT symbol, COUNT(*) AS open_count, array_agg(id ORDER BY opened_at DESC) AS position_ids
FROM positions
WHERE user_id = 2 AND closed_at IS NULL
GROUP BY symbol
HAVING COUNT(*) > 1;
"
```

- If there are symbols with **multiple open rows**, then any path that calls `mark_closed(symbol)` only once per symbol closes **one** row; others stay open (**H4**). Reconciliation normally calls it once per row, so this only applies if reconciliation didn’t run or didn’t process those rows.

### 3.6 Broker symbol format vs DB

Reconciliation matches using `pos.symbol.upper()` and `extract_base_symbol(symbol)`. If the broker returns a different format (e.g. no `-EQ`), we still map base symbol. To confirm broker format, you’d need a sample holdings response (e.g. from a test script or logged response). If the broker uses a symbol we never map (e.g. different segment suffix), lookup could fail and we’d treat as 0 and try to close—so symbol format is less likely to prevent closing than H1/H2/H3.

---

## 4. Summary table: use log + DB results

| What you see | Likely hypothesis |
|--------------|-------------------|
| "Holdings API returned None" / "Failed to fetch holdings" / "missing 'data' key" | **H1**: Reconciliation bailed; no closes. |
| "Reconciling N open positions" but no "Manual full sell detected" | Holdings had qty > 0 for all, or symbol mismatch (less likely if base symbol is mapped). |
| "Manual full sell detected" but no "Position marked as closed" for that symbol | **H5**: mark_closed failed (e.g. position not found), or exception after. |
| "Skipping reconciliation for … Recent executed buy" | **H2**: We intentionally skipped closing; next cycle should close unless buy is still “recent”. |
| Only "Status: rejected" / "No Holdings Present", no executed sells | **H3**: Path B never runs; only reconciliation can set closed_at. |
| Multiple open rows per symbol and only one closed_at set recently | **H4**: Some path closed one row per symbol; others left open. |

---

## 5. Next step after you have results

- If **H1**: Fix why holdings API is failing or returning invalid response at 9:15 / 16:05 (or add a safe fallback so we don’t place sells when holdings are missing).
- If **H2**: Review `_has_recent_executed_buy_order` window and whether we should still close when broker shows 0.
- If **H3**: Rely on reconciliation to set closed_at when broker has 0; ensure reconciliation runs and gets valid holdings. Optionally, when a sell is rejected with “No Holdings”, trigger reconciliation for that symbol or mark closed.
- If **H4**: Ensure every path that should “close this symbol” either calls `mark_closed` once per open row for that symbol (like reconciliation) or closes by position id if we have it.
- If **H5**: Find why `get_by_symbol_for_update` returned None (e.g. wrong user, already closed, or race) and fix that path.

Run the commands in section 3, note which of the log lines and DB results you get, then we can pinpoint the root cause and design the fix.

---

## 6. FAQ: Manual holdings, symbol format, API down

**Q: What if the broker has a manual holding (not traded by the system)?**
The system only places sells for positions that exist in the **positions** table. Symbols that appear only in broker holdings (never bought by the system) are never sold. If the user manually bought **more** of a symbol we already have, reconciliation treats it as "manual buy" (broker_qty > positions_qty) and **ignores** it (does not update the position). In `get_open_positions()` we use `min(positions_qty, broker_qty)`, so we only place a sell for up to `positions_qty` (the system’s quantity), not the extra manual quantity. So manual holdings are safe: we never sell symbols we don’t track, and we don’t sell the “extra” manual quantity.

**Q: Broker returns symbol "IDEA" but DB has "IDEA-EQ". How is this handled?**
- **Reconciliation:** The broker map is built with both full and base symbol (`extract_base_symbol`). For each position we look up `symbol` (e.g. IDEA-EQ) then `base_symbol` (e.g. IDEA). So IDEA-EQ matches broker "IDEA".
- **get_open_positions():** Same logic was added: we look up by `pos.symbol.upper()` (IDEA-EQ), then by `extract_base_symbol(symbol_upper)` (IDEA), so broker "IDEA" is matched to DB "IDEA-EQ".

**Q: What if the broker API is down during reconciliation? Are positions marked closed?**
No. If `get_holdings()` fails (exception or None) after retries, reconciliation **returns early** and does **not** update any position. No `mark_closed()` is called. So when the API is down we never mark positions closed; we only skip reconciliation. That avoids incorrectly closing positions when we have no data.
