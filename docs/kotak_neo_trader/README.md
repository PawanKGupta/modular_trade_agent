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
.venv\\Scripts\\python.exe -m modules.kotak_neo_auto_trader.run_place_amo \\
  --csv analysis_results\\bulk_analysis_final_*.csv
```
- **Note**: Credentials are loaded from database (configured via web UI)
- Sessions are kept by default; add `--logout` if you want to end the session.
- Omit `--csv` to auto-pick the newest file in `analysis_results/`.

## Configuration
Edit `modules/kotak_neo_auto_trader/config.py`:
- `CAPITAL_PER_TRADE` (default 100000)
- `MAX_PORTFOLIO_SIZE` (default 6)
- `MIN_QTY` (default 1)
- `DEFAULT_EXCHANGE` (`NSE`), `DEFAULT_PRODUCT` (`CNC`), `DEFAULT_VARIETY` (`AMO`)
- `MIN_COMBINED_SCORE` (default 25) — used when `final_verdict` exists in the CSV
- `ANALYSIS_DIR` (default `analysis_results`)

## Static IP whitelisting (Neo Trade API order APIs)

Kotak Neo **enforces static IP rules on order execution APIs** (place, modify, cancel). Login, reports, portfolio, and many data calls can work from any network; **orders will fail** if the egress IP is wrong or the session was not created from the whitelisted path.

**Canonical broker documentation:** [Static IP whitelisting for retail algo trading](https://www.kotakneo.com/platform/kotak-neo-trade-api/static-ip-details/) (Kotak Neo).

### What you will see

- Requests from a **non-whitelisted** public IP typically return **`stCode: 100008`**, **`errMsg: unauthorized`**, **`stat: Not_Ok`** on place/modify/cancel.
- This repo does **not** bypass or override that check; it is enforced at Kotak’s gateway.

### What to configure

1. **Whitelist the IPv4 address that Kotak sees** when your process calls their API (not necessarily your LAN IP). In the Neo app: **More → Trade API → Add IP** (primary; optional secondary per Kotak limits).
2. **Run the trade agent / API worker from that same egress IP** — e.g. a cloud VM with a **reserved / elastic / static** public IP, or an ISP-provided fixed public IP if you always trade from one location.
3. **Create a new API session after IP changes** — session is bound to the IP used at login; place orders from the same environment Kotak documents as required.

### Verify egress IP

From the **same host** that will call Kotak (or the same outbound path), confirm the public IP (e.g. `https://api.ipify.org/` as suggested on Kotak’s page) and ensure it matches what you whitelisted.

### Cloud static IP example

If you deploy on Oracle Cloud, reserved public IPs are described in-repo under [`docker/ACCESS_UI.md`](../../docker/ACCESS_UI.md) (static IP subsection). Other clouds use their own “elastic” / “static external” IP products the same way.

### FAQ (per Kotak’s published page)

- **Delay after whitelisting:** Kotak states changes apply **immediately**; if orders still fail, retry after a **fresh login** from the whitelisted path and re-check `ipify` vs the Neo Trade API IP list.
- **Support:** use **support@kotakneo.com** from Kotak’s Trade API help if configuration looks correct but `100008` persists.

## Credentials

**⚠️ IMPORTANT: Credentials are now stored in the database via web UI (not in env files)**

### Setting Up Credentials

1. **Access Web UI**: Navigate to `http://localhost:5173` (or your deployment URL)
2. **Login**: Use your account credentials
3. **Go to Settings**: Click "Settings" in the sidebar
4. **Configure Broker Credentials**:
   - Enter your Kotak Neo credentials:
     - Consumer Key
     - Consumer Secret
     - Access Token
     - User ID
   - Click "Save"
   - Credentials are **encrypted** using Fernet (AES-128) before storage

### Security

- ✅ Credentials are **encrypted** before storage in database
- ✅ No plain text credentials in files
- ✅ Per-user credential storage (multi-user system)
- ✅ Encryption key managed via `APP_DATA_ENCRYPTION_KEY` environment variable

### Legacy Note

If you're using the standalone CLI scripts (not recommended), you may still need `kotak_neo.env` file, but the **recommended approach** is to use the web UI for credential management.

### Session Cache

- A daily session token is cached at `modules/kotak_neo_auto_trader/session_cache.json` and reused automatically until EOD.

### Dev broker smoke (check-margin / gated live AMO)

For local debugging against Kotak REST (credentials from `kotak_neo.env` or `--config` only — **never** commit secrets), see:

`modules/kotak_neo_auto_trader/dev_tests/kotak_broker_smoke.py`

- `check-margin` — prints request/response JSON and a short sufficiency summary (no order).
- `place-amo` — places a real market buy; requires **`KOTAK_ALLOW_LIVE_PLACE_ORDER=1`** and **`--confirm-live-order`** (qty capped at 10). If Kotak returns **`100008` / `unauthorized`**, confirm **Static IP whitelisting** above and a **fresh session** from that IP.

## Notes
- This module does not run analysis or backtests; it trusts the CSV from trade_agent.
- GTT is not supported by this integration (AMO MARKET/LIMIT only).
- If account `limits` call shows insufficient funds, the order is skipped and a Telegram alert is sent (configure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`).
