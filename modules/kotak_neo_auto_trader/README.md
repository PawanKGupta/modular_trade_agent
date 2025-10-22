# kotak_neo_auto_trader

Separate module to:
- Read buy signals from a CSV
- Auto-place BUY orders when LTP is within range
- Auto-SELL when price reaches EMA(9)
- Limit to max 6 open positions
- Allocate 100,000 currency units per trade

## CSV format

Expected headers in `signals.csv`:

```
symbol,price_min,price_max[,note]
```

Example:

```
symbol,price_min,price_max,note
TCS,3500,3600,example signal
RELIANCE,2400,2450,example signal
```

## Configure

Edit `modules/kotak_neo_auto_trader/config.py` for:
- `capital_per_trade` (default 100,000)
- `max_open_positions` (default 6)
- `ema_period` (default 9)
- `poll_interval_seconds` (default 5)
- `exchange`, `product`, `order_type_default`

Set environment variables for Kotak Neo credentials:
- `KOTAK_NEO_API_KEY`
- `KOTAK_NEO_ACCESS_TOKEN`
- `KOTAK_NEO_USER_ID`

Replace API endpoints in `client/kotak_neo_client.py` with official SDK/REST calls.

## Mock/Paper demo

```
python -m modules.kotak_neo_auto_trader.run_mock_demo
```

This uses an in-memory mock to simulate LTP, trigger a BUY within the CSV range, and then exit on EMA(9).

## Run (real, SDK)

1) Install dependencies:
```
pip install neo_api_client pyotp
```

2) Export env vars (replace with your values):
- NEO_CONSUMER_KEY
- NEO_CONSUMER_SECRET
- NEO_ENV=uat or prod

Optional login via env (if you don’t have a persisted token):
- NEO_MOBILE
- NEO_PASSWORD
- NEO_OTP

Or use a .env file (recommended):
- Copy `.env.example` to `.env` and fill values (keep `.env` out of git)
- The runner will auto-load `.env` if present

3) Run:
```
python -m modules.kotak_neo_auto_trader.run_auto_trader_sdk
```

This uses `KotakNeoSDKClient`, logs in if env creds are present/.env exists, and parses CSV symbols like `RELIANCE.NS` to `RELIANCE` on `NSE`.
