import math
import yfinance as yf
from core.data_fetcher import fetch_ohlcv_yf
from core.indicators import compute_indicators
from core.patterns import is_hammer, is_bullish_engulfing, bullish_divergence
from config.settings import RSI_OVERSOLD, MIN_VOLUME_MULTIPLIER, VOLUME_MULTIPLIER_FOR_STRONG
from utils.logger import logger

def avg_volume(df, lookback=20):
    return df['volume'].tail(lookback).mean()

def analyze_ticker(ticker):
    try:
        logger.debug(f"Starting analysis for {ticker}")
        
        # Fetch OHLCV data with retry/circuit breaker
        df = fetch_ohlcv_yf(ticker)
        if df is None or df.empty:
            logger.warning(f"No data available for {ticker}")
            return {"ticker": ticker, "status": "no_data"}

        # Compute technical indicators
        df = compute_indicators(df)
        if df is None or df.empty:
            logger.error(f"Failed to compute indicators for {ticker}")
            return {"ticker": ticker, "status": "indicator_error"}
            
    except Exception as e:
        logger.error(f"Data fetching/processing failed for {ticker}: {type(e).__name__}: {e}")
        return {"ticker": ticker, "status": "data_error", "error": str(e)}

    try:
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else None
    except (IndexError, KeyError) as e:
        logger.error(f"Error accessing data rows for {ticker}: {e}")
        return {"ticker": ticker, "status": "data_access_error"}

    signals = []

    if is_hammer(last):
        signals.append("hammer")

    if prev is not None and is_bullish_engulfing(prev, last):
        signals.append("bullish_engulfing")

    if last['rsi14'] is not None and last['rsi14'] < RSI_OVERSOLD:
        signals.append("rsi_oversold")

    if bullish_divergence(df):
        signals.append("bullish_divergence")

    avg_vol = avg_volume(df, 20)
    vol_ok = last['volume'] >= avg_vol * MIN_VOLUME_MULTIPLIER
    vol_strong = last['volume'] >= avg_vol * VOLUME_MULTIPLIER_FOR_STRONG

    recent_low = df['low'].tail(20).min()
    recent_high = df['high'].tail(20).max()

    try:
        logger.debug(f"Fetching fundamental data for {ticker}")
        info = yf.Ticker(ticker).info
        pe = info.get('trailingPE', None)
        pb = info.get('priceToBook', None)
        logger.debug(f"Fundamental data for {ticker}: PE={pe}, PB={pb}")
    except Exception as e:
        logger.warning(f"Could not fetch fundamental data for {ticker}: {e}")
        pe = None
        pb = None

    verdict = "avoid"
    justification = []

    if (("bullish_engulfing" in signals or "hammer" in signals or "bullish_divergence" in signals or "rsi_oversold" in signals)
        and vol_ok):
        if not (pe is not None and pe < 0):
            verdict = "buy"
            justification.append("pattern:" + ",".join(signals))
            if vol_strong:
                justification.append("volume_strong")
            if last['rsi14'] is not None:
                justification.append(f"rsi:{round(last['rsi14'],1)}")
        else:
            verdict = "watch"
            justification.append("fundamental_red_flag")
    elif len(signals) > 0:
        verdict = "watch"
        justification.append("signals:" + ",".join(signals))
    else:
        verdict = "avoid"

    buy_range = None
    target = None
    stop = None

    if verdict == "buy":
        current_price = last['close']
        stop = round(min(recent_low * 0.995, current_price * 0.92), 2)
        risk_pct = (current_price - stop) / current_price
        target = round(current_price * (1 + max(0.08, risk_pct * 2)), 2)
        buy_range = (round(current_price * 0.995, 2), round(current_price * 1.01, 2))

    # Final result compilation with error handling
    try:
        rsi_value = None if math.isnan(last['rsi14']) else round(last['rsi14'], 2)
        
        result = {
            "ticker": ticker,
            "verdict": verdict,
            "signals": signals,
            "rsi": rsi_value,
            "avg_vol": int(avg_vol),
            "today_vol": int(last['volume']),
            "pe": pe,
            "pb": pb,
            "buy_range": buy_range,
            "target": target,
            "stop": stop,
            "justification": justification,
            "last_close": round(last['close'], 2),
            "status": "success"
        }
        
        logger.debug(f"Analysis completed successfully for {ticker}: {verdict}")
        return result
        
    except Exception as e:
        logger.error(f"Error compiling final results for {ticker}: {e}")
        return {"ticker": ticker, "status": "result_compilation_error", "error": str(e)}

    except Exception as e:
        logger.error(f"Unexpected error in analyze_ticker for {ticker}: {type(e).__name__}: {e}")
        return {"ticker": ticker, "status": "analysis_error", "error": str(e)}
