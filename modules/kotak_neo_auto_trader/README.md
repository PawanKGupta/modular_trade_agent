# kotak_neo_auto_trader (AMO Executor)

Execution-only module for placing AMO BUY orders on Kotak Neo using the final stock list produced by trade_agent + backtest.

Key capabilities:
- Reads the final, post-scored CSV from trade_agent (`analysis_results/bulk_analysis_final_*.csv`)
- Filters strictly: `final_verdict` in {`buy`,`strong_buy`} AND `combined_score` ≥ `MIN_COMBINED_SCORE`
- Sizing: `qty = floor(CAPITAL_PER_TRADE / close)` with affordability check via account limits
- Pre-checks per symbol:
  - Skip if already in holdings
  - Cancel any pending BUY order (variants: `-EQ`, `-BE`, `-BL`, `-BZ`) and place a fresh AMO order
  - If funds insufficient, send a Telegram notification with required/available/shortfall
- Session cache: reuses daily session token from `modules/kotak_neo_auto_trader/session_cache.json`
- GTT is not supported and is disabled

## Flow

1) Generate recommendations (with backtest scoring):
```
.venv\Scripts\python.exe trade_agent.py --backtest
```
This writes `analysis_results/bulk_analysis_final_<timestamp>.csv` (includes `final_verdict` and `combined_score`).

2) Place AMO orders from the final CSV:
```
.venv\Scripts\python.exe -m modules.kotak_neo_auto_trader.run_place_amo \
  --env modules\kotak_neo_auto_trader\kotak_neo.env \
  --csv analysis_results\bulk_analysis_final_*.csv
```
- Omit `--csv` to auto-pick the newest file in `analysis_results/`.

## Configuration
Edit `modules/kotak_neo_auto_trader/config.py`:
- `CAPITAL_PER_TRADE` (default 100000)
- `MAX_PORTFOLIO_SIZE` (default 6)
- `MIN_QTY` (default 1)
- `DEFAULT_EXCHANGE` (`NSE`), `DEFAULT_PRODUCT` (`CNC`), `DEFAULT_VARIETY` (`AMO`)
- `MIN_COMBINED_SCORE` (default 25) — used when `final_verdict` exists in the CSV
- `ANALYSIS_DIR` (default `analysis_results`)

## Credentials
Create `modules/kotak_neo_auto_trader/kotak_neo.env` (do not commit):
```
KOTAK_CONSUMER_KEY=
KOTAK_CONSUMER_SECRET=
KOTAK_MOBILE_NUMBER=
KOTAK_PASSWORD=
# use one of the following for 2FA
KOTAK_TOTP_SECRET=
# or
KOTAK_MPIN=
KOTAK_ENVIRONMENT=prod
```
- A daily session token is cached at `modules/kotak_neo_auto_trader/session_cache.json` and reused automatically until EOD.

## Notes
- This module does not run analysis or backtests; it trusts the CSV from trade_agent.
- GTT is not supported by this integration (AMO MARKET/LIMIT only).
- If account `limits` call shows insufficient funds, the order is skipped and a Telegram alert is sent (configure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`).
