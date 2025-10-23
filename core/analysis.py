import math
import yfinance as yf
import pandas as pd
from core.data_fetcher import fetch_ohlcv_yf, fetch_multi_timeframe_data
from core.indicators import compute_indicators
from core.patterns import is_hammer, is_bullish_engulfing, bullish_divergence
from core.timeframe_analysis import TimeframeAnalysis
from core.csv_exporter import CSVExporter
from core.volume_analysis import assess_volume_quality_intelligent, get_volume_verdict, analyze_volume_pattern
from config.settings import RSI_OVERSOLD, MIN_VOLUME_MULTIPLIER, VOLUME_MULTIPLIER_FOR_STRONG
from config.settings import (
    NEWS_SENTIMENT_ENABLED,
    NEWS_SENTIMENT_POS_THRESHOLD,
    NEWS_SENTIMENT_NEG_THRESHOLD,
)
from core.news_sentiment import analyze_news_sentiment
from utils.logger import logger

def avg_volume(df, lookback=20):
    return df['volume'].tail(lookback).mean()

def assess_fundamental_quality(pe, pb, rsi):
    """Assess fundamental quality (0-3 scale)"""
    score = 0
    
    # PE ratio assessment
    if pe is not None:
        if pe > 0 and pe < 15:  # Very attractive valuation
            score += 2
        elif pe > 0 and pe < 25:  # Decent valuation
            score += 1
        elif pe < 0:  # Negative earnings - penalize
            score -= 1
    
    # PB ratio assessment
    if pb is not None:
        if pb < 1.5:  # Trading below book value - attractive
            score += 1
        elif pb > 10:  # Very expensive - penalize
            score -= 1
    
    return max(0, min(score, 3))  # Cap between 0-3

def assess_volume_quality(vol_strong, current_volume, avg_volume):
    """Assess volume quality (0-3 scale)"""
    score = 0
    
    if vol_strong:
        score += 2  # Strong volume is excellent
    
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
    if volume_ratio >= 1.5:  # 50% above average
        score += 1
    elif volume_ratio < 0.5:  # Very low volume - penalize
        score -= 1
        
    return max(0, min(score, 3))  # Cap between 0-3

def assess_setup_quality(timeframe_confirmation, signals):
    """Assess overall setup quality (0-3 scale)"""
    score = 0
    
    if timeframe_confirmation:
        # Support quality
        daily_support = timeframe_confirmation.get('daily_analysis', {}).get('support_analysis', {})
        if daily_support.get('quality') == 'strong':
            score += 1
        
        # Oversold severity
        daily_oversold = timeframe_confirmation.get('daily_analysis', {}).get('oversold_analysis', {})
        if daily_oversold.get('severity') == 'extreme':  # RSI < 20
            score += 1
        elif daily_oversold.get('severity') == 'high':  # RSI < 30
            score += 0.5
        
        # Volume exhaustion
        daily_volume = timeframe_confirmation.get('daily_analysis', {}).get('volume_exhaustion', {})
        if daily_volume.get('exhaustion_score', 0) >= 2:
            score += 1
    
    # Pattern signals bonus
    pattern_count = len([s for s in signals if s in ['hammer', 'bullish_engulfing', 'bullish_divergence']])
    if pattern_count >= 2:
        score += 1
    elif pattern_count >= 1:
        score += 0.5
        
    return min(score, 3)  # Cap at 3

def assess_support_proximity(timeframe_confirmation):
    """Assess how close the stock is to support levels (0-3 scale)"""
    if not timeframe_confirmation:
        return 0  # No MTF data = no support analysis
    
    score = 0
    
    # Get daily support analysis
    daily_analysis = timeframe_confirmation.get('daily_analysis', {})
    daily_support = daily_analysis.get('support_analysis', {})
    
    support_quality = daily_support.get('quality', 'none')
    support_distance = daily_support.get('distance_pct', 999)
    
    # Score based on distance to support
    if support_quality in ['strong', 'moderate']:
        if support_distance <= 1.0:  # Very close to strong/moderate support
            score += 3
        elif support_distance <= 2.0:  # Close to support
            score += 2  
        elif support_distance <= 4.0:  # Reasonably close to support
            score += 1
        # >4% from support = 0 points
        
        # Bonus for strong support quality
        if support_quality == 'strong':
            score += 0.5
    
    elif support_quality == 'weak' and support_distance <= 2.0:
        score += 1  # Even weak support gets some points if very close
    
    # Get weekly support analysis for additional context
    weekly_analysis = timeframe_confirmation.get('weekly_analysis', {})
    if weekly_analysis:
        weekly_support = weekly_analysis.get('support_analysis', {})
        weekly_quality = weekly_support.get('quality', 'none')
        weekly_distance = weekly_support.get('distance_pct', 999)
        
        # Bonus for weekly support confluence
        if weekly_quality in ['strong', 'moderate'] and weekly_distance <= 3.0:
            score += 0.5  # Multi-timeframe support confluence bonus
    
    return min(round(score), 3)  # Cap at 3

def calculate_smart_buy_range(current_price, timeframe_confirmation):
    """
    Calculate intelligent buy range based on support levels and MTF analysis
    """
    try:
        # Default range ±1%
        default_range = (round(current_price * 0.995, 2), round(current_price * 1.01, 2))
        calculated_range = default_range
        
        if timeframe_confirmation:
            # Get support analysis from daily timeframe
            daily_analysis = timeframe_confirmation.get('daily_analysis', {})
            support_analysis = daily_analysis.get('support_analysis', {})
            
            support_level = support_analysis.get('support_level', 0)
            support_quality = support_analysis.get('quality', 'none')
            distance_pct = support_analysis.get('distance_pct', 999)
            mtf_confirmation = timeframe_confirmation.get('confirmation', '')
            
            # Calculate range based on conditions
            if support_quality in ['strong', 'moderate'] and distance_pct <= 2:
                # Very close to support - use support-based range
                support_buffer = 0.003 if support_quality == 'strong' else 0.005  # 0.3% or 0.5%
                buy_low = round(support_level * (1 - support_buffer), 2)
                buy_high = round(support_level * (1 + support_buffer), 2)
                calculated_range = (buy_low, buy_high)
                
            elif support_quality in ['strong', 'moderate'] and distance_pct <= 5:
                # Somewhat close to support - use tighter current price range
                calculated_range = (round(current_price * 0.9925, 2), round(current_price * 1.0075, 2))
                
            elif mtf_confirmation == 'excellent_uptrend_dip':
                # Excellent setup - use tight range
                calculated_range = (round(current_price * 0.997, 2), round(current_price * 1.007, 2))
        
        # Validate range width (safeguard against overly wide ranges)
        buy_low, buy_high = calculated_range
        range_width_pct = ((buy_high - buy_low) / current_price) * 100
        
        if range_width_pct > 2.0:
            logger.warning(f"Buy range too wide ({range_width_pct:.1f}%), using default range")
            return default_range
        
        # Log the calculation for debugging
        if calculated_range != default_range:
            logger.debug(f"Smart buy range: {calculated_range} (width: {range_width_pct:.1f}%) vs default: {default_range}")
        
        return calculated_range
        
    except Exception as e:
        logger.warning(f"Error calculating smart buy range: {e}")
        return (round(current_price * 0.995, 2), round(current_price * 1.01, 2))

def calculate_smart_stop_loss(current_price, recent_low, timeframe_confirmation, df):
    """
    Calculate intelligent stop loss based on uptrend context and support levels
    """
    try:
        # Default stop: recent low or 8% down
        default_stop = round(min(recent_low * 0.995, current_price * 0.92), 2)
        
        if not timeframe_confirmation:
            return default_stop
            
        daily_analysis = timeframe_confirmation.get('daily_analysis', {})
        weekly_analysis = timeframe_confirmation.get('weekly_analysis', {})
        
        # Get support levels
        daily_support = daily_analysis.get('support_analysis', {})
        weekly_support = weekly_analysis.get('support_analysis', {})
        
        daily_support_level = daily_support.get('support_level', 0)
        weekly_support_level = weekly_support.get('support_level', 0)
        
        mtf_confirmation = timeframe_confirmation.get('confirmation', '')
        
        # For strong uptrend dips, use more intelligent stops
        if mtf_confirmation in ['excellent_uptrend_dip', 'good_uptrend_dip']:
            
            # Use the lower of daily or weekly support (stronger level)
            key_support = min(daily_support_level, weekly_support_level) if daily_support_level > 0 and weekly_support_level > 0 else max(daily_support_level, weekly_support_level)
            
            if key_support > 0:
                # Calculate support-based stop (2% below support for safety)
                support_stop = round(key_support * 0.98, 2)
                
                # Calculate distance from current price to support-based stop
                support_stop_distance = ((current_price - support_stop) / current_price) * 100
                
                # If support is too far (>8%), use percentage-based stop instead
                if support_stop_distance > 8:
                    # Use reasonable percentage stops
                    max_loss = 0.06 if mtf_confirmation == 'excellent_uptrend_dip' else 0.05
                    return round(current_price * (1 - max_loss), 2)
                
                # If support is very close (<2%), use minimum 3% stop for breathing room
                if support_stop_distance < 3:
                    return round(current_price * 0.97, 2)  # 3% stop
                
                # Support is at reasonable distance (3-8%), use it
                return support_stop
        
        # For fair uptrend dips, slightly tighter than default
        elif mtf_confirmation == 'fair_uptrend_dip':
            return round(min(recent_low * 0.995, current_price * 0.94), 2)  # 6% instead of 8%
        
        return default_stop
        
    except Exception as e:
        logger.warning(f"Error calculating smart stop loss: {e}")
        return round(min(recent_low * 0.995, current_price * 0.92), 2)

def calculate_smart_target(current_price, stop_price, verdict, timeframe_confirmation, recent_high):
    """
    Calculate intelligent target based on MTF quality, resistance levels, and risk-reward
    """
    try:
        # Calculate risk amount
        risk_amount = current_price - stop_price
        risk_pct = risk_amount / current_price if current_price > 0 else 0.08
        
        # Base target multipliers
        if verdict == "strong_buy":
            min_target_pct = 0.12  # 12% minimum
            risk_multiplier = 3.0   # 3x risk-reward
        else:
            min_target_pct = 0.08  # 8% minimum
            risk_multiplier = 2.5   # 2.5x risk-reward
        
        # Enhanced targets based on MTF confirmation quality
        if timeframe_confirmation:
            mtf_confirmation = timeframe_confirmation.get('confirmation', '')
            alignment_score = timeframe_confirmation.get('alignment_score', 0)
            
            # Excellent setups get higher targets
            if mtf_confirmation == 'excellent_uptrend_dip':
                min_target_pct = 0.15  # 15% minimum for excellent setups
                risk_multiplier = 3.5   # 3.5x risk-reward
            elif mtf_confirmation == 'good_uptrend_dip':
                min_target_pct = 0.12  # 12% minimum for good setups
                risk_multiplier = 3.0   # 3x risk-reward
            
            # Bonus for high alignment scores
            if alignment_score >= 8:
                risk_multiplier += 0.5
            elif alignment_score >= 6:
                risk_multiplier += 0.25
        
        # Calculate target based on risk-reward
        risk_reward_target = current_price + (risk_amount * risk_multiplier)
        min_target = current_price * (1 + min_target_pct)
        
        # Use the higher of minimum target or risk-reward target
        base_target = max(min_target, risk_reward_target)
        
        # Enhanced resistance-based target capping
        resistance_cap = recent_high * 1.05  # Default: 5% above recent high
        
        # Use MTF resistance analysis if available
        if timeframe_confirmation:
            daily_analysis = timeframe_confirmation.get('daily_analysis', {})
            daily_resistance = daily_analysis.get('resistance_analysis', {})
            
            resistance_level = daily_resistance.get('resistance_level', recent_high)
            resistance_quality = daily_resistance.get('quality', 'unknown')
            distance_to_resistance = daily_resistance.get('distance_pct', 0)
            
            # Adjust target based on resistance context
            if resistance_quality == 'strong' and distance_to_resistance >= 8:
                # Far from strong resistance - can use higher targets
                resistance_cap = resistance_level * 0.98  # Stop just before resistance
            elif resistance_quality == 'moderate' and distance_to_resistance >= 5:
                # Moderate resistance with some room
                resistance_cap = resistance_level * 0.95
            elif resistance_quality in ['weak', 'immediate']:
                # Close to resistance - conservative targets
                resistance_cap = min(base_target * 0.9, resistance_level * 0.92)
        
        final_target = min(base_target, resistance_cap)
        
        # Ensure minimum viable target (at least 3% gain)
        min_viable_target = current_price * 1.03
        return round(max(final_target, min_viable_target), 2)
        
    except Exception as e:
        logger.warning(f"Error calculating smart target: {e}")
        # Fallback to simple calculation
        return round(current_price * 1.10, 2)

def analyze_ticker(ticker, enable_multi_timeframe=True, export_to_csv=False, csv_exporter=None, as_of_date=None):
    try:
        logger.debug(f"Starting analysis for {ticker}")
        
        # Initialize timeframe analyzer
        tf_analyzer = TimeframeAnalysis() if enable_multi_timeframe else None
        
        # Disable current day data addition during backtesting (when as_of_date is provided)
        add_current_day = as_of_date is None  # Only add current day for live analysis
        
        # Fetch data - multi-timeframe if enabled, single timeframe otherwise
        multi_data = None  # Initialize to prevent NameError
        if enable_multi_timeframe:
            multi_data = fetch_multi_timeframe_data(ticker, end_date=as_of_date, add_current_day=add_current_day)
            if multi_data is None or multi_data.get('daily') is None:
                logger.warning(f"No multi-timeframe data available for {ticker}")
                return {"ticker": ticker, "status": "no_data"}
            df = multi_data['daily']
        else:
            df = fetch_ohlcv_yf(ticker, end_date=as_of_date, add_current_day=add_current_day)
            if df is None or df.empty:
                logger.warning(f"No data available for {ticker}")
                return {"ticker": ticker, "status": "no_data"}

        # Compute technical indicators
        df = compute_indicators(df)
        if df is None or df.empty:
            logger.error(f"Failed to compute indicators for {ticker}")
            return {"ticker": ticker, "status": "indicator_error"}
        
        # Clip to as_of_date if provided (ensure no future data leaks)
        if as_of_date is not None:
            try:
                asof_ts = pd.to_datetime(as_of_date)
                if 'date' in df.columns:
                    df = df[df['date'] <= asof_ts]
                else:
                    df = df.loc[df.index <= asof_ts]
            except Exception as _:
                pass
            
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

    # Optional news sentiment (as-of date aware)
    news_sentiment = None
    try:
        news_sentiment = analyze_news_sentiment(ticker, as_of_date=as_of_date)
    except Exception as _e:
        news_sentiment = None
    
    # Multi-timeframe confirmation analysis for dip-buying
    timeframe_confirmation = None
    if enable_multi_timeframe and tf_analyzer and multi_data.get('weekly') is not None:
        try:
            timeframe_confirmation = tf_analyzer.get_dip_buying_confirmation(
                multi_data['daily'], multi_data['weekly']
            )
            logger.debug(f"Dip-buying MTF analysis for {ticker}: {timeframe_confirmation['confirmation']} (score: {timeframe_confirmation['alignment_score']})")
        except Exception as e:
            logger.warning(f"Multi-timeframe analysis failed for {ticker}: {e}")
            timeframe_confirmation = None

    if is_hammer(last):
        signals.append("hammer")

    if prev is not None and is_bullish_engulfing(prev, last):
        signals.append("bullish_engulfing")

    if last['rsi10'] is not None and last['rsi10'] < RSI_OVERSOLD:
        signals.append("rsi_oversold")

    if bullish_divergence(df):
        signals.append("bullish_divergence")
        
    # Add uptrend dip-buying timeframe confirmation signals
    if timeframe_confirmation:
        confirmation_type = timeframe_confirmation['confirmation']
        if confirmation_type == 'excellent_uptrend_dip':
            signals.append("excellent_uptrend_dip")
        elif confirmation_type == 'good_uptrend_dip':
            signals.append("good_uptrend_dip")
        elif confirmation_type == 'fair_uptrend_dip':
            signals.append("fair_uptrend_dip")

    avg_vol = avg_volume(df, 20)
    
    # Intelligent volume analysis with time-awareness
    volume_analysis = assess_volume_quality_intelligent(
        current_volume=last['volume'],
        avg_volume=avg_vol,
        enable_time_adjustment=True
    )
    
    vol_ok, vol_strong, volume_description = get_volume_verdict(volume_analysis)
    
    # Additional volume pattern context
    volume_pattern = analyze_volume_pattern(df)

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
    
    # Simplified decision logic for reversal strategy - focus on core signals
    # Core reversal conditions (matching backtest criteria)
    rsi_oversold = pd.notna(last['rsi10']) and last['rsi10'] < RSI_OVERSOLD  # RSI < 30
    above_trend = pd.notna(last['ema200']) and last['close'] > last['ema200']  # Above EMA200
    decent_volume = vol_ok  # Use intelligent volume analysis
    
    # Avoid stocks with negative earnings (fundamental red flag)
    fundamental_ok = not (pe is not None and pe < 0)
    
    if rsi_oversold and above_trend and decent_volume and fundamental_ok:
        # Simple quality-based classification using MTF and patterns
        alignment_score = timeframe_confirmation.get('alignment_score', 0) if timeframe_confirmation else 0
        
        # Strong Buy: Excellent MTF alignment OR excellent uptrend dip pattern
        if alignment_score >= 8 or "excellent_uptrend_dip" in signals:
            verdict = "strong_buy"
        
        # Buy: Good MTF alignment OR good patterns OR strong volume
        elif (alignment_score >= 5 or 
              any(s in signals for s in ["good_uptrend_dip", "fair_uptrend_dip", "hammer", "bullish_engulfing"]) or
              vol_strong):
            verdict = "buy"
        
        # Buy: Basic reversal setup (meets core criteria)
        else:
            verdict = "buy"  # Default for valid reversal conditions
    
    elif rsi_oversold and decent_volume and fundamental_ok:
        # RSI oversold with volume but may not be above EMA200 or other issues
        verdict = "watch"
    
    elif len(signals) > 0 and vol_ok:
        # Has some signals and volume but not core reversal conditions
        verdict = "watch"
    
    else:
        # No significant signals
        verdict = "avoid"
    
    # Build justification based on what was found
    if verdict in ["buy", "strong_buy"]:
        # Add core reversal justification
        if rsi_oversold:
            justification.append(f"rsi:{round(last['rsi10'], 1)}")
        
        # Add pattern signals (excluding MTF signals)
        pattern_signals = [s for s in signals if s not in ["excellent_uptrend_dip", "good_uptrend_dip", "fair_uptrend_dip"]]
        if pattern_signals:
            justification.append("pattern:" + ",".join(pattern_signals))
        
        # Add MTF uptrend dip confirmation
        if "excellent_uptrend_dip" in signals:
            justification.append("excellent_uptrend_dip_confirmation")
        elif "good_uptrend_dip" in signals:
            justification.append("good_uptrend_dip_confirmation")
        elif "fair_uptrend_dip" in signals:
            justification.append("fair_uptrend_dip_confirmation")
        
        # Add volume information with intelligent analysis
        if vol_strong:
            justification.append(f"volume_strong({volume_analysis['ratio']}x)")
        elif decent_volume:
            justification.append(f"volume_adequate({volume_analysis['ratio']}x)")
            
        # Add time adjustment info if applicable
        if volume_analysis.get('time_adjusted'):
            justification.append(f"intraday_adjusted(h{volume_analysis.get('current_hour')})")
            
    elif verdict == "watch":
        if not fundamental_ok:
            justification.append("fundamental_red_flag")
        elif len(signals) > 0:
            justification.append("signals:" + ",".join(signals))
        else:
            justification.append("partial_reversal_setup")

    buy_range = None
    target = None
    stop = None

    # Apply news sentiment adjustment (downgrade on negative news)
    if news_sentiment and news_sentiment.get('enabled') and verdict in ["buy", "strong_buy"]:
        sc = float(news_sentiment.get('score', 0.0))
        used = int(news_sentiment.get('used', 0))
        if used >= 1 and sc <= NEWS_SENTIMENT_NEG_THRESHOLD:
            verdict = "watch"
            justification.append("news_negative")

    if verdict in ["buy", "strong_buy"]:
        current_price = last['close']
        
        # Enhanced buy range based on support levels
        buy_range = calculate_smart_buy_range(current_price, timeframe_confirmation)
        
        # Enhanced stop loss based on uptrend context and support
        stop = calculate_smart_stop_loss(current_price, recent_low, timeframe_confirmation, df)
        
        # Enhanced target based on MTF quality and resistance levels
        target = calculate_smart_target(current_price, stop, verdict, timeframe_confirmation, recent_high)

    # Final result compilation with error handling
    try:
        rsi_value = None if math.isnan(last['rsi10']) else round(last['rsi10'], 2)
        
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
            "timeframe_analysis": timeframe_confirmation,
            "news_sentiment": news_sentiment,
            "volume_analysis": volume_analysis,
            "volume_pattern": volume_pattern,
            "volume_description": volume_description,
            "status": "success"
        }
        
        logger.debug(f"Analysis completed successfully for {ticker}: {verdict}")
        
        # Export to CSV if requested
        if export_to_csv:
            if csv_exporter is None:
                csv_exporter = CSVExporter()
            
            # Export individual stock analysis
            csv_exporter.export_single_stock(result)
            
            # Also append to master CSV for historical tracking
            csv_exporter.append_to_master_csv(result)
        
        return result
        
    except Exception as e:
        logger.error(f"Error compiling final results for {ticker}: {e}")
        return {"ticker": ticker, "status": "result_compilation_error", "error": str(e)}

    except Exception as e:
        logger.error(f"Unexpected error in analyze_ticker for {ticker}: {type(e).__name__}: {e}")
        return {"ticker": ticker, "status": "analysis_error", "error": str(e)}


def analyze_multiple_tickers(tickers, enable_multi_timeframe=True, export_to_csv=True, csv_filename=None):
    """
    Analyze multiple tickers and export results to CSV
    
    Args:
        tickers: List of ticker symbols to analyze
        enable_multi_timeframe: Enable multi-timeframe analysis
        export_to_csv: Export results to CSV
        csv_filename: Custom filename for CSV export
        
    Returns:
        List of analysis results and CSV filepath if exported
    """
    logger.info(f"Starting batch analysis for {len(tickers)} tickers")
    
    csv_exporter = CSVExporter() if export_to_csv else None
    results = []
    
    for i, ticker in enumerate(tickers, 1):
        logger.info(f"Analyzing {ticker} ({i}/{len(tickers)})")
        
        try:
            result = analyze_ticker(
                ticker, 
                enable_multi_timeframe=enable_multi_timeframe,
                export_to_csv=False,  # We'll handle bulk export separately
                csv_exporter=None
            )
            results.append(result)
            
            # Append to master CSV for historical tracking
            if csv_exporter:
                csv_exporter.append_to_master_csv(result)
                
        except Exception as e:
            logger.error(f"Failed to analyze {ticker}: {e}")
            error_result = {"ticker": ticker, "status": "batch_analysis_error", "error": str(e)}
            results.append(error_result)
            
            if csv_exporter:
                csv_exporter.append_to_master_csv(error_result)
    
    # Export bulk results to single CSV
    csv_filepath = None
    if export_to_csv and csv_exporter:
        csv_filepath = csv_exporter.export_multiple_stocks(results, csv_filename)
        logger.info(f"Batch analysis complete. Results exported to: {csv_filepath}")
    else:
        logger.info(f"Batch analysis complete for {len(results)} tickers")
    
    return results, csv_filepath
