
from core.analysis import analyze_ticker, analyze_multiple_tickers
from core.scoring import compute_strength_score
from core.telegram import send_telegram
from core.scrapping import get_stock_list
from core.csv_exporter import CSVExporter
from utils.logger import logger

def get_stocks():
    stocks = get_stock_list()
    # stocks = "NAVA, GLENMARK, VGL, HYUNDAI, ENRIN, OLECTRA, DDEVPLSTIK, CURAA, SUDARSCHEM, SMLISUZU"
    return [s.strip().upper() + ".NS" for s in stocks.split(",")]

def get_enhanced_stock_info(stock_data, rank, is_strong_buy=True):
    """Generate enhanced stock information for Telegram message"""
    try:
        ticker = stock_data['ticker']
        buy_low, buy_high = stock_data['buy_range']
        target = stock_data['target']
        stop = stock_data['stop']
        rsi = stock_data['rsi']
        last_close = stock_data['last_close']
        
        # Calculate potential returns
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
        
        # Build clean message
        msg = f"{rank}. *{ticker}*: Buy ({buy_low:.2f}-{buy_high:.2f})\n"
        msg += f"   Target {target:.2f} (+{potential_gain:.1f}%) | Stop {stop:.2f} (-{potential_loss:.1f}%)\n"
        msg += f"   RSI:{rsi}{mtf_info} RR:{risk_reward:.1f}x{setup_details}{fundamental_info}{volume_info}\n\n"
        
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

def main(export_csv=True, enable_multi_timeframe=True):
    tickers = get_stocks()
    
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

    results.sort(key=lambda x: -compute_strength_score(x))

    # Include both 'buy' and 'strong_buy' candidates
    buys = [r for r in results if r.get('verdict') in ['buy', 'strong_buy']]
    strong_buys = [r for r in results if r.get('verdict') == 'strong_buy']

    if buys:
        msg = "*Reversal Buy Candidates (today)*\n"
        
        # Highlight strong buys first
        if strong_buys:
            msg += "\n🔥 *STRONG BUY* (Multi-timeframe confirmed):\n"
            for i, b in enumerate(strong_buys, 1):
                enhanced_info = get_enhanced_stock_info(b, i)
                msg += enhanced_info
        
        # Regular buys
        regular_buys = [r for r in buys if r.get('verdict') == 'buy']
        if regular_buys:
            msg += "\n📈 *BUY* candidates:\n"
            for i, b in enumerate(regular_buys, 1):
                enhanced_info = get_enhanced_stock_info(b, i, is_strong_buy=False)
                msg += enhanced_info
        
        send_telegram(msg)
        logger.info(f"Sent Telegram alert for {len(buys)} buy candidates ({len(strong_buys)} strong buys)")
    else:
        logger.info("No buy candidates today.")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Stock Analysis with Multi-timeframe Confirmation')
    parser.add_argument('--no-csv', action='store_true', help='Disable CSV export')
    parser.add_argument('--no-mtf', action='store_true', help='Disable multi-timeframe analysis')
    
    args = parser.parse_args()
    
    main(
        export_csv=not args.no_csv,
        enable_multi_timeframe=not args.no_mtf
    )
