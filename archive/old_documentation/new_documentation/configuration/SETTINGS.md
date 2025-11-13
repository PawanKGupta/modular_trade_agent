# Configuration and Settings

This project supports configuration via environment variables (.env files) and Python constants.

Where to put secrets/keys
- Telegram: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in cred.env (preferred) or .env at repo root; core.telegram auto-loads cred.env and config/.env.
- Kotak Neo: set broker creds in modules/kotak_neo_auto_trader/kotak_neo.env and pass with --env when running unified service.

Global settings (config/settings.py)
- MIN_ABSOLUTE_AVG_VOLUME (env, default 150000): Minimum 20-day avg volume to consider a symbol liquid.
- NEWS_SENTIMENT_ENABLED (env, default true): Toggle news sentiment filter.
- NEWS_SENTIMENT_LOOKBACK_DAYS (env, default 30): News window for sentiment aggregation.
- NEWS_SENTIMENT_MIN_ARTICLES (env, default 2): Minimum articles required to score sentiment.
- NEWS_SENTIMENT_POS_THRESHOLD (env, default 0.25): Positive sentiment threshold.
- NEWS_SENTIMENT_NEG_THRESHOLD (env, default -0.25): Negative sentiment threshold.
- NEWS_SENTIMENT_CACHE_TTL_SEC (env, default 900): Cache TTL for news fetch.
- RETRY_MAX_ATTEMPTS (env, default 3): Max retries for transient operations.
- RETRY_BASE_DELAY (env, default 1.0): Initial delay for backoff.
- RETRY_MAX_DELAY (env, default 30.0): Max delay for backoff.
- RETRY_BACKOFF_MULTIPLIER (env, default 2.0): Exponential backoff factor.
- CIRCUITBREAKER_FAILURE_THRESHOLD (env, default 3): Trip threshold.
- CIRCUITBREAKER_RECOVERY_TIMEOUT (env, default 60.0): Half-open after seconds.

Other strategy constants (code defaults)
- RSI_OVERSOLD=30, RSI_NEAR_OVERSOLD=40
- VOLUME_INTRADAY_MULTIPLIER=0.6, VOLUME_QUALITY_* tiers
- POSITION_VOLUME_RATIO_TIERS: filters extreme illiquidity by price bands

Telegram config (env)
- TELEGRAM_BOT_TOKEN: Bot token
- TELEGRAM_CHAT_ID: Chat ID to receive alerts

Broker configuration (modules/kotak_neo_auto_trader/kotak_neo.env)
- KOTAK_CONSUMER_KEY, KOTAK_CONSUMER_SECRET
- KOTAK_MOBILE_NUMBER, KOTAK_PASSWORD, KOTAK_MPIN
- Optional: KOTAK_ENVIRONMENT=prod|uat

Auto Trader module settings (modules/kotak_neo_auto_trader/config.py)
- MAX_PORTFOLIO_SIZE (default 6)
- CAPITAL_PER_TRADE (default 100000)
- MIN_COMBINED_SCORE (default 25) — from analysis CSV to accept entries
- DEFAULT_EXCHANGE (NSE), DEFAULT_PRODUCT (CNC), DEFAULT_VARIETY (AMO)

How to override
- Create a .env in repo root for global settings:
  ```env
  MIN_ABSOLUTE_AVG_VOLUME=200000
  NEWS_SENTIMENT_ENABLED=false
  RETRY_MAX_ATTEMPTS=5
  ```
- Put Telegram in cred.env (or .env):
  ```env
  TELEGRAM_BOT_TOKEN=123:ABC
  TELEGRAM_CHAT_ID=123456789
  ```
- Keep broker creds in modules/kotak_neo_auto_trader/kotak_neo.env and pass with --env.

Validate
```powershell
.\.venv\Scripts\python.exe -c "import os;print(os.getenv('MIN_ABSOLUTE_AVG_VOLUME'))"
.\.venv\Scripts\python.exe -c "from core.telegram import send_telegram; send_telegram('Config test OK')"
```
