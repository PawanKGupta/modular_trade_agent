# Bulk analysis reliability (Phase 0)

## Overview

Overnight and large ChartInk bulk runs (`python trade_agent.py --backtest`) should stay on the **full quality path**:

- **Integrated** backtest (`run_integrated_backtest`)
- **Full** `AnalysisService.analyze_ticker` per historical signal (MTF, fundamentals, news when enabled in config). News uses **`NEWS_BACKTEST_PROFILE`** (default `cheap`); see **Composite news profiles** and the backtest lookahead caveat in [`TRADING_CONFIG.md`](TRADING_CONFIG.md#7-news-sentiment).
- No switching to simple backtest for speed

Speed is controlled only via **environment** (concurrency, delays), not by skipping analysis steps.

## Reliability profile

Copy the **two required** lines from [`config/bulk_reliability.env.example`](../../config/bulk_reliability.env.example) into your project `.env`:

| Variable | Bulk value | App default | Purpose |
|----------|------------|-------------|---------|
| `MAX_CONCURRENT_ANALYSES` | `1` | `5` | Fewer parallel Yahoo calls |
| `API_RATE_LIMIT_DELAY` | `2.0` | `1.0` | Seconds between OHLCV/fundamental fetches |

Optional (commented in the example file): looser circuit breaker if long runs trip Yahoo; `BULK_BACKTEST_FALLBACK_TO_SIMPLE`, validator strictness, ML training path guard.

See also [Rate limiting configuration](../features/RATE_LIMITING_CONFIGURATION.md).

## Backtest engine labels

Each row in `analysis_results/bulk_analysis_final_*.csv` includes **`backtest_mode`**:

| Value | Meaning |
|-------|---------|
| `integrated` | Integrated backtest completed for that symbol |
| `simple` | Only simple backtest (integrated module unavailable at import) |
| `simple_fallback` | Integrated failed; simple backtest used instead |
| `failed` | Integrated failed and `BULK_BACKTEST_FALLBACK_TO_SIMPLE=false` |

Startup logs print **available** engine (`integrated` vs `simple` at import) plus current `MAX_CONCURRENT_ANALYSES` and `API_RATE_LIMIT_DELAY`.

### ML training

`backtest_mode` and other bulk-export metadata columns are **not** used as sklearn features. See `services/ml_training_metadata.py` (`BULK_ANALYSIS_CSV_METADATA`, `select_training_feature_columns`). Safe to add operator columns to `bulk_analysis_final_*.csv` without retraining manifests.

**Note:** Admin ML training (`POST /api/v1/admin/ml/train`) **rejects** paths that look like `bulk_analysis_final_*.csv` (HTTP 400) unless `ML_ALLOW_BULK_ANALYSIS_TRAINING_CSV=true` for experiments. Use position/episode datasets (e.g. `data/ml_training_data.csv`). Metadata columns are still stripped if a bulk file is forced through.

### Strict integrated-only runs

```bash
BULK_BACKTEST_FALLBACK_TO_SIMPLE=false
```

Symbols that fail integrated backtest get `backtest_mode=failed` and score 0 instead of a silent simple fallback.

## Validate output CSV

```bash
.venv\Scripts\python.exe tools\validate_bulk_analysis_final.py
.venv\Scripts\python.exe tools/validate_bulk_analysis_final.py analysis_results/bulk_analysis_final_YYYYMMDD_HHMMSS.csv
```

Optional strict check (fail if any `simple_fallback`):

```bash
set BULK_EXPECT_INTEGRATED_BACKTEST=true
.venv\Scripts\python.exe tools/validate_bulk_analysis_final.py
```

## Run command

```bash
# From repo root with .venv activated; merge bulk_reliability.env.example into .env first
python trade_agent.py --backtest
```

## Web UI analysis

Dashboard **Analysis** (individual service `run_once` / scheduler) runs the same subprocess as CLI:

```text
python trade_agent.py --backtest --json-output analysis_results/latest_results.json
```

with `TRADE_AGENT_USER_ID` set to the logged-in user. Trading settings from the DB drive analysis (`ml_enabled`, thresholds, chart quality, etc.); the job does **not** pass CLI `--ml`. See [COMMANDS.md](../reference/COMMANDS.md) for CLI `--ml` vs user config.

**Server requirement:** The API process must use the same `DB_URL` (and `alembic upgrade head`) as your OHLCV cache. The subprocess inherits the server environment; if the server still uses default SQLite while you warm Postgres from a manual shell, UI runs will not share that cache.

## Postgres / SQLite OHLCV cache

Persistent cache (`price_cache`, `ohlcv_symbol_meta`, `corporate_actions`) avoids re-downloading full history on repeat bulk runs. **Daily `1d` bars** are filled from **NSE UDiFF bhavcopy** when `OHLCV_DAILY_SOURCE=nse` (default). Yahoo is still used for **weekly `1wk`**, **intraday `1m`**, corporate-action sync, and optional rollback (`OHLCV_DAILY_SOURCE=yahoo` or `nse_with_yahoo_fallback`). Gap-fill runs when **coverage** in the requested window is below `OHLCV_CACHE_MIN_COVERAGE_PCT` (default 85%) or the **tail** lacks bars (last ~10 trading days for `1d`, last ~3 weeks for `1wk`). **Listing-aware coverage:** expected bars are counted from `max(requested_start, first cached bar in range)` (and `ohlcv_symbol_meta.first_date` when the window is empty), so young listings are not treated as permanently incomplete versus a 5y lookback. Interior holiday holes that the vendor never returns do not force a refetch once coverage is adequate. Weekly bars use **ISO week** matching (±4 calendar days) so Yahoo week stamps align with cache without refetching. NSE daily closes align with TradingView RSI/EMA inputs; `price_cache.source` is `nse` for those rows.

**Correctness check** (field-by-field O/H/L/C/V on every bar vs Yahoo):

```bash
.venv\Scripts\python.exe tools\compare_yahoo_cache_ohlcv.py PFOCUS.NS --days 400
```

The tool compares **open, high, low, close, volume** on each common bar date (`dates × 5` scalar checks) for Yahoo vs Postgres and vs `fetch_ohlcv_yf()` return values.

| Setting | Default | Purpose |
|---------|---------|---------|
| `OHLCV_CACHE_ENABLED` | `true` when `DB_URL` set | Toggle read-through cache in `fetch_ohlcv_yf` |
| `OHLCV_DAILY_SOURCE` | `nse` | Daily gap-fill: `nse`, `yahoo`, or `nse_with_yahoo_fallback` |
| `NSE_BHAVCOPY_CACHE_DIR` | `.cache/nse_bhavcopy` | On-disk cache of downloaded bhavcopy CSV zips |
| `NSE_BHAVCOPY_REQUEST_DELAY_S` | `0.15` | Pause between NSE archive HTTP requests |
| `OHLCV_CACHE_TAIL_OVERLAP_TRADING_DAYS` | `10` | Tail refresh window |
| `OHLCV_CACHE_MIN_COVERAGE_PCT` | `85` | Health gate coverage threshold |
| `OHLCV_CACHE_DEBUG` | `false` | INFO logs for `cache_hit` / `gap_fill` (or `trade_agent --ohlcv-cache-debug`) |
| `OHLCV_REJECT_INVALID_FETCH` | `true` | Do not upsert when ingest validation fails |
| `OHLCV_MIN_DAILY_BARS_FOR_INDICATORS` | `250` | Warn when `partial` cache has fewer daily bars (EMA200 safety) |

**Ingest validation:** Each `gap_fill` validates the OHLCV frame (non-empty, valid OHLCV, no duplicate dates) and stores `fetch_status` (`ok` / `partial` / `failed`) on `ohlcv_symbol_meta`. Failed fetches are not written to cache; `get_ohlcv` returns nothing when `fetch_status=failed` so indicators are not run on corrupt data.

**NSE backfill** (run after deploy or when switching from Yahoo-backed cache):

```bash
.venv/bin/python tools/nse_bhavcopy_backfill.py backfill-symbol DMART.NS --days 500
.venv/bin/python tools/nse_bhavcopy_backfill.py backfill-dates --from 2024-07-08 --to 2026-06-02 --symbols DMART.NS,LINDEINDIA.NS
.venv/bin/python tools/ohlcv_cache_admin.py nse-gap-fill RELIANCE.NS --days 500
```

**RSI pilot** (NSE vs Yahoo vs TradingView, no DB):

```bash
.venv/bin/python tools/nse_rsi_pilot.py --symbols DMART LINDEINDIA AXISCADES
```

**Hardening (post listing-aware coverage):**

- `invalidate_symbol` resets `ohlcv_symbol_meta` (`fetch_status=unknown`, zero counts).
- On `cache_hit`, stale `partial` meta is re-validated when listing-aware coverage ≥ `OHLCV_CACHE_MIN_COVERAGE_PCT`.
- Daily `get_ohlcv` returns nothing when `OHLCV_ENFORCE_INDICATOR_MIN_BARS=true` and the window has fewer than `OHLCV_MIN_DAILY_BARS_FOR_INDICATORS` bars **and** listing age &lt; `OHLCV_MIN_LISTING_YEARS_FOR_INDICATORS` years.
- If ≥ `OHLCV_LISTING_START_GAP_MIN_MISSING` trading days are missing between `ohlcv_symbol_meta.first_date` and the earliest cached bar (first N days of the listing window), one gap-fill is triggered. Uses calendar coverage 85–95% **or** listing-aware coverage already ≥ threshold.

**Admin CLI** (health, gap-fill, invalidate, preload):

```bash
.venv\Scripts\python.exe tools\ohlcv_cache_admin.py health RELIANCE.NS
.venv\Scripts\python.exe tools\ohlcv_cache_admin.py gap-fill RELIANCE.NS --days 400
```

**Chunked overnight job** (DB checkpoint + resume):

```bash
.venv\Scripts\python.exe tools\bulk_analysis_job.py --chunk-size 25 --chartink
.venv\Scripts\python.exe tools\bulk_analysis_job.py --resume 3 --repair-cache
```

Optional CSV columns (ops only, excluded from ML features): `cache_health_status`, `yahoo_calls`. Set by `src/application/services/ohlcv_bulk_ops.py` on `trade_agent.py --backtest`, async/sequential analysis + backtest, and `tools/bulk_analysis_job.py`.

| Column | Meaning |
|--------|---------|
| `cache_health_status` | `assess_price_cache_health` over ~5y (`healthy`, `partial`, `empty`, `disabled`, `unknown`), or bulk job override `skipped` when `--repair-cache` is off |
| `yahoo_calls` | Per-symbol Yahoo fetches: analysis phase + backtest phase (since last per-symbol counter reset), not a run-wide cumulative total |

**ML on/off** does not change caching: OHLCV still flows through `fetch_ohlcv_yf` read-through cache. ML only affects verdict/backtest scoring and buyable filtering (user `ml_enabled` from Trading config, or CLI `--ml` when no `TRADE_AGENT_USER_ID` config loads).

Apply schema (both revisions):

```bash
alembic upgrade head
```

- `20260522_ohlcv` — `price_cache`, `ohlcv_symbol_meta`, `corporate_actions`, bulk job tables
- `20260523_ohlcv_meta` — `fetch_status` / ingest metadata on `ohlcv_symbol_meta`
