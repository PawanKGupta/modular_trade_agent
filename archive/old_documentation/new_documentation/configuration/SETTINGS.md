# Configuration and Settings

This project supports configuration via environment variables (.env files) and Python constants.

Where to put secrets/keys
- Telegram: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in cred.env (preferred) or .env at repo root; core.telegram auto-loads cred.env and config/.env.
- Kotak Neo: set broker creds in modules/kotak_neo_auto_trader/kotak_neo.env and pass with --env when running unified service.

Global settings (config/settings.py)
- MIN_ABSOLUTE_AVG_VOLUME (env, default 20000): Minimum 20-day avg volume to consider a symbol liquid (lowered to minimal safety net).
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

Chart Quality Settings (config/strategy_config.py)
- CHART_QUALITY_ENABLED (env, default true): Enable/disable chart quality filtering.
- CHART_QUALITY_MIN_SCORE (env, default 60.0): Minimum chart quality score (0-100) for acceptance.
- CHART_QUALITY_MAX_GAP_FREQUENCY (env, default 20.0): Maximum gap frequency (%) before filtering.
- CHART_QUALITY_MIN_DAILY_RANGE_PCT (env, default 1.5): Minimum daily range (%) to avoid flat charts.
- CHART_QUALITY_MAX_EXTREME_CANDLE_FREQUENCY (env, default 15.0): Maximum extreme candle frequency (%) before filtering.
- CHART_QUALITY_ENABLED_IN_BACKTEST (env, default true): Enable chart quality filtering in backtests.

Capital & Liquidity Settings (config/strategy_config.py)
- USER_CAPITAL (env, default 200000.0): User's configured capital per trade (₹200,000 = 2L).
- MAX_POSITION_VOLUME_RATIO (env, default 0.10): Maximum position size as % of daily volume (10% default).
- MIN_ABSOLUTE_AVG_VOLUME (env, default 20000): Minimum average volume for minimal safety net.

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
- CAPITAL_PER_TRADE (default 100000) — Note: This is overridden by execution_capital from analysis CSV
- MIN_COMBINED_SCORE (default 25) — from analysis CSV to accept entries
- DEFAULT_EXCHANGE (NSE), DEFAULT_PRODUCT (CNC), DEFAULT_VARIETY (AMO)

Note: The auto trader now uses `execution_capital` from the analysis CSV, which is automatically calculated based on stock liquidity. If `execution_capital` is not available, it falls back to `CAPITAL_PER_TRADE`.

How to override
- Create a .env in repo root for global settings:
  ```env
  MIN_ABSOLUTE_AVG_VOLUME=20000
  NEWS_SENTIMENT_ENABLED=false
  RETRY_MAX_ATTEMPTS=5
  
  # Chart Quality Settings
  CHART_QUALITY_ENABLED=true
  CHART_QUALITY_MIN_SCORE=60.0
  CHART_QUALITY_MAX_GAP_FREQUENCY=20.0
  CHART_QUALITY_MIN_DAILY_RANGE_PCT=1.5
  CHART_QUALITY_MAX_EXTREME_CANDLE_FREQUENCY=15.0
  CHART_QUALITY_ENABLED_IN_BACKTEST=true
  
  # Capital & Liquidity Settings
  USER_CAPITAL=200000.0
  MAX_POSITION_VOLUME_RATIO=0.10
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
