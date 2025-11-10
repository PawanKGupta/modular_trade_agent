"""
Backtest Command

CLI command for running backtests on analysis logic.
"""

import argparse
from typing import List

from ....infrastructure.web_scraping.chartink_scraper import ChartInkScraper
from utils.logger import logger


class BacktestCommand:
    """
    Command for backtesting strategies
    
    Handles CLI arguments and orchestrates backtesting workflow.
    """
    
    def __init__(self, scraper: ChartInkScraper):
        """
        Initialize command
        
        Args:
            scraper: Stock list scraper
        """
        self.scraper = scraper
    
    def execute(self, args: argparse.Namespace) -> int:
        """
        Execute backtest command
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code (0 = success)
        """
        try:
            # Get stock list
            tickers = self._get_tickers(args)
            
            if not tickers:
                logger.error("No stocks to backtest")
                return 1
            
            # Import backtest logic
            from integrated_backtest import run_integrated_backtest
            
            logger.info(f"Running backtest on {len(tickers)} stocks...")
            
            # Run backtest for each ticker
            results = []
            for ticker in tickers:
                try:
                    date_range = (args.start_date, args.end_date)
                    result = run_integrated_backtest(
                        stock_name=ticker,
                        date_range=date_range,
                        capital_per_position=100000
                    )
                    results.append(result)
                    logger.info(f"Backtest for {ticker}: {result.get('executed_trades', 0)} trades")
                except Exception as e:
                    logger.error(f"Backtest failed for {ticker}: {e}")
                    results.append({'ticker': ticker, 'error': str(e)})
            
            # Log summary
            if results:
                logger.info(f"Backtest complete: {len(results)} results")
                # Could add more detailed summary here
            
            return 0
            
        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            return 1
    
    def _get_tickers(self, args: argparse.Namespace) -> List[str]:
        """Get list of tickers to backtest"""
        # Check if specific tickers provided
        if hasattr(args, 'tickers') and args.tickers:
            tickers = args.tickers
            # Add .NS suffix if not present
            return [t if t.endswith('.NS') else f"{t}.NS" for t in tickers]
        
        # Otherwise scrape from ChartInk
        logger.info("Scraping stocks from ChartInk...")
        return self.scraper.get_stocks_with_suffix(".NS")
    
    @staticmethod
    def add_arguments(parser: argparse.ArgumentParser):
        """Add command-specific arguments to parser"""
        parser.add_argument(
            'tickers',
            nargs='*',
            help='Specific tickers to backtest (optional, otherwise scrapes from ChartInk)'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            default='2020-01-01',
            help='Backtest start date (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            default=None,
            help='Backtest end date (YYYY-MM-DD, default: today)'
        )
        parser.add_argument(
            '--no-csv',
            action='store_true',
            help='Disable CSV export'
        )
