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
| **18:00** | `eod_cleanup` | End-of-day reset |

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

**Purpose**: Place **REGULAR** buys when the session is open (pre-open from 9:00 IST in code).

**Flow**:
1. Load buy recommendations from `signals`.
2. Portfolio limits, margin check, `place_new_entries()`.
3. `place_reentry_orders()` in the same task.

**Note**: Requires prior-day (or same-day) analysis signals.

#### Pre-market retry (9:03 / configurable)
**Task**: `run_premarket_retry()`

Retries **FAILED** / insufficient-balance orders from the database (after morning placement).

#### Pre-market pending buy adjustment (9:05)
**Task**: `run_premarket_amo_adjustment()`

**Purpose**: Adjust open **pending BUY** orders (AMO or REGULAR) using pre-market prices when `enable_premarket_amo_adjustment` is on.

**Key operations**:
- `engine.adjust_amo_quantities_premarket()`
- Broker modify for qty changes; EMA9 cancel logic for re-entries

---

### Market hours (9:15–15:30)

#### Sell monitor (9:15–15:30, continuous)
**Task**: `run_sell_monitor()`

Places EMA9 limit sells at first run, then monitors RSI exit / fills.

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
