
from core.analysis import analyze_ticker, analyze_multiple_tickers
# Phase 4: Use services instead of core modules
from services import ScoringService, BacktestService, compute_strength_score
from core.telegram import send_telegram  # TODO Phase 4: Migrate to infrastructure/notifications
from core.scrapping import get_stock_list  # TODO Phase 4: Migrate to infrastructure/web_scraping
from core.csv_exporter import CSVExporter  # TODO Phase 4: Migrate to infrastructure/persistence
from utils.logger import logger
import os
from datetime import datetime
import pandas as pd
from pathlib import Path

# ML verdict service (optional, for testing only)
_ml_verdict_service = None
try:
    from services.ml_verdict_service import MLVerdictService
    ml_model_path = Path("models/verdict_model_random_forest.pkl")
    if ml_model_path.exists():
        _ml_verdict_service = MLVerdictService(model_path=str(ml_model_path))
        logger.info("✅ ML verdict service loaded for testing (will include ML predictions in Telegram)")
    else:
        logger.info("ℹ️ ML model not found. Run ML training first. Using rule-based only.")
except ImportError:
    logger.debug("ML verdict service not available (scikit-learn may not be installed)")
except Exception as e:
    logger.warning(f"⚠️ Failed to load ML verdict service: {e}")

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

    Phase 4: Now uses ScoringService instead of duplicating logic
    """
    try:
        # Use ScoringService (Phase 4)
        scoring_service = ScoringService()
        return scoring_service.compute_trading_priority_score(stock_data)
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

        # Phase 13: Capital and chart quality information
        execution_capital = stock_data.get('execution_capital', 0)
        capital_adjusted = stock_data.get('capital_adjusted', False)
        chart_quality = stock_data.get('chart_quality', {})

        # Format capital info
        capital_info = ""
        if execution_capital and execution_capital > 0:
            if capital_adjusted:
                capital_info = f" 💰 Capital: ₹{execution_capital:,.0f} (adjusted for liquidity)"
            else:
                capital_info = f" 💰 Capital: ₹{execution_capital:,.0f}"

        # Format chart quality info
        chart_info = ""
        if chart_quality and isinstance(chart_quality, dict):
            chart_score = chart_quality.get('score', 0)
            chart_status = chart_quality.get('status', 'unknown')
            if chart_score > 0:
                if chart_status == 'clean':
                    chart_info = f" 📊 Chart: {chart_score:.0f}/100 (clean)"
                elif chart_status == 'acceptable':
                    chart_info = f" 📊 Chart: {chart_score:.0f}/100 (acceptable)"
                else:
                    chart_info = f" 📊 Chart: {chart_score:.0f}/100"

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

        # Phase 13: Add capital and chart quality info
        if capital_info:
            # Extract just the capital amount and adjustment status
            capital_text = capital_info.replace('💰 Capital: ', '').strip()
            lines.append(f"\tCapital: {capital_text}")

        if chart_info:
            # Extract just the chart score and status
            chart_text = chart_info.replace('📊 Chart: ', '').strip()
            lines.append(f"\tChart: {chart_text}")
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

        # ML Verdict (monitoring mode - add if available)
        ml_verdict = stock_data.get('ml_verdict')
        ml_confidence = stock_data.get('ml_confidence')
        if ml_verdict and ml_confidence is not None:
            # Handle both decimal (0-1) and percentage (0-100) formats
            if isinstance(ml_confidence, (int, float)):
                conf_pct = ml_confidence if ml_confidence > 1 else ml_confidence * 100
            else:
                conf_pct = 0
            # Add ML prediction for comparison/monitoring
            ml_emoji = {"strong_buy": "🔥", "buy": "📈", "watch": "👀", "avoid": "❌"}.get(ml_verdict, "🤖")
            lines.append(f"\t🤖 ML: {ml_verdict.upper()} {ml_emoji} ({conf_pct:.0f}% conf)")

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

async def main_async(export_csv=True, enable_multi_timeframe=True, enable_backtest_scoring=False, dip_mode=False):
    """
    Async main function using async batch analysis

    This version uses async/await for parallel processing, significantly
    reducing analysis time for batch operations.
    """
    tickers = get_stocks()

    if not tickers:
        logger.error("No stocks to analyze. Exiting.")
        return

    logger.info(f"Starting async analysis for {len(tickers)} stocks (Multi-timeframe: {enable_multi_timeframe}, CSV Export: {export_csv})")

    # Use async batch analysis (Phase 2)
    try:
        from services.async_analysis_service import AsyncAnalysisService

        # Use configurable concurrency from settings
        # Default: 5 for regular backtesting (balanced), can be increased via MAX_CONCURRENT_ANALYSES env var
        # For ML training with >3000 stocks, set MAX_CONCURRENT_ANALYSES=10 for faster processing
        from config.settings import MAX_CONCURRENT_ANALYSES
        async_service = AsyncAnalysisService(max_concurrent=MAX_CONCURRENT_ANALYSES)
        results = await async_service.analyze_batch_async(
            tickers=tickers,
            enable_multi_timeframe=enable_multi_timeframe,
            export_to_csv=export_csv
        )

        logger.info(f"Async analysis complete: {len(results)} results")

        # Process results (scoring, backtest, Telegram)
        return _process_results(results, enable_backtest_scoring, dip_mode)

    except ImportError:
        logger.warning("Async service not available, falling back to sequential analysis")
        # Fall back to sequential analysis
        return main_sequential(export_csv, enable_multi_timeframe, enable_backtest_scoring, dip_mode)


def main_sequential(export_csv=True, enable_multi_timeframe=True, enable_backtest_scoring=False, dip_mode=False):
    """
    Sequential main function (backward compatible)

    Uses traditional sequential analysis for backward compatibility.
    """
    tickers = get_stocks()

    if not tickers:
        logger.error("No stocks to analyze. Exiting.")
        return

    logger.info(f"Starting sequential analysis for {len(tickers)} stocks (Multi-timeframe: {enable_multi_timeframe}, CSV Export: {export_csv})")

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

    # Continue with scoring and Telegram (same for both async and sequential)
    return _process_results(results, enable_backtest_scoring, dip_mode)


def main(export_csv=True, enable_multi_timeframe=True, enable_backtest_scoring=False, dip_mode=False, use_async=True):
    """
    Main function - supports both async and sequential modes

    Args:
        export_csv: Export results to CSV
        enable_multi_timeframe: Enable multi-timeframe analysis
        enable_backtest_scoring: Enable backtest scoring
        dip_mode: Enable dip-buying mode
        use_async: Use async batch analysis (Phase 2 feature, default: True)
    """
    if use_async:
        # Use async analysis (Phase 2)
        try:
            import asyncio
            return asyncio.run(main_async(
                export_csv=export_csv,
                enable_multi_timeframe=enable_multi_timeframe,
                enable_backtest_scoring=enable_backtest_scoring,
                dip_mode=dip_mode
            ))
        except Exception as e:
            logger.warning(f"Async analysis failed, falling back to sequential: {e}")
            return main_sequential(
                export_csv=export_csv,
                enable_multi_timeframe=enable_multi_timeframe,
                enable_backtest_scoring=enable_backtest_scoring,
                dip_mode=dip_mode
            )
    else:
        # Use sequential analysis (backward compatible)
        return main_sequential(
            export_csv=export_csv,
            enable_multi_timeframe=enable_multi_timeframe,
            enable_backtest_scoring=enable_backtest_scoring,
            dip_mode=dip_mode
        )


def _process_results(results, enable_backtest_scoring=False, dip_mode=False):
    """Process analysis results (common for both async and sequential)"""

    # Calculate strength scores for all results (needed for backtest scoring)
    # Also add ML verdict predictions if ML service is available (for testing)
    for result in results:
        if result.get('status') == 'success':
            result['strength_score'] = compute_strength_score(result)

            # ML predictions are now handled in AnalysisService (2025-11-11)
            # No need to re-predict here - just use what analysis_service provided
            # Legacy code removed to prevent overwriting initial ML predictions
            
            # ML verdict and confidence should already be in result from analysis_service
            # If not present, that's OK - stock may not have had ML prediction
            if 'ml_verdict' not in result or result.get('ml_verdict') is None:
                logger.debug(f"{result.get('ticker')}: No ML prediction from analysis (chart quality may have failed)")
            else:
                logger.debug(f"{result.get('ticker')}: ML prediction from analysis: {result.get('ml_verdict')} ({result.get('ml_confidence')}%)")

    # Add backtest scoring if enabled (Phase 4: Use BacktestService)
    if enable_backtest_scoring:
        mode_info = " (DIP MODE)" if dip_mode else ""
        logger.info(f"Running backtest scoring analysis{mode_info}...")
        # Use BacktestService (Phase 4)
        backtest_service = BacktestService(default_years_back=2, dip_mode=dip_mode)
        results = backtest_service.add_backtest_scores_to_results(results)
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
            # Added: More fields for ML training data collection and verdict analysis (2025-11-09)
            cols = [
                'ticker','status','verdict','final_verdict','combined_score','strength_score','last_close',
                'buy_range','target','stop','timeframe_analysis','backtest',
                'execution_capital','max_capital','capital_adjusted','chart_quality',  # Phase 12: New fields
                # Verdict analysis fields
                'justification','pe','pb','rsi','avg_vol','today_vol',
                # ML PREDICTION (2025-11-11): ML monitoring data
                'ml_verdict','ml_confidence','ml_probabilities',
                # ML training fields - volume data
                'volume_analysis','volume_pattern','volume_description','vol_ok','vol_strong','volume_ratio','volume_quality',
                # ML training fields - signals and indicators
                'signals','candle_analysis','is_above_ema200',
                # ML training fields - fundamental data
                'fundamental_assessment','fundamental_ok',
                # ML training fields - timeframe data (already in timeframe_analysis but extracted for clarity)
                'news_sentiment',
                # ML training fields - chart quality details
                'chart_quality',
                # ML ENHANCED DIP FEATURES (2025-01-10): Advanced features for dip-buying strategy
                'dip_depth_from_20d_high_pct','consecutive_red_days','dip_speed_pct_per_day',
                'decline_rate_slowing','volume_green_vs_red_ratio','support_hold_count'
            ]
            def _flatten(row):
                d = {k: row.get(k) for k in cols if k in row}
                # Simple stringify for complex fields
                for k in ('buy_range','timeframe_analysis','backtest','volume_analysis','candle_analysis','news_sentiment','chart_quality','fundamental_assessment'):
                    if k in d and not isinstance(d[k], (str,int,float,bool)):
                        d[k] = str(d[k])

                # Extract vol_ok, vol_strong, volume_ratio, volume_quality from volume_analysis if available
                # But prefer direct fields if they exist (added in analysis_service.py)
                if 'vol_ok' not in d or d['vol_ok'] is None:
                    if 'volume_analysis' in d and isinstance(d['volume_analysis'], dict):
                        vol_analysis = d['volume_analysis']
                        d['vol_ok'] = vol_analysis.get('vol_ok', None)
                        d['vol_strong'] = vol_analysis.get('vol_strong', None)
                        d['volume_ratio'] = vol_analysis.get('volume_ratio', None)
                        d['volume_quality'] = vol_analysis.get('quality', None)
                    elif isinstance(row.get('volume_analysis'), dict):
                        vol_analysis = row.get('volume_analysis')
                        d['vol_ok'] = vol_analysis.get('vol_ok', None)
                        d['vol_strong'] = vol_analysis.get('vol_strong', None)
                        d['volume_ratio'] = vol_analysis.get('volume_ratio', None)
                        d['volume_quality'] = vol_analysis.get('quality', None)

                # Extract fundamental assessment fields if available
                if 'fundamental_assessment' in d and isinstance(d['fundamental_assessment'], dict):
                    fa = d['fundamental_assessment']
                    d['fundamental_growth_stock'] = fa.get('fundamental_growth_stock', None)
                    d['fundamental_avoid'] = fa.get('fundamental_avoid', None)
                    d['fundamental_reason'] = fa.get('fundamental_reason', None)

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
    parser.add_argument('--async', action='store_true', dest='use_async', default=True, help='Use async batch analysis (Phase 2, default: enabled)')
    parser.add_argument('--no-async', action='store_false', dest='use_async', help='Disable async analysis (use sequential)')

    args = parser.parse_args()

    main(
        export_csv=not args.no_csv,
        enable_multi_timeframe=not args.no_mtf,
        enable_backtest_scoring=args.backtest,
        dip_mode=getattr(args, 'dip_mode', False),
        use_async=args.use_async
    )
