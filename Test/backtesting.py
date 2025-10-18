# save as nse_buy_signal_and_reversal_analysis_fixed.py
import time
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
from tqdm import tqdm
from textblob import TextBlob
import requests

INPUT_CSV = "nse_rsi10_lt30_gt_ema200_by_date.csv"
OUTPUT_CSV = "nse_buy_signal_with_reversal.csv"
LOOKAHEAD_DAYS = 30
NEWS_WINDOW_DAYS = 7

# ---- Helper functions ----
def compute_rsi(series, period=10):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rsi = 100 - (100 / (1 + (avg_gain / avg_loss)))
    return rsi

def compute_ema(series, span=200):
    return series.ewm(span=span, adjust=False).mean()

def is_hammer(row):
    """
    Detect hammer candlestick pattern:
    - Small real body (Open/Close difference)
    - Long lower shadow (at least 2x the real body)
    - Little to no upper shadow
    """
    try:
        open_price = float(row['Open'])
        high_price = float(row['High']) 
        low_price = float(row['Low'])
        close_price = float(row['Close'])
        
        # Real body size
        real_body = abs(close_price - open_price)
        
        # Shadow lengths
        lower_shadow = min(open_price, close_price) - low_price
        upper_shadow = high_price - max(open_price, close_price)
        
        # Total range
        total_range = high_price - low_price
        
        if total_range == 0:
            return False
            
        # Hammer criteria:
        # 1. Lower shadow at least 2x real body
        # 2. Real body is small (less than 1/3 of total range)
        # 3. Upper shadow is small (less than real body)
        return (
            lower_shadow >= 2 * real_body and
            real_body < total_range / 3 and
            upper_shadow <= real_body
        )
    except (ValueError, TypeError, KeyError):
        return False

def is_bullish_engulfing(current_row, prev_row):
    """
    Detect bullish engulfing pattern:
    - Previous candle is bearish (red)
    - Current candle is bullish (green) 
    - Current candle's body completely engulfs previous candle's body
    """
    try:
        # Previous candle
        prev_open = float(prev_row['Open'])
        prev_close = float(prev_row['Close'])
        
        # Current candle
        curr_open = float(current_row['Open'])
        curr_close = float(current_row['Close'])
        
        # Check if previous is bearish and current is bullish
        prev_bearish = prev_close < prev_open
        curr_bullish = curr_close > curr_open
        
        # Check if current engulfs previous
        engulfs = (curr_open < prev_close and curr_close > prev_open)
        
        return prev_bearish and curr_bullish and engulfs
    except (ValueError, TypeError, KeyError):
        return False

def find_optimal_buy_date_with_volume(data, signal_date, lookforward_days=5):
    """
    Find the best buy date after signal using volume and price analysis.
    Looks for:
    1. Volume spikes (capitulation selling)
    2. Price bottoming patterns
    3. Volume confirmation of reversal
    """
    try:
        signal_date = get_nearest_signal_date(data, signal_date)
        if signal_date is None:
            return signal_date, "No signal date", 0, 0, 0
            
        # Get data for next few days after signal
        future_data = data.loc[data.index > signal_date].head(lookforward_days)
        
        if future_data.empty:
            return signal_date, "No future data", 0, 0, 0
            
        # Calculate volume metrics
        recent_volume = data.tail(20)['Volume'].mean()  # 20-day avg volume
        
        best_buy_date = future_data.index[0]  # Default to next day
        best_reason = "Default next day"
        max_volume_ratio = 0
        lowest_price = float('inf')
        volume_spike_detected = False
        
        for date in future_data.index:
            row = future_data.loc[date]
            current_volume = float(row['Volume'])
            current_low = float(row['Low'])
            current_close = float(row['Close'])
            
            # Volume analysis
            volume_ratio = current_volume / recent_volume if recent_volume > 0 else 1
            
            # Look for high volume + lower price (capitulation)
            if volume_ratio >= 1.5 and current_low < lowest_price:
                best_buy_date = date
                best_reason = f"Volume spike {volume_ratio:.1f}x + price bottom"
                max_volume_ratio = volume_ratio
                lowest_price = current_low
                volume_spike_detected = True
            
            # Look for the lowest low with decent volume
            elif current_low < lowest_price and volume_ratio >= 0.8:
                best_buy_date = date
                best_reason = f"Lowest price with volume {volume_ratio:.1f}x"
                max_volume_ratio = volume_ratio
                lowest_price = current_low
        
        # Calculate the decline saved by waiting
        next_day_price = float(future_data.iloc[0]['Open'])
        optimal_buy_price = float(future_data.loc[best_buy_date, 'Open'])
        decline_saved = (next_day_price - optimal_buy_price) / next_day_price * 100
        
        return best_buy_date, best_reason, max_volume_ratio, decline_saved, optimal_buy_price
        
    except (ValueError, TypeError, KeyError, IndexError):
        return signal_date, "Error in analysis", 0, 0, 0

def calculate_price_decline_before_reversal(data, signal_date, lookback_days=20):
    """
    Calculate how much price fell from recent high before the reversal signal.
    Returns the percentage decline from the highest point in the lookback period.
    """
    try:
        signal_date = get_nearest_signal_date(data, signal_date)
        if signal_date is None:
            return 0
            
        # Get data from lookback period to signal date
        end_date = signal_date
        start_date = signal_date - pd.Timedelta(days=lookback_days)
        
        # Filter data for the lookback period
        lookback_data = data.loc[(data.index >= start_date) & (data.index <= end_date)]
        
        if lookback_data.empty or len(lookback_data) < 2:
            return 0
            
        # Find the highest high in the lookback period
        highest_high = lookback_data['High'].max()
        
        # Get the close price on signal date
        signal_close = float(data.at[signal_date, 'Close'])
        
        # Calculate decline percentage
        decline_pct = (highest_high - signal_close) / highest_high * 100
        
        return max(0, decline_pct)  # Return 0 if price didn't decline
        
    except (ValueError, TypeError, KeyError, IndexError):
        return 0

def check_bullish_divergence(data, current_idx, lookback=5):
    """
    Detect bullish divergence:
    - Price makes lower lows
    - RSI makes higher lows
    """
    try:
        if current_idx < lookback:
            return False
            
        # Get recent data
        recent_data = data.iloc[current_idx-lookback:current_idx+1]
        
        if len(recent_data) < 3:
            return False
            
        # Find local lows in price and RSI
        prices = recent_data['Low'].values
        rsi_values = recent_data['RSI10'].values
        
        # Check if we have valid RSI values
        if pd.isna(rsi_values).any():
            return False
            
        # Find the lowest price points
        price_min_idx = np.argmin(prices)
        current_price_low = prices[-1]  # Current low
        previous_price_low = prices[price_min_idx]
        
        # Find corresponding RSI values
        current_rsi = rsi_values[-1]
        previous_rsi = rsi_values[price_min_idx]
        
        # Bullish divergence: price lower low, RSI higher low
        return (current_price_low <= previous_price_low and 
                current_rsi > previous_rsi)
    except (ValueError, TypeError, IndexError):
        return False

def get_nearest_signal_date(data, target_date):
    """
    Returns the nearest future date in data.index >= target_date.
    Returns None if no such date exists.
    """
    target_date = pd.to_datetime(target_date).normalize()
    data.index = pd.to_datetime(data.index).normalize()
    data = data.sort_index()
    future_dates = data.index[data.index >= target_date]
    if len(future_dates) == 0:
        return None
    return future_dates[0]

def get_news_sentiment_time_window(ticker, signal_date):
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={ticker}"
        resp = requests.get(url, timeout=10)
        if not resp.ok:
            return "No News"
        data = resp.json()
        headlines = []
        start = signal_date - timedelta(days=NEWS_WINDOW_DAYS)
        end = signal_date + timedelta(days=NEWS_WINDOW_DAYS)
        if "news" in data:
            for n in data["news"]:
                if "providerPublishTime" in n:
                    pub_time = datetime.utcfromtimestamp(n["providerPublishTime"]).date()
                    if start <= pub_time <= end:
                        headlines.append(n["title"])
        if not headlines:
            return "No News"
        scores = [TextBlob(h).sentiment.polarity for h in headlines]
        avg = np.mean(scores)
        if avg > 0.1:
            return "Positive"
        elif avg < -0.1:
            return "Negative"
        else:
            return "Neutral"
    except Exception:
        return "Error"

def get_fundamentals_asof(ticker, signal_date):
    try:
        t = yf.Ticker(ticker)
        qf = t.quarterly_financials
        if qf.empty:
            return {"EPS": np.nan, "Revenue": np.nan, "NetIncome": np.nan, "Growth": np.nan, "PE": np.nan}
        qf = qf.T
        qf.index = pd.to_datetime(qf.index)
        qf = qf[qf.index <= signal_date]
        if qf.empty:
            return {"EPS": np.nan, "Revenue": np.nan, "NetIncome": np.nan, "Growth": np.nan, "PE": np.nan}

        last = qf.iloc[-1]
        eps = last.get("Diluted EPS", np.nan)
        rev = last.get("Total Revenue", np.nan)
        net = last.get("Net Income", np.nan)
        growth = np.nan

        if len(qf) > 1:
            prev = qf.iloc[-2]
            # Safely extract revenue values
            try:
                if isinstance(rev, pd.Series) and not rev.empty:
                    rev_val = rev.iloc[0]
                else:
                    rev_val = rev
                    
                prev_rev_val = prev.get("Total Revenue", np.nan)
                if isinstance(prev_rev_val, pd.Series) and not prev_rev_val.empty:
                    prev_rev_val = prev_rev_val.iloc[0]
                    
                if pd.notna(rev_val) and pd.notna(prev_rev_val) and prev_rev_val != 0:
                    growth = (float(rev_val) - float(prev_rev_val)) / float(prev_rev_val) * 100
            except (IndexError, ValueError, TypeError):
                growth = np.nan

        pe = t.info.get("trailingPE", np.nan)
        return {"EPS": eps, "Revenue": rev, "NetIncome": net, "Growth": growth, "PE": pe}
    except Exception:
        return {"EPS": np.nan, "Revenue": np.nan, "NetIncome": np.nan, "Growth": np.nan, "PE": np.nan}

def evaluate_buy_signal(tech, fund, sentiment):
    score = 0
    reasons = []
    # RSI<30 check removed - stocks are pre-filtered to be oversold
    # EMA check removed - stocks are pre-filtered to be above EMA200
    
    # Technical momentum
    if tech.get("RSI_rising", False):
        score += 1; reasons.append("RSI rising")
        
    # Candlestick patterns (new)
    if tech.get("is_hammer", False):
        score += 1; reasons.append("Hammer pattern")
    if tech.get("is_bullish_engulfing", False):
        score += 1; reasons.append("Bullish engulfing")
    if tech.get("bullish_divergence", False):
        score += 1; reasons.append("Bullish divergence")
        
    # Fundamental analysis
    if pd.notna(fund["EPS"]) and fund["EPS"] > 0:
        score += 1; reasons.append("EPS positive")
    if pd.notna(fund["Growth"]) and fund["Growth"] > 0:
        score += 1; reasons.append("Revenue growth")
    if pd.notna(fund["PE"]) and fund["PE"] < 40:
        score += 1; reasons.append("Reasonable PE")
        
    # Sentiment
    if sentiment == "Positive":
        score += 1; reasons.append("Positive news")

    # Max score is now 8 points
    if score >= 5:
        signal = "Strong Buy"
    elif 2 <= score < 5:
        signal = "Weak Buy"
    else:
        signal = "Avoid"

    return signal, score, ", ".join(reasons)

def check_reversal(data, signal_date, optimal_buy_date=None, optimal_buy_price=None):
    signal_date = get_nearest_signal_date(data, signal_date)
    if signal_date is None:
        return "No", "No data for signal date", 0, "No", "No data", 0
    
    # Find next trading day for buy price (open price)
    future_data = data.loc[data.index > signal_date]
    if future_data.empty:
        return "No", "No future data", 0, "No", "No future data", 0
        
    # Get the next trading day (first day after signal) - original approach
    next_day = future_data.index[0]
    
    try:
        # Buy at next day's open price (original)
        next_day_buy_price = float(future_data.at[next_day, "Open"])
        if pd.isna(next_day_buy_price) or next_day_buy_price <= 0:
            return "No", "Invalid buy price", 0, "No", "Invalid buy price", 0
    except (ValueError, TypeError, KeyError):
        return "No", "Cannot extract buy price", 0, "No", "Cannot extract buy price", 0
        
    # Use optimal buy date if provided
    if optimal_buy_date is not None and optimal_buy_price is not None:
        actual_buy_date = optimal_buy_date
        buy_price = optimal_buy_price
    else:
        actual_buy_date = next_day
        buy_price = next_day_buy_price

    # Calculate performance for both scenarios
    def calculate_performance(buy_date, buy_price_val):
        performance_data = future_data.loc[future_data.index >= buy_date]
        if performance_data.empty:
            return "No", "No performance data"
            
        max_close = performance_data["Close"].max()
        max_gain = (max_close - buy_price_val) / buy_price_val * 100
        
        final_close = performance_data["Close"].iloc[-1]
        final_gain = (final_close - buy_price_val) / buy_price_val * 100
        
        if max_gain >= 5:
            if final_gain >= 0:
                return "Yes", f"Max gain {max_gain:.1f}%, Final gain {final_gain:.1f}%"
            else:
                return "Partial", f"Max gain {max_gain:.1f}%, but Final loss {final_gain:.1f}%"
        else:
            return "No", f"Max gain only {max_gain:.1f}%, Final {final_gain:.1f}%"
    
    # Calculate both scenarios
    next_day_result, next_day_reason = calculate_performance(next_day, next_day_buy_price)
    optimal_result, optimal_reason = calculate_performance(actual_buy_date, buy_price)
    
    return (next_day_result, next_day_reason, next_day_buy_price,
            optimal_result, optimal_reason, buy_price)

# ---- Main ----
signals = pd.read_csv(INPUT_CSV)
signals["Date"] = pd.to_datetime(signals["Date"]).dt.normalize()
records = []

debug_info = {"processed": 0, "skipped_future": 0, "data_empty": 0, "no_close": 0, "insufficient_data": 0, "no_signal_date": 0, "errors": 0}

for _, row in tqdm(signals.iterrows(), total=len(signals), desc="Analyzing"):
    date = row["Date"]
    
    # Skip future dates - can't analyze data that doesn't exist yet
    current_date = pd.Timestamp.now().normalize()
    if date >= current_date:
        debug_info["skipped_future"] += 1
        continue
        
    tickers = row["Ticker"].split("|")
    for ticker in tickers:
        debug_info["processed"] += 1
        time.sleep(1.0)
        try:
            start = date - timedelta(days=365)  # Get more historical data
            end = date + timedelta(days=LOOKAHEAD_DAYS)
            
            # Ensure end date is not in the future
            end = min(end, pd.Timestamp.now())
            
            data = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
            if data.empty:
                debug_info["data_empty"] += 1
                continue
                
            # Handle MultiIndex columns from yfinance
            if isinstance(data.columns, pd.MultiIndex):
                # Flatten the MultiIndex columns - take the first level (Price type)
                data.columns = data.columns.get_level_values(0)

            # Ensure we have the required columns
            if "Close" not in data.columns:
                debug_info["no_close"] += 1
                continue
                
            data.index = pd.to_datetime(data.index).normalize()
            
            # Check if we have enough data for calculations (reduced requirement)
            if len(data) < 50:  # Reduced from 200 to 50
                debug_info["insufficient_data"] += 1
                print(f"  {ticker}: Only {len(data)} data points, need 50+")
                continue
                
            data["RSI10"] = compute_rsi(data["Close"], 10)
            data = data.sort_index()
            
            # Remove rows with NaN values in critical columns
            data = data.dropna(subset=["Close", "RSI10"])

            signal_date_check = get_nearest_signal_date(data, date)
            if signal_date_check is None:
                debug_info["no_signal_date"] += 1
                print(f"  {ticker}: No signal date found for {date}")
                continue

            # Safely extract scalar values
            close_val = data.at[signal_date_check, "Close"]
            rsi_val = data.at[signal_date_check, "RSI10"]
            
            # Handle potential NaN or invalid values
            if pd.isna(close_val) or pd.isna(rsi_val):
                continue
                
            close = float(close_val)
            rsi = float(rsi_val)

            # Get index position safely
            try:
                idx = data.index.get_loc(signal_date_check)
                # If get_loc returns an array/slice, get the first position
                if isinstance(idx, (slice, np.ndarray)):
                    if isinstance(idx, slice):
                        idx = idx.start if idx.start is not None else 0
                    else:
                        idx = int(idx[0]) if len(idx) > 0 else 0
                else:
                    idx = int(idx)
            except (KeyError, IndexError, TypeError, ValueError):
                continue
                
            # Analyze candlestick patterns on signal date
            current_candle = data.iloc[idx]
            
            # Check hammer pattern
            is_hammer_pattern = is_hammer(current_candle)
            
            # Check bullish engulfing (need previous candle)
            is_engulfing_pattern = False
            if idx > 0:
                prev_candle = data.iloc[idx-1]
                is_engulfing_pattern = is_bullish_engulfing(current_candle, prev_candle)
                
            # Check bullish divergence
            has_divergence = check_bullish_divergence(data, idx)
            
            # Calculate price decline before reversal
            decline_before_reversal = calculate_price_decline_before_reversal(data, signal_date_check)
            try:
                if idx + 3 < len(data):
                    future_rsi = data["RSI10"].iloc[idx+1:idx+4]
                    if not future_rsi.empty and len(future_rsi) > 1:
                        rsi_rising = (future_rsi.diff() > 0).sum() >= 2
                    else:
                        rsi_rising = False
                else:
                    rsi_rising = False
            except (IndexError, TypeError, ValueError):
                rsi_rising = False

            tech = {
                "Close": close, 
                "RSI": rsi, 
                "RSI_rising": rsi_rising,
                "is_hammer": is_hammer_pattern,
                "is_bullish_engulfing": is_engulfing_pattern,
                "bullish_divergence": has_divergence
            }
            fund = get_fundamentals_asof(ticker, signal_date_check)
            sentiment = get_news_sentiment_time_window(ticker, signal_date_check)
            buy_label, buy_score, buy_reasons = evaluate_buy_signal(tech, fund, sentiment)
            
            # Find optimal buy date using volume analysis
            optimal_date, optimal_reason, volume_ratio, decline_saved, optimal_price = find_optimal_buy_date_with_volume(data, signal_date_check)
            
            # Check performance for both scenarios
            (next_day_result, next_day_reason, next_day_price,
             optimal_result, optimal_reason_perf, optimal_buy_price) = check_reversal(data, signal_date_check, optimal_date, optimal_price)

            records.append({
                "Date": signal_date_check.date(),
                "Ticker": ticker,
                "SignalClose": close,
                "DeclineBeforeSignal%": round(decline_before_reversal, 2),
                # Next day buying (original approach)
                "NextDayBuyPrice": next_day_price,
                "NextDayResult": next_day_result,
                "NextDayReason": next_day_reason,
                # Volume-optimized buying
                "OptimalBuyDate": optimal_date.date() if optimal_date else None,
                "OptimalBuyPrice": optimal_buy_price,
                "OptimalBuyReason": optimal_reason,
                "VolumeRatio": round(volume_ratio, 1),
                "DeclineSaved%": round(decline_saved, 2),
                "OptimalResult": optimal_result,
                "OptimalPerformance": optimal_reason_perf,
                # Technical indicators
                "RSI10": rsi,
                "RSI_rising": rsi_rising,
                "Hammer": is_hammer_pattern,
                "BullishEngulfing": is_engulfing_pattern,
                "BullishDivergence": has_divergence,
                # Fundamental data
                "EPS": fund["EPS"],
                "Revenue": fund["Revenue"],
                "Growth%": fund["Growth"],
                "PE": fund["PE"],
                "News": sentiment,
                # Buy signal evaluation
                "Score": buy_score,
                "BuyVerdict": buy_label,
                "BuyReasons": buy_reasons
            })
        except Exception as e:
            debug_info["errors"] += 1
            print(f"Error processing {ticker}: {str(e)}")
            import traceback
            print(f"  Traceback: {traceback.format_exc()}")

# ---- Debug Info ----
print(f"\n🔍 Debug Information:")
for key, value in debug_info.items():
    print(f"  {key}: {value}")
print(f"  Total records generated: {len(records)}")

# ---- Save ----
if records:
    df = pd.DataFrame(records)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\n✅ Final results with Buy Signal + Reversal saved to {OUTPUT_CSV}")
    print(df.tail())
else:
    print("\n❌ No results generated.")
