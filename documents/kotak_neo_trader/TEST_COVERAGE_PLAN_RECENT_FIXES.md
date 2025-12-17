## Test Coverage & Edge-Case Plan – Recent Fixes (Full Symbols, Sell Flow, ML, Regime)

**Scope**: This document tracks remaining tests and edge cases for the recent changes:
- Full-symbols migration (`RELIANCE` → `RELIANCE-EQ`, etc.)
- Positions vs broker holdings reconciliation
- Scrip master auth/download behavior
- ML verdict service market-regime features (VIX, Nifty trend)
- Sell order placement persistence into `orders` table

Status markers:
- `[ ]` = not implemented
- `[~]` = partially implemented
- `[x]` = implemented & covered

---

## 1. Positions & Reconciliation (Broker vs DB)

- **[x] Holdings symbol mapping (full vs base)**
  - **Goal**: `_reconcile_positions_with_broker_holdings()` correctly matches:
    - `ASTERDM-EQ` ↔ holdings with `symbol='ASTERDM'`, `displaySymbol='ASTERDM'`
    - `EMKAY-BE` ↔ holdings with `symbol='EMKAY'`, `displaySymbol='EMKAY-BE'`
  - **Test ideas**:
    - Unit tests for `_reconcile_positions_with_broker_holdings` using:
      - Mock `positions_repo.list()` returning open positions with full symbols.
      - Mock `portfolio.get_holdings()` returning only base symbols / displaySymbol.
    - Assert that `broker_holdings_map` contains both full and base keys.

- **[x] No false "manual full sell" when holdings exist**
  - **Goal**: When DB position has `quantity > 0` and broker holdings show non-zero qty, reconciliation must **not**:
    - Call `mark_closed()`
    - Set `quantity = 0`
  - **Test ideas**:
    - Given `positions_repo.list()` returns `ASTERDM-EQ` qty=16 and holdings map has qty=16 (via base key):
      - Assert `positions_repo.mark_closed` is **not** called.
      - Assert stats `closed == 0`, `updated == 0`, `ignored == 1` or `0` depending on scenario.

- **[x] Correct behavior when holdings truly missing**
  - **Goal**: If holdings do not contain the symbol (even via base symbol), and DB shows qty>0:
    - Reconciliation should treat as **manual full sell** and call `mark_closed()` (setting `closed_at` and qty=0).
  - **Test ideas**:
    - holdings_data = `[]` or missing both full/base keys.
    - Assert `positions_repo.mark_closed` is called with correct `symbol` and `user_id`.

- **[x] Manual partial sells (broker_qty < positions_qty)**
  - **Goal**: When broker_qty < positions_qty, we detect partial sells and call `reduce_quantity()` correctly.
  - **Test ideas**:
    - DB position qty=100, holdings qty=60; expect `reduce_quantity(... sold_quantity=40)` and stats `updated == 1`.

- **[x] Manual buys (broker_qty > positions_qty) ignored**
  - **Goal**: When broker_qty > positions_qty, reconciliation logs and **does not** modify the DB.
  - **Test ideas**:
    - DB position qty=100, holdings qty=120; assert no `mark_closed` or `reduce_quantity` calls.

---

## 2. SellOrderManager → `orders` Table Persistence

- **[x] DB persistence on sell placement (happy path)**
  - **Goal**: When `place_sell_order()` succeeds:
    - A row is created in `orders` with:
      - `side='sell'`
      - Correct `symbol`, `quantity`, `price`
      - `broker_order_id` set to extracted ID
      - `entry_type='exit'`
      - `order_metadata` includes `ticker`, `exchange`, `base_symbol`, `full_symbol`, `variety`, `source`.
  - **Test ideas**:
    - Unit test with:
      - Mock `self.orders.place_limit_sell` returning a fake response (`{"neoOrdNo": "12345"}`).
      - Mock `orders_repo.create_amo` and assert it is called with expected kwargs.

- **[x] No DB write when `orders_repo` or `user_id` missing**
  - **Goal**: Legacy / test-mode paths should still work without DB.
  - **Test ideas**:
    - Initialize `SellOrderManager` with `orders_repo=None` or `user_id=None`.
    - Assert broker call is made and order ID returned.
    - Assert `create_amo` is **not** called.

- **[x] Handling DB errors during persistence**
  - **Goal**: If `orders_repo.create_amo` raises, the broker sell order is still considered placed and returned.
  - **Test ideas**:
    - Mock `create_amo` to raise an exception.
    - Assert `place_sell_order` returns the broker `order_id_str` and logs a warning (no crash).

---

## 3. Scrip Master & Authentication

- **[x] No background download when `auth_client` is None**
  - **Goal**: Avoid noisy auth errors when only cached scrip master is used.
  - **Test ideas**:
    - Unit test `KotakNeoScripMaster.load_scrip_master(force_download=False)`:
      - Setup `self.auth_client = None` and a fake `latest_cache` file.
      - Assert `_download_scrip_master` is **not** called.
      - Assert a debug log like “skipping background download … auth_client not available” is emitted.

- **[x] Background download when `auth_client` present**
  - **Goal**: When authenticated, background refresh should be attempted and cache updated.
  - **Test ideas**:
    - Mock `self.auth_client` and `_download_scrip_master` to return a small instrument list.
    - Assert `_save_to_cache` is called and the returned `instruments` are updated.

- **[x] Symbol resolution for sell placement**
  - **Goal**: `place_sell_order()` uses scrip master correctly when available.
  - **Test ideas**:
    - Mock `self.scrip_master.symbol_map` so `get_trading_symbol("ASTERDM-EQ", exchange="NSE")` returns `ASTERDM-EQ` or alternate mapping.
    - Ensure symbol passed to `place_limit_sell` matches expected full broker symbol.

---

## 4. MarketRegimeService & ML Features (VIX)

- **[x] VIX clamping range in `_get_vix`**
  - **Goal**: `_get_vix()` always returns `10.0 <= india_vix <= 50.0`.
  - **Test ideas**:
    - Patch `yf.download` to return `Close`=9.0 → expect 10.0.
    - Patch to return `Close`=60.0 → expect 50.0.
    - Patch to return empty DataFrame → expect default 20.0.

- **[ ] MLVerdictService feature extraction uses clamped VIX**
  - **Goal**: `_extract_features()` always sets `features['india_vix']` in `[10, 50]`.
  - **Test ideas**:
    - Patch `get_market_regime_service().get_market_regime_features` to return edge VIX values and confirm final feature is clamped.
    - Ensure failure path (exception in regime service) still sets `india_vix=20.0`.

---

## 5. Full-Symbols Migration & Utility Scripts

- **[ ] Migration script: positions to full symbols**
  - **Goal**: Alembic migration `20250117_migrate_positions_to_full_symbols`:
    - Converts base symbols to full symbols correctly.
    - Has correct `down_revision` for production (`20250115_remove_positions_unique_constraint`).
  - **Test ideas**:
    - Use a temporary DB with synthetic `positions` rows (`RELIANCE`, `SALSTEEL`).
    - Run migration up, then verify `symbol` updated to `RELIANCE-EQ`, `SALSTEEL-BE`, etc.

- **[ ] `add_missing_broker_positions.py` behavior**
  - **Goal**: Script adds positions like ASTERDM-EQ, EMKAY-BE with correct metadata.
  - **Test ideas**:
    - Run script in a test DB:
      - Assert new rows have proper `user_id`, `symbol`, `quantity`, `avg_price`, `opened_at`.
      - Assert `entry_type="initial"` and `orig_source="signal"`.
      - Assert `order_metadata` includes `ticker`, `exchange`, `base_symbol`, `full_symbol`.

- **[ ] `fix_missed_entry_type.py` corrections**
  - **Goal**: Script updates existing rows incorrectly flagged as manual.
  - **Test ideas**:
    - Pre-populate test DB with `orders` / `positions` having `entry_type="manual"` / `orig_source="manual"` for known IDs.
    - Run script and assert those specific rows are updated to `"initial"` / `"signal"` and others untouched.

---

## 6. Scheduler & Session Management (Sell Monitor)

> Note: This section is for upcoming fixes to the SQLAlchemy session error in the scheduler thread.

- **[ ] No `InvalidRequestError` in sell monitor scheduler**
  - **Goal**: When using thread-local sessions in `_run_paper_trading_scheduler`, sell monitor:
    - Does not reuse the main `db` session incorrectly.
    - Runs without “session in 'prepared' state” errors.
  - **Test ideas**:
    - Integration-style test with a fake scheduler thread and mock DB that asserts separate sessions are used per thread.

- **[ ] Legacy file + DB hybrid monitoring consistency**
  - **Goal**: With both file-based active orders and DB-backed orders:
    - Monitor does not double-place or double-track sell orders.
  - **Test ideas**:
    - Seed JSON history with active sell orders and DB with matching `orders` rows.
    - Run monitoring cycle and assert no duplicate broker submissions.

---

## 7. Observability & Logging

- **[ ] Reconciliation logs**
  - **Goal**: Key log lines exist and are stable enough to grep in prod:
    - `"Reconciling X open positions with broker holdings..."`
    - Warnings for manual full/partial sells.
  - **Test ideas**:
    - Use `caplog` in unit tests to assert presence of messages when reconciliation runs.

- **[x] Sell order persistence logs**
  - **Goal**:
    - Log when sell order is placed and persisted to DB.
    - Log warning when DB persistence fails but broker order succeeded.
  - **Test ideas**:
    - Unit test `place_sell_order` with a caplog fixture.

- **[x] Scrip master cache/skip logs**
  - **Goal**: Clear logging around cache usage and background download behavior.
  - **Test ideas**:
    - Unit test `load_scrip_master` with/without `auth_client` and assert expected log lines.

---

## 8. Execution Checklist

- **[x] Implement unit tests for reconciliation mapping & behavior (Section 1).**
- **[x] Implement unit tests for sell order DB persistence (Section 2).**
- **[x] Implement scrip master auth/cache tests (Section 3).**
- **[x] Implement VIX clamping & ML feature tests (Section 4).**
- **[~] Add migration & script tests around full-symbols (Section 5).** - *Not required (manual/integration tests)*
- **[ ] Add scheduler/session tests once final design is agreed (Section 6).** - *Pending design*
- **[~] Add caplog-based logging tests for critical flows (Section 7).** - *Partially implemented (2/3 areas)*
