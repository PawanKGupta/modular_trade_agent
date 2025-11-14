#!/usr/bin/env python3
"""
Backtest Scoring Module

This module integrates historical backtesting into the trading agent workflow
to provide additional scoring based on past performance of the trading strategy.
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import logger first
from utils.logger import logger

try:
    from integrated_backtest import run_integrated_backtest
    BACKTEST_MODE = 'integrated'
except ImportError as e:
    logger.warning(f"Integrated backtest not available: {e}, using simple backtest")
    run_integrated_backtest = None
    BACKTEST_MODE = 'simple'

# Always import these for simple backtest fallback
import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


def calculate_backtest_score(backtest_results: Dict, dip_mode: bool = False) -> float:
    """
    Calculate a backtest score based on performance metrics.

    Score components:
    - Annualized return percentage (40%)
    - Win rate (40%)
    - Strategy vs buy-and-hold performance (20%)
    - No trade frequency penalty (quality over quantity for reversals)

    Enhanced with:
    - Mild confidence adjustment for very low sample sizes
    - Pure focus on reversal quality over entire backtest period

    Returns:
        Float score between 0-100
    """

    if not backtest_results or backtest_results.get('total_positions', 0) == 0:
        return 0.0

    try:
        # Calculate annualized return based on actual trading days
        total_return = backtest_results.get('total_return_pct', 0)
        total_trades = backtest_results.get('total_trades', 0)

        # Estimate average holding period (assume 15 days if no position data available)
        avg_holding_days = 15  # Default assumption
        if 'full_results' in backtest_results and backtest_results['full_results'].get('positions'):
            positions = backtest_results['full_results']['positions']
            if positions:
                total_days = 0
                valid_positions = 0
                for pos in positions:
                    if pos.get('entry_date') and pos.get('exit_date'):
                        from datetime import datetime
                        entry = datetime.strptime(pos['entry_date'], '%Y-%m-%d')
                        exit = datetime.strptime(pos['exit_date'], '%Y-%m-%d')
                        days = (exit - entry).days
                        total_days += days
                        valid_positions += 1
                if valid_positions > 0:
                    avg_holding_days = total_days / valid_positions

        # For reversal strategy, use total return directly (avoid extreme annualization)
        # Reversals are about absolute performance over the backtest period
        effective_return = total_return

        # Component 1: Total Return (40% weight) - Focus on reversal performance quality
        # Scale: 0-10% -> 0-50 points, 10%+ -> 50-100 points (more appropriate for reversals)
        if effective_return <= 10:
            return_score = (effective_return / 10) * 50 * 0.4
        else:
            return_score = (50 + min((effective_return - 10) * 2.5, 50)) * 0.4

        # Component 2: Win Rate (40% weight) - High importance for reversal consistency
        win_rate = backtest_results.get('win_rate', 0)
        win_score = win_rate * 0.4

        # Component 3: Strategy vs Buy & Hold (20% weight)
        vs_buyhold = backtest_results.get('strategy_vs_buy_hold', 0)
        alpha_score = min(max(vs_buyhold + 50, 0), 100) * 0.2

        # No trade frequency component - quality over quantity for reversal strategy

        # Calculate base score (no trade frequency penalty)
        base_score = return_score + win_score + alpha_score

        # Enhancement 1: Mild confidence adjustment for reversal strategy
        confidence_factor = 1.0
        if total_trades < 3:  # Only penalize very low sample sizes
            confidence_factor = 0.8 + (total_trades / 10)  # 80-100% confidence (mild penalty)
            logger.debug(f"Applied confidence adjustment: {confidence_factor:.2f} for {total_trades} trades")

        # No recent performance boost - reversal quality is consistent over time
        recent_boost = 1.0

        # Apply enhancements (confidence adjustment only)
        total_score = base_score * confidence_factor

        logger.debug(f"Backtest score breakdown: Total Return={effective_return:.1f}% ({return_score:.1f}), "
                    f"Win={win_rate:.1f}% ({win_score:.1f}), Alpha={alpha_score:.1f}, "
                    f"Trades={total_trades}, Total={total_score:.1f}")

        return min(total_score, 100.0)  # Cap at 100

    except Exception as e:
        logger.error(f"Error calculating backtest score: {e}")
        return 0.0


def calculate_wilder_rsi(prices, period=None, config=None):
    """
    Calculate RSI using Wilder's method (matches your trading strategy)

    Args:
        prices: Price series
        period: RSI period (uses config if None)
        config: StrategyConfig instance (uses default if None)
    """
    from config.strategy_config import StrategyConfig

    # Get config if not provided
    if config is None:
        config = StrategyConfig.default()

    # Use provided period or config default
    period = period if period is not None else config.rsi_period

    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    # Wilder's smoothing using exponential moving average with alpha = 1/period
    alpha = 1.0 / period
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def run_simple_backtest(stock_symbol: str, years_back: int = 2, dip_mode: bool = False, config=None) -> Dict:
    """
    Run a simple backtest using configurable RSI oversold strategy.

    Strategy:
    - Buy when RSI < 30 (oversold) and above EMA200
    - Sell at 8% target or 5% stop loss
    - Uses dynamic capital based on liquidity
    - Filters by chart quality if enabled

    Args:
        stock_symbol: Stock symbol to backtest
        years_back: Number of years to look back
        dip_mode: Enable dip mode (more permissive volume requirements)
        config: StrategyConfig instance (uses default if None)
    """
    from config.strategy_config import StrategyConfig
    from services.chart_quality_service import ChartQualityService
    from services.liquidity_capital_service import LiquidityCapitalService

    # Get config if not provided
    if config is None:
        config = StrategyConfig.default()

    # Initialize services
    chart_quality_service = ChartQualityService(config=config)
    liquidity_capital_service = LiquidityCapitalService(config=config)

    try:
        # Get historical data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years_back * 365)

        logger.info(f"Running simple backtest for {stock_symbol}")

        # Download data
        data = yf.download(stock_symbol, start=start_date, end=end_date, progress=False)

        if data.empty:
            logger.warning(f"No data available for {stock_symbol}")
            return {'symbol': stock_symbol, 'backtest_score': 0.0, 'error': 'No data'}

        # Handle MultiIndex columns if present
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        # Phase 9: Check chart quality if enabled in backtest
        chart_quality_enabled = getattr(config, 'chart_quality_enabled_in_backtest', True)
        chart_quality_data = None
        if chart_quality_enabled:
            chart_quality_data = chart_quality_service.assess_chart_quality(data)
            if not chart_quality_data.get('passed', True):
                logger.info(f"{stock_symbol}: Chart quality failed in backtest - {chart_quality_data.get('reason', 'Poor chart quality')}")
                return {
                    'symbol': stock_symbol,
                    'backtest_score': 0.0,
                    'total_return_pct': 0,
                    'win_rate': 0,
                    'total_trades': 0,
                    'vs_buy_hold': 0,
                    'execution_rate': 100.0,
                    'chart_quality': chart_quality_data,
                    'reason': 'Chart quality failed'
                }

        # Calculate indicators using configurable RSI period
        rsi_col = f'RSI{config.rsi_period}'
        data[rsi_col] = calculate_wilder_rsi(data['Close'], period=config.rsi_period, config=config)

        # Also keep 'RSI10' for backward compatibility if period is 10
        if config.rsi_period == 10:
            data['RSI10'] = data[rsi_col]

        data['EMA20'] = data['Close'].ewm(span=20).mean()
        data['EMA50'] = data['Close'].ewm(span=50).mean()
        data['EMA200'] = data['Close'].ewm(span=200).mean()

        # Calculate volume indicators for filtering and capital calculation
        data['Volume_SMA20'] = data['Volume'].rolling(20).mean()
        data['Volume_Ratio'] = data['Volume'] / data['Volume_SMA20']

        # Strategy logic
        positions = []
        current_position = None

        for i, (date, row) in enumerate(data.iterrows()):
            rsi_value = row[rsi_col] if rsi_col in row.index else row.get('RSI10')
            if pd.isna(rsi_value):
                continue

            # Entry condition: RSI < oversold threshold, above EMA200, and adequate volume
            # Dip mode: More permissive volume requirements for extreme oversold conditions
            extreme_oversold_threshold = config.rsi_extreme_oversold if hasattr(config, 'rsi_extreme_oversold') else 20
            if dip_mode and rsi_value < extreme_oversold_threshold:  # Extreme oversold in dip mode
                volume_threshold = 1.0  # Any volume OK for extreme dips
            else:
                volume_threshold = 1.2 if not dip_mode else 1.1  # Relaxed in dip mode

            if (current_position is None and
                rsi_value < config.rsi_oversold and
                row['Close'] > row['EMA200'] and
                not pd.isna(row['Volume_Ratio']) and
                row['Volume_Ratio'] > volume_threshold):

                # Phase 9: Calculate execution capital based on liquidity at entry
                avg_volume = row.get('Volume_SMA20', row['Volume'])
                stock_price = row['Close']
                capital_data = liquidity_capital_service.calculate_execution_capital(
                    avg_volume=avg_volume,
                    stock_price=stock_price
                )
                execution_capital = capital_data.get('execution_capital', config.user_capital)

                # Calculate position size (shares) based on execution capital
                shares = int(execution_capital / stock_price) if stock_price > 0 else 0

                # Skip if capital is too low (below minimum threshold)
                if execution_capital < 1000:  # Minimum 1K capital
                    logger.debug(f"{stock_symbol}: Skipping trade at {date} - insufficient capital: {execution_capital:.0f}")
                    continue

                current_position = {
                    'entry_date': date,
                    'entry_price': row['Close'],
                    'target_price': row['Close'] * 1.08,  # 8% target
                    'stop_loss': row['Close'] * 0.95,     # 5% stop
                    'volume_ratio': row['Volume_Ratio'],   # Track volume quality
                    'execution_capital': execution_capital,  # Track capital used
                    'shares': shares,  # Track position size
                    'avg_volume': avg_volume  # Track liquidity
                }
                continue

            # Exit conditions
            if current_position is not None:
                hit_target = row['High'] >= current_position['target_price']
                hit_stop = row['Low'] <= current_position['stop_loss']

                if hit_target or hit_stop:
                    exit_price = current_position['target_price'] if hit_target else current_position['stop_loss']
                    exit_reason = "Target" if hit_target else "Stop Loss"

                    # Calculate P&L based on position size and price movement
                    shares = current_position.get('shares', 0)
                    entry_price = current_position['entry_price']
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                    pnl_absolute = (exit_price - entry_price) * shares
                    execution_capital = current_position.get('execution_capital', 0)
                    roi = (pnl_absolute / execution_capital * 100) if execution_capital > 0 else 0

                    positions.append({
                        'entry_date': current_position['entry_date'],
                        'entry_price': entry_price,
                        'exit_date': date,
                        'exit_price': exit_price,
                        'exit_reason': exit_reason,
                        'pnl_pct': pnl_pct,
                        'pnl_absolute': pnl_absolute,
                        'execution_capital': execution_capital,
                        'shares': shares,
                        'roi': roi,
                        'winner': pnl_pct > 0
                    })

                    current_position = None

        # Calculate performance metrics
        if not positions:
            return {
                'symbol': stock_symbol,
                'backtest_score': 0.0,
                'total_return_pct': 0,
                'win_rate': 0,
                'total_trades': 0,
                'vs_buy_hold': 0,
                'execution_rate': 100.0,
                'chart_quality': chart_quality_data
            }

        total_trades = len(positions)
        winning_trades = sum(1 for p in positions if p['winner'])
        win_rate = (winning_trades / total_trades) * 100

        # Calculate returns based on weighted average (by capital)
        # This gives better representation of actual returns when capital varies
        total_capital = sum(p.get('execution_capital', 0) for p in positions)
        total_pnl = sum(p.get('pnl_absolute', 0) for p in positions)

        # Calculate average return (percentage)
        avg_return = np.mean([p['pnl_pct'] for p in positions])

        # Total return as weighted ROI (total P&L / total capital)
        # This gives accurate return when capital varies per trade
        if total_capital > 0:
            total_return = (total_pnl / total_capital) * 100
        else:
            # Fallback to average percentage return if no capital data
            total_return = avg_return * len(positions)

        # Also calculate total return as sum of percentage returns (legacy compatibility)
        total_return_pct = sum(p['pnl_pct'] for p in positions)

        # Buy and hold comparison
        first_price = data.iloc[0]['Close']
        last_price = data.iloc[-1]['Close']
        buy_hold_return = ((last_price - first_price) / first_price) * 100

        vs_buy_hold = total_return - buy_hold_return

        # Calculate average execution capital
        avg_execution_capital = np.mean([p.get('execution_capital', 0) for p in positions])

        logger.info(f"Simple backtest for {stock_symbol}: "
                   f"{total_trades} trades, {win_rate:.1f}% win rate, "
                   f"{total_return:.1f}% return (weighted), {total_pnl:.0f} total P&L")

        result = {
            'symbol': stock_symbol,
            'backtest_score': 0,  # Will be calculated later
            'total_return_pct': total_return,  # Weighted average ROI
            'total_return_pct_legacy': total_return_pct,  # Sum of percentage returns (legacy)
            'win_rate': win_rate,
            'total_trades': total_trades,
            'vs_buy_hold': vs_buy_hold,
            'execution_rate': 100.0,
            'avg_return': avg_return,
            'winning_trades': winning_trades,
            'losing_trades': total_trades - winning_trades,
            'total_pnl': total_pnl,
            'avg_execution_capital': avg_execution_capital,
            'chart_quality': chart_quality_data
        }

        return result

    except Exception as e:
        logger.error(f"Simple backtest failed for {stock_symbol}: {e}")
        return {
            'symbol': stock_symbol,
            'backtest_score': 0.0,
            'error': str(e)
        }


def run_stock_backtest(stock_symbol: str, years_back: int = 2, dip_mode: bool = False, config=None) -> Dict:
    """
    Run backtest for a stock using available method (integrated or simple).

    Args:
        stock_symbol: Stock symbol (e.g., "RELIANCE.NS")
        years_back: Number of years to backtest (default: 2)

    Returns:
        Dict with backtest results and score
    """

    if BACKTEST_MODE == 'simple':
        # Use simple backtest
        backtest_results = run_simple_backtest(stock_symbol, years_back, dip_mode, config)
        backtest_score = calculate_backtest_score(backtest_results, dip_mode)
        backtest_results['backtest_score'] = backtest_score
        return backtest_results

    else:
        # Use integrated backtest
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=years_back * 365)

            date_range = (
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )

            logger.info(f"Running {years_back}-year integrated backtest for {stock_symbol}")

            # Run integrated backtest with smaller capital to speed up
            backtest_results = run_integrated_backtest(
                stock_name=stock_symbol,
                date_range=date_range,
                capital_per_position=50000  # Reduced for faster execution
            )

            # Calculate backtest score
            backtest_score = calculate_backtest_score(backtest_results, dip_mode)

            # Return summary with score
            return {
                'symbol': stock_symbol,
                'period': f"{date_range[0]} to {date_range[1]}",
                'backtest_score': backtest_score,
                'total_return_pct': backtest_results.get('total_return_pct', 0),
                'win_rate': backtest_results.get('win_rate', 0),
                'total_trades': backtest_results.get('executed_trades', 0),
                'vs_buy_hold': backtest_results.get('strategy_vs_buy_hold', 0),
                'execution_rate': backtest_results.get('trade_agent_accuracy', 0),
                'full_results': backtest_results
            }

        except Exception as e:
            logger.error(f"Integrated backtest failed for {stock_symbol}: {e}, falling back to simple")
            # Fallback to simple backtest
            backtest_results = run_simple_backtest(stock_symbol, years_back, dip_mode, config)
            backtest_score = calculate_backtest_score(backtest_results, dip_mode)
            backtest_results['backtest_score'] = backtest_score
            return backtest_results


def add_backtest_scores_to_results(stock_results: list, years_back: int = 2, dip_mode: bool = False, config=None) -> list:
    """
    Add backtest scores to existing stock analysis results.

    ⚠️ DEPRECATED in Phase 4: This function is deprecated and will be removed in a future version.

    For new code, prefer using BacktestService:
        from services import BacktestService
        service = BacktestService(default_years_back=years_back, dip_mode=dip_mode)
        enhanced_results = service.add_backtest_scores_to_results(stock_results)

    Migration guide: See utils.deprecation.get_migration_guide("add_backtest_scores_to_results")

    Args:
        stock_results: List of stock analysis results
        years_back: Years of historical data to analyze
        dip_mode: Enable dip-buying mode

    Returns:
        Enhanced stock results with backtest scores
    """
    # Phase 4: Issue deprecation warning
    import warnings
    from utils.deprecation import deprecation_notice

    deprecation_notice(
        module="core.backtest_scoring",
        function="add_backtest_scores_to_results",
        replacement="services.BacktestService.add_backtest_scores_to_results()",
        version="Phase 4"
    )

    logger.info(f"Adding backtest scores for {len(stock_results)} stocks...")

    enhanced_results = []

    for i, stock_result in enumerate(stock_results, 1):
        try:
            ticker = stock_result.get('ticker', 'Unknown')
            logger.info(f"Processing {i}/{len(stock_results)}: {ticker}")

            # Run backtest for this stock
            backtest_data = run_stock_backtest(ticker, years_back, dip_mode, config)

            # Add backtest data to stock result
            stock_result['backtest'] = {
                'score': backtest_data.get('backtest_score', 0),
                'total_return_pct': backtest_data.get('total_return_pct', 0),
                'win_rate': backtest_data.get('win_rate', 0),
                'total_trades': backtest_data.get('total_trades', 0),
                'vs_buy_hold': backtest_data.get('vs_buy_hold', 0),
                'execution_rate': backtest_data.get('execution_rate', 0)
            }

            # Calculate combined score (50% current analysis + 50% backtest)
            current_score = stock_result.get('strength_score', 0)
            backtest_score = backtest_data.get('backtest_score', 0)
            combined_score = (current_score * 0.5) + (backtest_score * 0.5)

            stock_result['combined_score'] = combined_score

            # Re-classify based on combined score and key metrics
            mtf_score = 0
            if stock_result.get('timeframe_analysis'):
                mtf_score = stock_result['timeframe_analysis'].get('alignment_score', 0)

            # Get trade count for confidence assessment
            trade_count = backtest_data.get('total_trades', 0)

            # Get current RSI for dynamic threshold adjustment
            current_rsi = stock_result.get('rsi', 30)  # Default to 30 if not available

            # RSI-based threshold adjustment (more oversold = lower thresholds)
            # Use configurable thresholds from StrategyConfig
            from config.strategy_config import StrategyConfig
            config = StrategyConfig.default()

            rsi_factor = 1.0
            extreme_oversold = config.rsi_extreme_oversold  # Default: 20
            rsi_oversold = config.rsi_oversold  # Default: 30

            if current_rsi < extreme_oversold:  # Extremely oversold
                rsi_factor = 0.7  # 30% lower thresholds
            elif current_rsi < (extreme_oversold + 5):  # Very oversold (default: 25)
                rsi_factor = 0.8  # 20% lower thresholds
            elif current_rsi < rsi_oversold:  # Oversold
                rsi_factor = 0.9  # 10% lower thresholds

            # Enhanced reclassification with confidence-aware and RSI-adjusted thresholds
            # FIXED: Reduced thresholds to be less conservative (Issue #1)
            if trade_count >= 5:
                # High confidence thresholds (adjusted by RSI)
                strong_buy_threshold = 60 * rsi_factor
                combined_strong_threshold = 35 * rsi_factor
                combined_exceptional_threshold = 60 * rsi_factor

                buy_threshold = 35 * rsi_factor  # Reduced from 40
                combined_buy_threshold = 22 * rsi_factor  # Reduced from 25
                combined_decent_threshold = 35 * rsi_factor  # Reduced from 40

                if (backtest_score >= strong_buy_threshold and combined_score >= combined_strong_threshold) or combined_score >= combined_exceptional_threshold:
                    stock_result['final_verdict'] = 'strong_buy'
                elif (backtest_score >= buy_threshold and combined_score >= combined_buy_threshold) or combined_score >= combined_decent_threshold:
                    stock_result['final_verdict'] = 'buy'
                else:
                    stock_result['final_verdict'] = 'watch'
            else:
                # Lower confidence thresholds (adjusted by RSI)
                # FIXED: Made less conservative for low trade counts
                strong_buy_threshold = 65 * rsi_factor  # Reduced from 70
                combined_strong_threshold = 42 * rsi_factor  # Reduced from 45
                combined_exceptional_threshold = 65 * rsi_factor  # Reduced from 70

                buy_threshold = 40 * rsi_factor  # Reduced from 50
                combined_buy_threshold = 28 * rsi_factor  # Reduced from 35
                combined_decent_threshold = 45 * rsi_factor  # Reduced from 50

                if (backtest_score >= strong_buy_threshold and combined_score >= combined_strong_threshold) or combined_score >= combined_exceptional_threshold:
                    stock_result['final_verdict'] = 'strong_buy'
                elif (backtest_score >= buy_threshold and combined_score >= combined_buy_threshold) or combined_score >= combined_decent_threshold:
                    stock_result['final_verdict'] = 'buy'
                else:
                    stock_result['final_verdict'] = 'watch'

            # Log RSI adjustment if applied
            if rsi_factor < 1.0:
                logger.debug(f"{ticker}: RSI={current_rsi:.1f}, applied {(1-rsi_factor)*100:.0f}% threshold reduction")

            # Add confidence indicator to result
            confidence_level = "High" if trade_count >= 5 else "Medium" if trade_count >= 2 else "Low"
            stock_result['backtest_confidence'] = confidence_level

            # FIXED: Recalculate trading parameters if verdict was upgraded (Issue #2)
            # Check if verdict was upgraded to buy/strong_buy but parameters are missing
            # ALSO check ML verdict (for ML-only buy/strong_buy signals)
            needs_params = stock_result['final_verdict'] in ['buy', 'strong_buy']
            
            # Check ML verdict if available (for "ONLY ML" signals)
            ml_verdict = stock_result.get('ml_verdict')
            if ml_verdict and ml_verdict in ['buy', 'strong_buy']:
                needs_params = True
                
            if needs_params:
                if not stock_result.get('buy_range') or not stock_result.get('target') or not stock_result.get('stop'):
                    logger.info(f"  {ticker}: Recalculating trading parameters (verdict: {stock_result['final_verdict']}, ML: {ml_verdict})")

                    try:
                        from core.analysis import calculate_smart_buy_range, calculate_smart_stop_loss, calculate_smart_target
                        import pandas as pd

                        # Get current price (try multiple sources)
                        current_price = stock_result.get('last_close')
                        
                        # Fallback 1: Try to get from pre_fetched_df if available
                        if (not current_price or current_price <= 0) and 'pre_fetched_df' in stock_result:
                            try:
                                pre_df = stock_result['pre_fetched_df']
                                if pre_df is not None and not pre_df.empty:
                                    current_price = float(pre_df['close'].iloc[-1])
                                    logger.debug(f"  {ticker}: Got current_price from pre_fetched_df: {current_price}")
                            except Exception as e:
                                logger.debug(f"  {ticker}: Failed to get price from pre_fetched_df: {e}")
                        
                        # Fallback 2: Try to get from stock_info if available
                        if (not current_price or current_price <= 0) and 'stock_info' in stock_result:
                            try:
                                info = stock_result['stock_info']
                                if isinstance(info, dict):
                                    current_price = info.get('currentPrice') or info.get('regularMarketPrice')
                                    if current_price:
                                        logger.debug(f"  {ticker}: Got current_price from stock_info: {current_price}")
                            except Exception as e:
                                logger.debug(f"  {ticker}: Failed to get price from stock_info: {e}")
                        
                        if current_price and current_price > 0:
                            timeframe_confirmation = stock_result.get('timeframe_analysis')

                            # Estimate recent low/high from current price if not available
                            recent_low = current_price * 0.92
                            recent_high = current_price * 1.15

                            # Calculate buy range (only takes 2 args: current_price, timeframe_confirmation)
                            buy_range = calculate_smart_buy_range(
                                current_price,
                                timeframe_confirmation
                            )

                            # Calculate stop loss
                            stop = calculate_smart_stop_loss(
                                current_price,
                                recent_low,
                                timeframe_confirmation,
                                None  # df
                            )

                            # Calculate target
                            target = calculate_smart_target(
                                current_price,
                                stop,
                                stock_result['final_verdict'],
                                timeframe_confirmation,
                                recent_high
                            )

                            # Update result with calculated parameters
                            stock_result['buy_range'] = buy_range
                            stock_result['target'] = target
                            stock_result['stop'] = stop

                            logger.info(f"  {ticker}: Calculated - Buy Range: {buy_range}, Target: {target}, Stop: {stop}")
                        else:
                            logger.warning(f"  {ticker}: Cannot calculate parameters - current_price is missing or zero")
                            # Set minimal defaults to prevent 0.00 display errors
                            # Use a placeholder price if absolutely nothing is available
                            stock_result['buy_range'] = None
                            stock_result['target'] = None
                            stock_result['stop'] = None

                    except Exception as calc_error:
                        logger.error(f"  {ticker}: Failed to recalculate parameters: {calc_error}")
                        # Set safe defaults to prevent telegram errors
                        if current_price and current_price > 0:
                            stock_result['buy_range'] = (round(current_price * 0.995, 2), round(current_price * 1.01, 2))
                            stock_result['stop'] = round(current_price * 0.92, 2)
                            stock_result['target'] = round(current_price * 1.10, 2)
                        else:
                            # No valid price available - set None to trigger filtering
                            logger.error(f"  {ticker}: No valid current_price available, cannot set parameters")
                            stock_result['buy_range'] = None
                            stock_result['target'] = None
                            stock_result['stop'] = None

            logger.info(f"  {ticker}: Current={current_score:.1f}, Backtest={backtest_score:.1f}, Combined={combined_score:.1f}, Final={stock_result['final_verdict']}")

            enhanced_results.append(stock_result)

        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
            # Still add the stock but without backtest data
            stock_result['backtest'] = {'score': 0, 'error': str(e)}
            stock_result['combined_score'] = stock_result.get('strength_score', 0)
            enhanced_results.append(stock_result)

    # Sort by combined score (highest first)
    enhanced_results.sort(key=lambda x: x.get('combined_score', 0), reverse=True)

    logger.info("Backtest scoring complete!")
    return enhanced_results


if __name__ == "__main__":
    # Test with a single stock
    test_symbol = "RELIANCE.NS"
    result = run_stock_backtest(test_symbol)
    print(f"Backtest score for {test_symbol}: {result['backtest_score']:.1f}")
