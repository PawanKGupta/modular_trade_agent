# Trading Services Flow - Real Trading Day

## Overview

The unified trading service (`run_trading_service.py`) runs continuously 24/7 and executes different tasks automatically on trading days (Monday-Friday) at specific times. This document explains the flow of each service during a real trading day.

---

## Service Architecture

### Unified Trading Service
- **Single Persistent Service**: Runs all tasks with one persistent session
- **Continuous Operation**: Runs 24/7, checks every 30 seconds
- **Trading Days Only**: Tasks execute only on Mon-Fri
- **Database-Driven Schedules**: Task times are configurable via `service_schedules`
- **Heartbeat Updates**: Updates service status every minute

### Default schedule (IST)

| Time | Task | Purpose |
|------|------|---------|
| **16:00** | `analysis` | Generate buy/sell signals for next session |
| **16:05** | `buy_margin_preview` | Margin check + Telegram if shortfall (**no orders placed**) |
| **09:01** | `buy_orders` | Place **REGULAR** market buys at open |
| **09:03** | `premarket_retry` | Retry failed buys from DB |
| **09:05** | `premarket_amo_adjustment` | Adjust open **pending BUY** qty (if enabled in config) |
| **09:15** | `sell_monitor` | Place/monitor sells (continuous until 15:30) |
| **18:00** | `eod_cleanup` | End-of-day reset; cancels unexecuted **DAY sell limits** and **REGULAR/DAY pending buys** (AMO buys kept for 9:05 adjustment) |

---

## Daily Trading Flow Timeline

### Evening (after analysis)

#### Analysis (16:00 / configurable)
**Task**: `run_analysis()` (via Individual Service Manager)

Generates recommendations in `signals` for the next trading day.

#### Buy margin preview (16:05 / configurable)
**Task**: `run_buy_margin_preview()`

**Purpose**: Check Kotak `check-margin` for each buy recommendation **without placing orders**. Sends Telegram warnings when margin is insufficient so funds can be added before the open.

**Key operations**:
- `engine.preview_evening_buy_margins()` → `place_new_entries(..., dry_run=True)`
- No broker placement; no failed-order rows for shortfall (preview only)

---

### Pre-market / open (9:00–9:15)

#### Buy orders (9:01 / configurable)
**Task**: `run_buy_orders()`

**Purpose**: Place morning **REGULAR** buys when `is_market_hours()` is true (includes NSE pre-open from 9:00 IST). During **pre-open** (`is_pre_open_session()`), orders are **LIMIT @ signal close**; after 9:15-style regular placement windows, **MARKET**.

**Flow**:
1. Load buy recommendations from `signals`.
2. Portfolio limits, margin check, `place_new_entries()`.
3. `place_reentry_orders()` in the same task.

**Note**: Requires prior-day (or same-day) analysis signals. Full intent and 9:05/9:15 behavior: [Morning buy flow](#morning-buy-flow-901--905--915).

#### Pre-market retry (9:03 / configurable)
**Task**: `run_premarket_retry()`

Retries **FAILED** / insufficient-balance orders from the database (after morning placement).

Uses the same pre-open placement rules as **9:01** (`is_pre_open_session()` → **REGULAR LIMIT** at signal close).

#### Pre-market pending buy adjustment (9:05)
**Task**: `run_premarket_amo_adjustment()`

**Purpose**: Recalculate pending **buy** quantity from pre-market LTP so deployment tracks assigned capital at **today’s** price. Gated by `enable_premarket_amo_adjustment` (default **on** in `StrategyConfig`).

**Key operations**:
- `engine.adjust_amo_quantities_premarket()` (live and paper)
- EMA9 gap-up cancel when pre-market > EMA9 − 1%
- Finalize as **MARKET** when LTP/EMA9 gates pass (LIMIT always; MARKET only on qty change) — live: `modify_order(..., order_type="MKT")`; paper: cancel + replace
- **Live only (log-only):** Kotak `filter=all` quote → log all **5 bid** (`depth.buy`) and **5 ask** (`depth.sell`) levels per pending entry/re-entry buy. INFO line is tagged `[ok]`, `[empty]` (API ok, no live levels), or `[unavailable]` (API fault / no quote / token missing); does not change qty, price, or order type
- **Notifications (Telegram / in-app / email):** Order events use the shared trading dispatcher — per-channel prefs and **quiet hours** apply. Fill/reject/cancel can fire from the **order verifier** (immediate) and **unified order monitor** (poll); **dedupe** on `(user_id, order_id, event_type)` prevents double delivery. Order-event Telegram is **exempt from the 10/min rate cap** (9:05 bursts). Per-order alerts when a buy is adjusted or EMA9-cancelled (**Order modified** / **Order cancelled**). Service task completion sends an **in-app one-liner** only (e.g. `3 adjusted, 1 cancelled (EMA9)`); duplicate Telegram/email for `SERVICE_EXECUTION_COMPLETED` is suppressed. Sell-monitor programmatic edits do **not** use **Order modified**. Defaults: **in-app on**, Telegram/email off until enabled. Failures in notify paths are logged only — trading is not blocked.

See **[Morning buy flow (9:01 → 9:05 → 9:15)](#morning-buy-flow-901--905--915)** below for product intent, code validation, and edge cases.

---

## Morning buy flow (9:01 → 9:05 → 9:15)

### Purpose

Morning buys use a **two-step** model:

1. **9:01** — Pre-market LTP is not reliable for **MARKET** placement; use **prior signal close** as a price proxy and place a **pending REGULAR LIMIT** order.
2. **9:05** — Pre-market LTP is available; **resize quantity** using **execution_capital** (liquidity-aware, same as 9:01) and **finalize as MARKET** (always for LIMIT proxy orders; MARKET orders only when qty changes).
3. **9:15** — Regular session; pending **MARKET** buys execute with the broker (or paper simulator). **`sell_monitor`** starts (sells); it is not a separate “buy fill” task.

The **9:01 LIMIT price is not a permanent “never pay above ₹X” cap**. It is a **stand-in until pre-market data exists**. Capital deployment at **today’s** price is the goal at **9:05**.

### Validated flow (code)

NSE pre-open in code: `is_pre_open_session()` → **9:00–9:25 IST** (`core/volume_analysis.py`). Regular continuous session pricing for new **MARKET** buys is after the open; scheduler tasks below use the default IST times from `service_schedules`.

| Time | Task | What the code does | Code anchors |
|------|------|-------------------|--------------|
| **9:01** | `buy_orders` | Load signals → `place_new_entries()` + `place_reentry_orders()`. If `is_pre_open_session()`: **REGULAR LIMIT** at `round(signal_close, 2)`; qty `floor(execution_capital / close)` (liquidity may cap below `user_capital`). | `auto_trade_engine._attempt_place_order`, `paper_trading_service_adapter._buy_order_type_and_price_for_session` |
| **9:03** | `premarket_retry` | Retry **FAILED** rows from DB with same pre-open LIMIT @ close rules. | `run_premarket_retry` |
| **9:05** | `premarket_amo_adjustment` | For each open pending buy (non-IOC): fetch pre-market LTP → optional **EMA9 cancel** → `new_qty = floor(execution_capital / premarket_price)`. **LIMIT** (9:01 close proxy) → always **MARKET** finalize. **MARKET** → finalize only if `new_qty != original_qty`. | `adjust_amo_quantities_premarket` (live + paper) |
| **9:15+** | `sell_monitor` | **Live:** broker executes pending **MARKET** buys at open; sells monitored/placed. **Paper:** `_execute_pending_limit_buys_before_sell_placement()` runs any **remaining LIMIT** buys before sell placement. New buys after pre-open use **MARKET**. | `run_sell_monitor`, paper `run_sell_monitor` path |

### Flow diagram (happy path)

Example: assigned capital **₹2,00,000**, signal close **₹100**, pre-market at 9:05 **₹105**.

```text
9:01 — No reliable pre-market LTP for MARKET
        → REGULAR LIMIT @ ₹100 (signal close proxy)
        → qty ≈ floor(execution_capital / 100)  e.g. 2000 shares
        → Pending at broker; not a permanent price cap

9:05 — Pre-market LTP available (₹105)
        → new_qty = floor(2,00,000 / 105) = 1904  (≠ 2000)
        → Modify/replace as MARKET, qty 1904
        → Yesterday’s ₹100 limit superseded for sizing

9:15 — Regular session
        → MARKET buy fills near open (~₹2L notional, subject to liquidity/gaps)
        → sell_monitor places/monitors exits on filled holdings
```

### Edge cases (validated)

| Case | Behavior |
|------|----------|
| **`enable_premarket_amo_adjustment` off** | 9:05 skipped; 9:01 LIMIT @ close remains until broker fill/cancel/EOD. |
| **Pre-market LTP missing** | Order skipped at 9:05 (`price_unavailable`); 9:01 LIMIT unchanged. |
| **Pre-market > EMA9 − 1%** | Order **cancelled** at 9:05 (`cancelled_above_ema9`); no 9:15 buy. |
| **`new_qty == original_qty` at 9:05, order is LIMIT** | **MARKET finalize** anyway (close proxy superseded). |
| **`new_qty == original_qty` at 9:05, order is MARKET** | **No modify** (`no_adjustment_needed`). |
| **9:01 and 9:05 capital** | Both use **execution_capital** (liquidity-aware via `LiquidityCapitalService`). |
| **Legacy evening AMO** | Not the default path; paper logs stale AMO at 9:01 for manual handling. |

### QA note: LIMIT → MARKET at 9:05

Reviewers sometimes treat 9:01 LIMIT as **price protection**. In this product, it is a **placement proxy** without pre-market data. Converting to **MARKET** when quantity changes at 9:05 is **intentional** so ~**assigned capital** deploys at **pre-market-based** sizing, not at yesterday’s close notional.

### 9:05 finalize rules (implemented)

1. **Capital** — `execution_capital` at 9:05 (liquidity-capped, same basis as 9:01 placement).
2. **MARKET finalize** — After LTP + EMA9 gates: **LIMIT** orders always → **MARKET** at `floor(execution_capital / premarket)`; **MARKET** orders only when qty changes.
3. **Logging** — `PREMARKET_LIMIT_PROXY_LOG` when converting LIMIT proxy orders.

**Not planned:** LIMIT @ pre-market at 9:05 (rejected — conflicts with reliable capital deployment on gap-up days).

Operator-facing LIMIT vs MARKET and slippage: [Operator FAQ](#operator-faq-morning-buys-limit-market-and-slippage).

---

## Operator FAQ: morning buys, LIMIT, MARKET, and slippage

Quick reference for operators and QA. Full scheduler flow: [Morning buy flow](#morning-buy-flow-901--905--915).

### Why two order types in one morning?

| Time | Order type | Why |
|------|------------|-----|
| **9:01** | **LIMIT @ signal close** | Pre-market LTP is not used for MARKET placement yet. Close is a **proxy** to place a pending order and size qty. |
| **9:05** (target) | **MARKET** | Pre-market LTP is available. Resize qty for assigned capital and **finalize for open fill** — close proxy is obsolete. |
| **9:15** | Broker fills **MARKET** | Execution at the **opening auction / first trades**, usually **near** 9:05 pre-market (not guaranteed identical). |

**9:01 LIMIT is not “never pay above ₹X.”** It is “we don’t have today’s price yet.”

### What is slippage here?

**Slippage** = difference between a **reference price** and the **price you actually get**.

Three references matter:

| Reference | Example |
|-----------|---------|
| Signal close (9:01 proxy) | ₹100 |
| Pre-market LTP (9:05) | ₹105 |
| Open fill (9:15 MARKET) | ₹108 |

- Slippage vs **close**: ₹108 − ₹100 = ₹8 (often a **gap-up**, not bad broker execution).
- Slippage vs **premarket**: ₹108 − ₹105 = ₹3 (9:05 → 9:15 gap).

**MARKET does not create the gap-up** — it **accepts the open** so you **fill**. **LIMIT** can **avoid** paying above a cap by **not filling at all**.

### LIMIT vs MARKET after 9:05 (pros and cons)

| | **MARKET** (recommended at 9:05) | **Keep LIMIT @ close** | **LIMIT @ pre-market** (not planned) |
|---|----------------------------------|-------------------------|----------------------------------------|
| **Primary goal** | Deploy ~assigned capital | Cap price at yesterday’s close | Cap price near pre-market |
| **Fill at open** | High (normal liquidity) | Low if open > limit | Low if open > limit |
| **Price vs 9:05 premarket** | Usually close; can gap to open | N/A if no fill | Capped; may not trade |
| **Capital deployed on gap-up** | ~Yes (~₹2L) | Often **₹0** | Often **₹0** |
| **Worst case** | Pay above premarket if open gaps | Miss the trade entirely | Miss the trade entirely |

### Example (₹2L capital, close ₹100, premarket ₹105, open ₹108)

| 9:05 choice | Qty | Fills at open? | ~Deployed |
|-------------|-----|----------------|-----------|
| Stay **LIMIT @ ₹100** | 2000 | **No** | **₹0** |
| **MARKET** | 1904 | **Yes** | **~₹2.06L** @ ~₹108 |
| **LIMIT @ ₹105** (not planned) | 1904 | **No** | **₹0** |

For **“invest my assigned capital today,”** **MARKET** is the aligned choice.

### How much slippage should we expect with MARKET?

| Situation | Typical size | Notes |
|-----------|--------------|--------|
| 9:05 premarket → 9:15 open (liquid largecaps) | **Small** (often &lt; 1–2%) | Normal days |
| Same (volatile / news) | **Larger** | Open can jump past premarket |
| Fill price vs **yesterday close** on gap-up day | **Large** | Real market move; LIMIT @ close would not have filled |

**MARKET guarantees an attempt to fill at the market — not a guarantee of the 9:05 premarket price.** EMA9 cancel at 9:05 is the strategy guardrail when the gap vs entry target is too large.

### Decision rule

| Priority | After 9:05 use |
|----------|----------------|
| Deploy ~assigned capital at today’s session | **MARKET** |
| Never pay above a fixed price | **LIMIT** (accept missed fills) |
| Both on a gap-up day | **Not possible** — choose capital **or** price cap |

### 9:05 behavior summary

| Order at 9:01 | Qty at 9:05 | Action |
|---------------|-------------|--------|
| **LIMIT** @ close | Any | → **MARKET** finalize |
| **MARKET** | Changed | → **MARKET** finalize (new qty) |
| **MARKET** | Unchanged | No modify |
| Capital for qty | | `execution_capital` (liquidity-aware) |

---

### Market hours (9:15–15:30)

#### Sell monitor (9:15–15:30, continuous)
**Task**: `run_sell_monitor()`

Places EMA9 limit sells at first run, then monitors RSI exit / fills.

**Paper trading:** Unexecuted DAY sell limits are cancelled at **EOD (18:00)**. The next **9:15** `sell_monitor` run cancels any leftovers and places fresh limits at the **latest EMA9** for each holding (re-entry qty updates during the session use `_update_sell_order_quantity`).

---

## Configuration

- **Schedules**: `service_schedules` table (defaults in `IndividualServiceManager._ensure_default_schedules()`).
- **Pending buy adjustment**: `enable_premarket_amo_adjustment` in user trading config (name retained for compatibility).
- **Migration**: `alembic/versions/20260520_morning_buy_schedule_margin_preview.py` updates existing deployments.

---

## AMO deprecation note

Evening **16:05 `buy_orders` (AMO)** is replaced by **`buy_margin_preview`**. Morning **`buy_orders` at 9:01** uses **REGULAR** variety when `is_market_hours()` is true. Kotak AMO at 16:05 is no longer the default path.

**Paper trading:** The multi-user paper scheduler does **not** call `execute_amo_orders_at_market_open()` at 9:15. Stale simulator AMO buys from the old evening path are logged at 9:01 and must be cancelled or executed manually; unit tests may still call `execute_amo_orders_at_market_open()` directly.

**Log labels:** `TASK:` banners in `run_trading_service.py` and `paper_trading_service_adapter.py` use the default IST times above (e.g. 9:03 retry, 18:00 EOD). Custom `service_schedules` may differ; grep logs by `action=` field when in doubt.
