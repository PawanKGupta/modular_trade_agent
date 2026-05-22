# Bulk analysis reliability (Phase 0)

## Overview

Overnight and large ChartInk bulk runs (`python trade_agent.py --backtest`) should stay on the **full quality path**:

- **Integrated** backtest (`run_integrated_backtest`)
- **Full** `AnalysisService.analyze_ticker` per historical signal (MTF, fundamentals, news when enabled in config)
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

## Later phases

Phase 1+ adds Postgres OHLCV cache, gap-fill, and chunked resumable jobs. This document stays the operator entry point for bulk reliability settings.
