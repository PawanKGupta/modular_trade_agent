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
    
    import yfinance as yf
    import numpy as np
    import pandas as pd


def calculate_backtest_score(backtest_results: Dict) -> float:
    """
    Calculate a backtest score based on performance metrics.
    
    Score components:
    - Total return percentage (40%)
    - Win rate (30%) 
    - Strategy vs buy-and-hold performance (20%)
    - Trade execution rate (10%)
    
    Returns:
        Float score between 0-100
    """
    
    if not backtest_results or backtest_results.get('total_positions', 0) == 0:
        return 0.0
    
    try:
        # Component 1: Total Return (40% weight)
        total_return = backtest_results.get('total_return_pct', 0)
        return_score = min(max(total_return, 0), 100) * 0.4  # Cap at 100%
        
        # Component 2: Win Rate (30% weight)  
        win_rate = backtest_results.get('win_rate', 0)
        win_score = win_rate * 0.3
        
        # Component 3: Strategy vs Buy & Hold (20% weight)
        vs_buyhold = backtest_results.get('strategy_vs_buy_hold', 0)
        alpha_score = min(max(vs_buyhold + 50, 0), 100) * 0.2  # Normalize around 50
        
        # Component 4: Trade Execution Rate (10% weight)
        execution_rate = backtest_results.get('trade_agent_accuracy', 0)
        execution_score = execution_rate * 0.1
        
        total_score = return_score + win_score + alpha_score + execution_score
        
        logger.debug(f"Backtest score breakdown: Return={return_score:.1f}, Win={win_score:.1f}, "
                    f"Alpha={alpha_score:.1f}, Exec={execution_score:.1f}, Total={total_score:.1f}")
        
        return min(total_score, 100.0)  # Cap at 100
        
    except Exception as e:
        logger.error(f"Error calculating backtest score: {e}")
        return 0.0


def calculate_wilder_rsi(prices, period=10):
    """Calculate RSI using Wilder's method (matches your trading strategy)"""
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


def run_simple_backtest(stock_symbol: str, years_back: int = 2) -> Dict:
    """
    Run a simple backtest using RSI 10 oversold strategy.
    
    Strategy:
    - Buy when RSI10 < 30 (oversold) and above EMA200
    - Sell at 8% target or 5% stop loss
    """
    
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
        
        # Calculate indicators
        data['RSI10'] = calculate_wilder_rsi(data['Close'], 10)
        data['EMA20'] = data['Close'].ewm(span=20).mean()
        data['EMA50'] = data['Close'].ewm(span=50).mean()
        data['EMA200'] = data['Close'].ewm(span=200).mean()
        
        # Strategy logic
        positions = []
        current_position = None
        
        for i, (date, row) in enumerate(data.iterrows()):
            if pd.isna(row['RSI10']):
                continue
                
            # Entry condition: RSI10 < 30 and above EMA200
            if current_position is None and row['RSI10'] < 30 and row['Close'] > row['EMA200']:
                current_position = {
                    'entry_date': date,
                    'entry_price': row['Close'],
                    'target_price': row['Close'] * 1.08,  # 8% target
                    'stop_loss': row['Close'] * 0.95     # 5% stop
                }
                continue
            
            # Exit conditions
            if current_position is not None:
                hit_target = row['High'] >= current_position['target_price']
                hit_stop = row['Low'] <= current_position['stop_loss']
                
                if hit_target or hit_stop:
                    exit_price = current_position['target_price'] if hit_target else current_position['stop_loss']
                    exit_reason = "Target" if hit_target else "Stop Loss"
                    
                    pnl_pct = ((exit_price - current_position['entry_price']) / current_position['entry_price']) * 100
                    
                    positions.append({
                        'entry_date': current_position['entry_date'],
                        'entry_price': current_position['entry_price'],
                        'exit_date': date,
                        'exit_price': exit_price,
                        'exit_reason': exit_reason,
                        'pnl_pct': pnl_pct,
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
                'execution_rate': 100.0
            }
        
        total_trades = len(positions)
        winning_trades = sum(1 for p in positions if p['winner'])
        win_rate = (winning_trades / total_trades) * 100
        
        avg_return = np.mean([p['pnl_pct'] for p in positions])
        total_return = sum(p['pnl_pct'] for p in positions)
        
        # Buy and hold comparison
        first_price = data.iloc[0]['Close']
        last_price = data.iloc[-1]['Close']
        buy_hold_return = ((last_price - first_price) / first_price) * 100
        
        vs_buy_hold = total_return - buy_hold_return
        
        logger.info(f"Simple backtest for {stock_symbol}: "
                   f"{total_trades} trades, {win_rate:.1f}% win rate, "
                   f"{total_return:.1f}% return")
        
        return {
            'symbol': stock_symbol,
            'backtest_score': 0,  # Will be calculated later
            'total_return_pct': total_return,
            'win_rate': win_rate,
            'total_trades': total_trades,
            'vs_buy_hold': vs_buy_hold,
            'execution_rate': 100.0,
            'avg_return': avg_return,
            'winning_trades': winning_trades,
            'losing_trades': total_trades - winning_trades
        }
        
    except Exception as e:
        logger.error(f"Simple backtest failed for {stock_symbol}: {e}")
        return {
            'symbol': stock_symbol,
            'backtest_score': 0.0,
            'error': str(e)
        }


def run_stock_backtest(stock_symbol: str, years_back: int = 2) -> Dict:
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
        backtest_results = run_simple_backtest(stock_symbol, years_back)
        backtest_score = calculate_backtest_score(backtest_results)
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
            backtest_score = calculate_backtest_score(backtest_results)
            
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
            backtest_results = run_simple_backtest(stock_symbol, years_back)
            backtest_score = calculate_backtest_score(backtest_results)
            backtest_results['backtest_score'] = backtest_score
            return backtest_results


def add_backtest_scores_to_results(stock_results: list, years_back: int = 2) -> list:
    """
    Add backtest scores to existing stock analysis results.
    
    Args:
        stock_results: List of stock analysis results
        years_back: Years of historical data to analyze
        
    Returns:
        Enhanced stock results with backtest scores
    """
    
    logger.info(f"Adding backtest scores for {len(stock_results)} stocks...")
    
    enhanced_results = []
    
    for i, stock_result in enumerate(stock_results, 1):
        try:
            ticker = stock_result.get('ticker', 'Unknown')
            logger.info(f"Processing {i}/{len(stock_results)}: {ticker}")
            
            # Run backtest for this stock
            backtest_data = run_stock_backtest(ticker, years_back)
            
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
            
            logger.info(f"  {ticker}: Current={current_score:.1f}, Backtest={backtest_score:.1f}, Combined={combined_score:.1f}")
            
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