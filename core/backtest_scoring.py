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

try:
    from integrated_backtest import run_integrated_backtest
except ImportError as e:
    logger.error(f"Integrated backtest not available: {e}")
    run_integrated_backtest = None

from utils.logger import logger


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


def run_stock_backtest(stock_symbol: str, years_back: int = 2) -> Dict:
    """
    Run integrated backtest for a stock over specified period.
    
    Args:
        stock_symbol: Stock symbol (e.g., "RELIANCE.NS")
        years_back: Number of years to backtest (default: 2)
        
    Returns:
        Dict with backtest results and score
    """
    
    if run_integrated_backtest is None:
        logger.warning(f"Integrated backtest unavailable for {stock_symbol}")
        return {
            'symbol': stock_symbol,
            'backtest_score': 0.0,
            'error': 'Integrated backtest module not available'
        }
    
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years_back * 365)
        
        date_range = (
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        logger.info(f"Running {years_back}-year backtest for {stock_symbol}")
        
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
        logger.error(f"Backtest failed for {stock_symbol}: {e}")
        return {
            'symbol': stock_symbol,
            'backtest_score': 0.0,
            'error': str(e)
        }


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