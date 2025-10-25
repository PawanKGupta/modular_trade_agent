
from core.analysis import analyze_ticker, analyze_multiple_tickers
from core.scoring import compute_strength_score
from core.telegram import send_telegram
from core.scrapping import get_stock_list
from core.csv_exporter import CSVExporter
from core.backtest_scoring import add_backtest_scores_to_results
from utils.logger import logger
import os
from datetime import datetime
import pandas as pd

def get_stocks():
    stocks = get_stock_list()
    
    # Check if scraping failed
    if stocks is None or stocks.strip() == "":
        logger.error("Stock scraping failed, no stocks to analyze")
        return []
    
    return [s.strip().upper() + ".NS" for s in stocks.split(",")]

def compute_trading_priority_score(stock_data):
    """
    Compute trading priority score based on key metrics for better buy candidate sorting.
    Higher score = higher priority for trading
    """
    try:
        if stock_data is None or not isinstance(stock_data, dict):
            return 0
        priority_score = 0
        
        # 1. Risk-Reward Ratio (most important for profitability)
        risk_reward = stock_data.get('risk_reward_ratio', 0)
        if risk_reward >= 4.0:
            priority_score += 40
        elif risk_reward >= 3.0:
            priority_score += 30
        elif risk_reward >= 2.0:
            priority_score += 20
        elif risk_reward >= 1.5:
            priority_score += 10
        
        # 2. RSI Oversold Level (lower = better for dip buying)
        rsi = stock_data.get('rsi', 50)
        if rsi <= 15:
            priority_score += 25  # Extremely oversold
        elif rsi <= 20:
            priority_score += 20  # Very oversold
        elif rsi <= 25:
            priority_score += 15  # Oversold
        elif rsi <= 30:
            priority_score += 10  # Near oversold
        
        # 3. Volume Strength (higher = more conviction)
        volume_multiplier = stock_data.get('volume_multiplier', 1.0)
        if volume_multiplier >= 4.0:
            priority_score += 20
        elif volume_multiplier >= 2.0:
            priority_score += 15
        elif volume_multiplier >= 1.5:
            priority_score += 10
        elif volume_multiplier >= 1.2:
            priority_score += 5
        
        # 4. MTF Alignment Score
        timeframe_analysis = stock_data.get('timeframe_analysis', {})
        alignment_score = timeframe_analysis.get('alignment_score', 0)
        priority_score += min(alignment_score, 10)  # Cap at 10 points
        
        # 5. PE Ratio (lower = better value, but cap the bonus)
        pe = stock_data.get('pe', 100)
        if pe and pe > 0:
            if pe <= 15:
                priority_score += 10
            elif pe <= 25:
                priority_score += 5
            elif pe <= 35:
                priority_score += 2
            elif pe >= 50:
                priority_score -= 5  # Penalty for expensive stocks
        
        # 6. Backtest Performance (if available)
        backtest_score = stock_data.get('backtest_score', 0)
        if backtest_score >= 40:
            priority_score += 15
        elif backtest_score >= 30:
            priority_score += 10
        elif backtest_score >= 20:
            priority_score += 5
        
        return priority_score
        
    except Exception as e:
        logger.warning(f"Error computing priority score: {e}")
        if stock_data is None:
            return 0
        return stock_data.get('combined_score', stock_data.get('strength_score', 0))

def get_enhanced_stock_info(stock_data, index, is_strong_buy=True):
    """Generate enhanced stock information for Telegram message"""
    try:
        ticker = stock_data.get('ticker', 'N/A')
        buy_range = stock_data.get('buy_range', [0, 0])
        if buy_range and len(buy_range) >= 2:
            buy_low, buy_high = buy_range
        else:
            buy_low, buy_high = 0, 0
        target = stock_data.get('target', 0)
        stop = stock_data.get('stop', 0)
        rsi = stock_data.get('rsi', 0)
        last_close = stock_data.get('last_close', 0)
        
        # Calculate potential returns with None checks
        if target is None:
            target = 0
        if stop is None:
            stop = 0
        if last_close is None or last_close == 0:
            last_close = 1  # Avoid division by zero
            
        potential_gain = ((target - last_close) / last_close) * 100
        potential_loss = ((last_close - stop) / last_close) * 100
        risk_reward = potential_gain / potential_loss if potential_loss > 0 else 0
        
        # Multi-timeframe analysis details
        mtf_info = ""
        setup_details = ""
        
        if stock_data.get('timeframe_analysis'):
            tf_analysis = stock_data['timeframe_analysis']
            score = tf_analysis.get('alignment_score', 0)
            confirmation = tf_analysis.get('confirmation', 'none')
            
            mtf_info = f" MTF:{score}/10"
            
            # Get specific setup details
            daily_analysis = tf_analysis.get('daily_analysis', {})
            if daily_analysis:
                # Support quality
                support = daily_analysis.get('support_analysis', {})
                support_quality = support.get('quality', 'none')
                support_distance = support.get('distance_pct', 0)
                
                # Oversold severity
                oversold = daily_analysis.get('oversold_analysis', {})
                oversold_severity = oversold.get('severity', 'none')
                
                # Volume exhaustion
                volume_ex = daily_analysis.get('volume_exhaustion', {})
                volume_exhaustion = volume_ex.get('exhaustion_score', 0)
                
        # Build setup quality indicators (simplified)
                quality_indicators = []
                if support_quality == 'strong':
                    quality_indicators.append(f"StrongSupp:{support_distance:.1f}%")
                elif support_quality == 'moderate':
                    quality_indicators.append(f"ModSupp:{support_distance:.1f}%")
                    
                if oversold_severity == 'extreme':
                    quality_indicators.append("ExtremeRSI")
                elif oversold_severity == 'high':
                    quality_indicators.append("HighRSI")
                    
                if volume_exhaustion >= 2:
                    quality_indicators.append("VolExh")
                
                # Add support proximity score
                if support_distance <= 1.0 and support_quality in ['strong', 'moderate']:
                    quality_indicators.append("NearSupport")
                elif support_distance <= 2.0 and support_quality in ['strong', 'moderate']:
                    quality_indicators.append("CloseSupport")
                
                if quality_indicators:
                    setup_details = f" | {' '.join(quality_indicators)}"
        
        # Fundamental info (simplified)
        pe = stock_data.get('pe')
        fundamental_info = ""
        if pe is not None and pe > 0:
            fundamental_info = f" PE:{pe:.1f}"
        
        # Volume strength indicator (simplified)
        volume_info = ""
        vol_ratio = stock_data.get('today_vol', 0) / stock_data.get('avg_vol', 1) if stock_data.get('avg_vol', 1) > 0 else 1
        if vol_ratio >= 1.5:
            volume_info = f" Vol:{vol_ratio:.1f}x"
        elif vol_ratio < 0.6:
            volume_info = f" Vol:{vol_ratio:.1f}x"

        # News sentiment (if available)
        sentiment_info = ""
        s = stock_data.get('news_sentiment')
        if s and s.get('enabled'):
            used = int(s.get('used', 0))
            label = s.get('label', 'neutral')
            score = float(s.get('score', 0.0))
            label_short = 'Pos' if label == 'positive' else 'Neg' if label == 'negative' else 'Neu'
            sentiment_info = f" News:{label_short} {score:+.2f} ({used})"
        else:
            sentiment_info = " News:NA"
        
        # Build clean multi-line message
        lines = []
        lines.append(f"{index}. {ticker}:")
        lines.append(f"\tBuy ({buy_low:.2f}-{buy_high:.2f})")
        lines.append(f"\tTarget {target:.2f} (+{potential_gain:.1f}%)")
        lines.append(f"\tStop {stop:.2f} (-{potential_loss:.1f}%)")
        lines.append(f"\tRSI:{rsi}")
        # MTF on its own line if available
        if stock_data.get('timeframe_analysis'):
            tf_analysis = stock_data['timeframe_analysis']
            mtf_score = tf_analysis.get('alignment_score', 0)
            lines.append(f"\tMTF:{mtf_score}/10")
        # Risk-reward
        lines.append(f"\tRR:{risk_reward:.1f}x")
        # Setup quality indicators (space-separated)
        if setup_details:
            # setup_details currently like " | tokens"; extract tokens only
            tokens = setup_details.replace('|', '').strip()
            if tokens:
                lines.append(f"\t{tokens}")
        # Fundamentals (PE)
        if pe is not None and pe > 0:
            lines.append(f"\tPE:{pe:.1f}")
        # Volume ratio (always print)
        lines.append(f"\tVol:{vol_ratio:.1f}x")
        # News sentiment (always print)
        lines.append(f"\t{sentiment_info.strip()}")
        
        # Backtest information (if available)
        backtest = stock_data.get('backtest')
        if backtest and backtest.get('score', 0) > 0:
            bt_score = backtest.get('score', 0)
            bt_return = backtest.get('total_return_pct', 0)
            bt_winrate = backtest.get('win_rate', 0)
            bt_trades = backtest.get('total_trades', 0)
            lines.append(f"\tBacktest: {bt_score:.0f}/100 ({bt_return:+.1f}% return, {bt_winrate:.0f}% win, {bt_trades} trades)")
        
        # Combined score (if available)
        combined_score = stock_data.get('combined_score')
        if combined_score is not None:
            lines.append(f"\tCombined Score: {combined_score:.1f}/100")
        
        # Confidence level (if available)
        confidence = stock_data.get('backtest_confidence')
        if confidence:
            confidence_emoji = {"High": "🟢", "Medium": "🟡", "Low": "🟠"}.get(confidence, "⚪")
            lines.append(f"\tConfidence: {confidence_emoji} {confidence}")
        
        msg = "\n".join(lines) + "\n\n"
        return msg
        
    except Exception as e:
        logger.warning(f"Error generating enhanced info for {stock_data.get('ticker', 'unknown')}: {e}")
        # Fallback to simple format
        ticker = stock_data.get('ticker', 'N/A')
        buy_low, buy_high = stock_data.get('buy_range', [0, 0])
        target = stock_data.get('target', 0)
        stop = stock_data.get('stop', 0)
        rsi = stock_data.get('rsi', 0)
        return f"{ticker}: Buy ({buy_low:.2f}, {buy_high:.2f}) Target {target:.2f} Stop {stop:.2f} (rsi={rsi})\n"

def main(export_csv=True, enable_multi_timeframe=True, enable_backtest_scoring=False, dip_mode=False):
    tickers = get_stocks()
    
    if not tickers:
        logger.error("No stocks to analyze. Exiting.")
        return
    
    logger.info(f"Starting analysis for {len(tickers)} stocks (Multi-timeframe: {enable_multi_timeframe}, CSV Export: {export_csv})")
    
    # Use batch analysis with CSV export
    if export_csv:
        results, csv_filepath = analyze_multiple_tickers(
            tickers, 
            enable_multi_timeframe=enable_multi_timeframe,
            export_to_csv=True
        )
        logger.info(f"Analysis results exported to: {csv_filepath}")
    else:
        # Original single-ticker approach without CSV export
        results = []
        for t in tickers:
            try:
                r = analyze_ticker(
                    t, 
                    enable_multi_timeframe=enable_multi_timeframe,
                    export_to_csv=False
                )
                results.append(r)
                
                # Log based on analysis status
                if r.get('status') == 'success':
                    logger.debug(f"SUCCESS {t}: {r['verdict']}")
                else:
                    logger.warning(f"WARNING {t}: {r.get('status', 'unknown_error')} - {r.get('error', 'No details')}")
                    
            except Exception as e:
                logger.error(f"ERROR Unexpected error analyzing {t}: {e}")
                results.append({"ticker": t, "status": "fatal_error", "error": str(e)})

    # Calculate strength scores for all results (needed for backtest scoring)
    for result in results:
        if result.get('status') == 'success':
            result['strength_score'] = compute_strength_score(result)
    
    # Add backtest scoring if enabled
    if enable_backtest_scoring:
        mode_info = " (DIP MODE)" if dip_mode else ""
        logger.info(f"Running backtest scoring analysis{mode_info}...")
        results = add_backtest_scores_to_results(results, years_back=2, dip_mode=dip_mode)
        # Re-sort by priority score for better trading decisions
        results = [r for r in results if r is not None]  # Filter out None values
        results.sort(key=lambda x: -compute_trading_priority_score(x))
        # Export a final CSV with backtest fields for auto-trader
        try:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            out_dir = 'analysis_results'
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"bulk_analysis_final_{ts}.csv")
            # Keep the most useful fields; include fallbacks
            cols = [
                'ticker','status','verdict','final_verdict','combined_score','strength_score','last_close',
                'buy_range','target','stop','timeframe_analysis','backtest'
            ]
            def _flatten(row):
                d = {k: row.get(k) for k in cols if k in row}
                # Simple stringify for complex fields
                for k in ('buy_range','timeframe_analysis','backtest'):
                    if k in d and not isinstance(d[k], (str,int,float)):
                        d[k] = str(d[k])
                return d
            df_final = pd.DataFrame([_flatten(r) for r in results if isinstance(r, dict)])
            df_final.to_csv(out_path, index=False)
            logger.info(f"Final post-scored CSV written to: {out_path}")
        except Exception as e:
            logger.warning(f"Failed to export final post-scored CSV: {e}")
    else:
        results = [r for r in results if r is not None]  # Filter out None values  
        results.sort(key=lambda x: -compute_trading_priority_score(x))

    # Include both 'buy' and 'strong_buy' candidates, but exclude failed analysis
    # Use final_verdict if backtest scoring was enabled, otherwise use original verdict
    if enable_backtest_scoring:
        # Apply filtering with reasonable combined score threshold
        buys = [r for r in results if 
                r.get('final_verdict') in ['buy', 'strong_buy'] and 
                r.get('status') == 'success' and
                r.get('combined_score', 0) >= 25]  # Minimum combined score (lowered from 35)
        strong_buys = [r for r in results if 
                      r.get('final_verdict') == 'strong_buy' and 
                      r.get('status') == 'success' and
                      r.get('combined_score', 0) >= 25]
    else:
        buys = [r for r in results if r.get('verdict') in ['buy', 'strong_buy'] and r.get('status') == 'success']
        strong_buys = [r for r in results if r.get('verdict') == 'strong_buy' and r.get('status') == 'success']

    # Send Telegram notification with final results (after backtest scoring if enabled)
    if buys:
        msg_prefix = "*Reversal Buy Candidates (today)*"
        if enable_backtest_scoring:
            msg_prefix += " *with Backtest Scoring*"
        msg = msg_prefix + "\n"
        
        # Highlight strong buys first (sorted by priority)
        if strong_buys:
            strong_buys = [r for r in strong_buys if r is not None]  # Filter out None values
            strong_buys.sort(key=lambda x: -compute_trading_priority_score(x))  # Sort by priority
            msg += "\n🔥 *STRONG BUY* (Multi-timeframe confirmed):\n"
            for i, b in enumerate(strong_buys, 1):
                enhanced_info = get_enhanced_stock_info(b, i)
                msg += enhanced_info
        
        # Regular buys (exclude stocks already in strong_buys to avoid duplicates)
        strong_buy_tickers = {r.get('ticker') for r in strong_buys}
        if enable_backtest_scoring:
            regular_buys = [r for r in buys if r.get('final_verdict') == 'buy' and r.get('ticker') not in strong_buy_tickers]
        else:
            regular_buys = [r for r in buys if r.get('verdict') == 'buy' and r.get('ticker') not in strong_buy_tickers]
        
        if regular_buys:
            regular_buys = [r for r in regular_buys if r is not None]  # Filter out None values
            regular_buys.sort(key=lambda x: -compute_trading_priority_score(x))  # Sort by priority
            msg += "\n📈 *BUY* candidates:\n"
            for i, b in enumerate(regular_buys, 1):
                enhanced_info = get_enhanced_stock_info(b, i, is_strong_buy=False)
                msg += enhanced_info
        
        send_telegram(msg)
        scoring_info = " (with backtest scoring)" if enable_backtest_scoring else ""
        logger.info(f"Sent Telegram alert for {len(buys)} buy candidates ({len(strong_buys)} strong buys){scoring_info}")
    else:
        logger.info("No buy candidates today.")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Stock Analysis with Multi-timeframe Confirmation')
    parser.add_argument('--no-csv', action='store_true', help='Disable CSV export')
    parser.add_argument('--no-mtf', action='store_true', help='Disable multi-timeframe analysis')
    parser.add_argument('--backtest', action='store_true', help='Enable backtest scoring (slower but more accurate)')
    parser.add_argument('--dip-mode', action='store_true', help='Enable dip-buying mode with more permissive thresholds')
    
    args = parser.parse_args()
    
    main(
        export_csv=not args.no_csv,
        enable_multi_timeframe=not args.no_mtf,
        enable_backtest_scoring=args.backtest,
        dip_mode=getattr(args, 'dip_mode', False)
    )
