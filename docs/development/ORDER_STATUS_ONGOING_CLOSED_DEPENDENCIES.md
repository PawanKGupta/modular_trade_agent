# Order Status: ONGOING and CLOSED Dependencies

Summary of modules that depend on **ONGOING** status and modules that use **CLOSED** in the context of closing positions. After the change "filled = CLOSED, closed_at at order closer", ONGOING is legacy for filled orders; new fills are CLOSED.

---

## 0. Modules incorporated (CLOSED treated like ONGOING where “executed / active buy” is intended)

These modules have been updated so that **CLOSED** (filled) orders are treated the same as **ONGOING** where the intent is “executed order” or “active buy order”:

| Module | Change |
|--------|--------|
| **order_tracker.py** | EXECUTED → CLOSED; `get_pending_orders()` uses PENDING only. |
| **sell_engine.py** | `_has_recent_executed_buy_order` and executed-buy queries use `(ONGOING, CLOSED)`; active sell filters use PENDING only. |
| **auto_trade_engine.py** | “Already executed / skip” checks use `(ONGOING, CLOSED)`. |
| **unified_order_monitor.py** | Executed-buy and sync logic use `(ONGOING, CLOSED)`. |
| **portfolio_service.py** | get_current_positions includes CLOSED where ONGOING was used for “executed, position open”. |
| **order_validation_service.py** | Active buy order check: `status in [PENDING, ONGOING, CLOSED]` so filled (CLOSED) orders also block duplicate buy. |
| **analysis_deduplication_service.py** | Renamed `_has_ongoing_buy_order_by_symbol` → `_has_open_position_for_symbol`; comments use open position; “open position” logic unchanged (uses Positions via `has_ongoing_buy_order()`). |

---

## 1. Modules that depend on ONGOING status

### Production / source code (excluding tests and alembic)

| Module | Usage | Notes |
|--------|--------|--------|
| **order_tracker.py** | `get_pending_orders()`: includes `DbOrderStatus.ONGOING` in `pending_statuses` (line ~293). | Legacy: orders synced as ONGOING may still exist. New EXECUTED → CLOSED, so new orders won't be ONGOING. Keeping ONGOING in the filter supports legacy rows. |
| **orders_repository.py** | `create_amo` duplicate check: `status not in [PENDING, ONGOING]` (303, 332). `cancel_active_sell_for_symbol`: `status.in_([PENDING, ONGOING])` (560, 832). `get_order_with_position`: `status.in_([ONGOING, CLOSED])` (602). `list` default statuses: PENDING, ONGOING (627). Symbol-order check: `o.status in [ONGOING, PENDING]` (1092, 1094). Raw SQL / index: `status IN ('pending','ongoing')` (388, 400, 500). | Active sell index and duplicate checks treat ONGOING as "active". Filled orders are now CLOSED; ONGOING remains for legacy or any other path that still writes it. |
| **analysis_deduplication_service.py** | Uses `_has_open_position_for_symbol()` which calls `orders_repo.has_ongoing_buy_order()`. | **Done.** Renamed from _has_ongoing_buy_order_by_symbol. `has_ongoing_buy_order()` uses **Positions** (closed_at IS NULL); open position is from Positions table. |
| **paper_trading_service_adapter.py** | Comment only: "ONGOING and CLOSED orders which indicate a position was opened" (2008). | No logic change needed; comment could be updated to "CLOSED orders which indicate a position was opened". |
| **sell_engine.py** | Ticker from order: queries orders with `status in (ONGOING, CLOSED)` (639). Manual sell detection: filters ONGOING/CLOSED (955, 980). Position close via `positions_repo.mark_closed()`; `_close_buy_orders_for_symbol` updates orders only (ONGOING or CLOSED+closed_at None) for legacy/backfill (3315). `_has_recent_executed_buy_order`: treats CLOSED with execution_time/filled_at as "recent executed" (2030). `_cancel_orphaned_sell_orders`: only PENDING (2089). | **Done.** Position close is via Positions only; _close_buy_orders_for_symbol docstring clarifies order lifecycle/legacy. _has_recent_executed_buy_order already uses (ONGOING, CLOSED). |
| **auto_trade_engine.py** | Re-entry block check includes PENDING/ONGOING/CLOSED; only blocks when execution_qty is None (2183). ONGOING in cancel-before-retry (3474). | **Done.** Re-entry: CLOSED included so only unfilled orders block; filled (ONGOING/CLOSED) don't block. |
| **unified_order_monitor.py** | Queries/checks ONGOING (697, 763, 1980). | Same idea: "executed order" was ONGOING; now can be CLOSED. |
| **order_validation_service.py** | Active buy check now `[PENDING, ONGOING, CLOSED]` (351). | **Incorporated:** CLOSED (filled) orders also block duplicate buy; see §0. |
| **portfolio_service.py** | get_current_positions / capacity includes ONGOING and CLOSED (373, etc.). | **Done.** CLOSED (filled) orders included so "executed, position open" is consistent with filled=CLOSED. |
| **src/infrastructure/db/models.py** | `ONGOING = "ongoing"` enum value. | Keep for legacy data and any code that still reads/writes ONGOING. |
| **alembic** | Unique index and migrations use `status IN ('pending','ongoing')`. | Schema/history; no code change. |

### Tests

Many tests still create or assert ONGOING (e.g. test_buy_order_closure_on_position_close, test_order_tracker_dual_write, test_analysis_deduplication_service, test_unified_order_monitor, test_portfolio_service, test_sell_engine_*, test_premarket_reentry_adjustment, test_broker, etc.). They either validate legacy behavior or "active order" semantics; update as needed when switching to CLOSED-only for filled orders.

---

## 2. Modules that use CLOSED status to close positions

**Finding:** Nothing uses order CLOSED status to close the position. Positions are closed only via the **Positions** table (e.g. `positions_repo.mark_closed()`).

Here "close position" means updating **Positions** (e.g. `mark_closed`, `closed_at`). "Order CLOSED" is the Orders row status.

| Module | Usage | Notes |
|--------|--------|--------|
| **sell_engine.py** | When a sell executes: (1) calls `positions_repo.mark_closed()` (and similar) to close the **position**; (2) calls `_close_buy_orders_for_symbol()` which updates **orders** (sets status CLOSED and order `closed_at`) for legacy ONGOING or CLOSED+closed_at None. It does **not** close the position. | Position close is done only via **Positions** (mark_closed). New fills already get `closed_at` in `mark_executed`, so `_close_buy_orders_for_symbol` is only for legacy/backfill. |
| **orders_repository.py** | `mark_executed`: sets order `status = CLOSED` and `closed_at` at fill time. `mark_cancelled`: sets `closed_at`. | Order lifecycle only; does not touch positions. |
| **order_tracker.py** | When broker reports EXECUTED, sets order status CLOSED and closed_at/filled_at. | Order lifecycle only; no position close. |
| **paper_trading_adapter.py** | Comment: "Order status to CLOSED when executed (for both buy and sell)". | No position close; comment describes order status. |

**Summary:** CLOSED is used on **orders** when the order is done (filled/cancelled), not to close the position. Position close is always via **Positions**. A more detailed breakdown (with line refs) is in this doc.

---

## 2b. “Closed position” vs “order status CLOSED/ONGOING” — using Positions table

**Yes. We use the Positions table for “position open/closed”; we do not use order status for that.**

| Question | Source of truth | Notes |
|----------|------------------|--------|
| **Is the position closed?** | **Positions table**: `closed_at IS NOT NULL` (or `position.closed_at is not None`) | Set when `positions_repo.mark_closed()` is called (e.g. on sell execution). |
| **Is the position open?** | **Positions table**: `closed_at IS NULL` | `positions_repo.list()` / `get_by_symbol()` return only open positions by default. |
| **Was the order filled?** | **Orders table**: `status in (ONGOING, CLOSED)` | Order lifecycle only; does not imply position is still open. |
| **Does user have an open position for symbol?** | **Positions table** (e.g. `orders_repo.has_ongoing_buy_order()` → queries Positions with `closed_at IS NULL`) | Used by analysis_deduplication_service, order_validation_service (positions check), portfolio_service, sell_engine, etc. |

**Modules that use Positions table for closed/open position:**

- **positions_repository**: `mark_closed()` sets `closed_at`; `list()` / `get_by_symbol()` filter by `closed_at.is_(None)`.
- **orders_repository.has_ongoing_buy_order()**: Uses **Positions** (`closed_at IS NULL`), not Order status.
- **analysis_deduplication_service**: “Open position” via `has_ongoing_buy_order()` (Positions) and `position.closed_at is None`.
- **order_validation_service**: Positions check uses `existing_position.closed_at is None`.
- **sell_engine**: Uses `positions_repo.mark_closed()` when sell executes; elsewhere checks `position.closed_at is None` for open.
- **auto_trade_engine**: Open positions filtered by `p.closed_at is None`; calls `positions_repo.mark_closed()`; re-entry cancellation checks `position.closed_at is not None`.
- **unified_order_monitor**: Checks `existing_pos.closed_at`, `current_position.closed_at`; creates/updates positions; does not use order status for “position closed”.
- **portfolio_service.get_current_positions()**: Counts open **system** positions (`Positions` table) plus in-flight system buy orders; manual broker demat holdings do not count toward `max_portfolio_size`.
- **paper_trading_adapter**: Uses `position.closed_at` and `positions_repo.mark_closed()`; open positions filtered by `closed_at is None`.

**Summary:** Order status **CLOSED**/ONGOING means “order filled”. Whether a **position** is open or closed is determined only by the **Positions** table (`closed_at`). Modules that need “closed position” or “open position” use the Positions table (and `mark_closed()` for closing), not order status.

---

## 3. Recommended follow-ups (optional)

1. **sell_engine._has_recent_executed_buy_order**
   **Done.** Treats CLOSED orders with execution_time/filled_at as "recent executed" (not only ONGOING).

2. **order_tracker.get_pending_orders**
   Keep ONGOING in `pending_statuses` for legacy; no change required unless we stop writing ONGOING entirely.

3. **analysis_deduplication_service**
   **Done.** Renamed to `_has_open_position_for_symbol`; comments use "open position" wording. Logic already used Positions via `has_ongoing_buy_order()`.

4. **auto_trade_engine / unified_order_monitor / portfolio_service**
   **Done.** Where intent is "user has open position" or "executed order": include CLOSED (and/or rely on Positions). portfolio_service get_current_positions includes CLOSED; auto_trade_engine re-entry block check includes CLOSED so only unfilled (execution_qty None) block.

5. **Tests**
   Gradually replace ONGOING with CLOSED in tests that represent filled orders, and adjust any that assert "pending" to exclude CLOSED where appropriate.
