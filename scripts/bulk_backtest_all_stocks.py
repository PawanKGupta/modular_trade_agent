#!/usr/bin/env python3
"""
Bulk Backtest All NSE Stocks

Runs backtest on all NSE stocks to generate large training dataset for ML models.
This script:
1. Gets all NSE stocks
2. Runs backtest on each stock
3. Collects backtest results with actual outcomes
4. Saves results for ML training

Usage:
    python scripts/bulk_backtest_all_stocks.py --stocks-file data/all_nse_stocks.txt --output data/backtest_training_data.csv
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import argparse
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger
from services.backtest_service import BacktestService
from scripts.get_all_nse_stocks import get_all_nse_stocks, get_nse_stocks_from_file
from config.settings import MAX_CONCURRENT_ANALYSES


def _process_single_stock(
    ticker: str,
    years_back: int,
    dip_mode: bool,
    disable_chart_quality: bool,
    skip_trade_agent_validation: bool,
    config,
    backtest_service: BacktestService,
    index: int,
    total: int,
) -> Dict:
    """
    Process a single stock backtest (used for parallel processing)

    Args:
        ticker: Stock symbol
        years_back: Years of historical data
        dip_mode: Enable dip-buying mode
        disable_chart_quality: Whether to disable chart quality
        skip_trade_agent_validation: Whether to skip trade agent validation (for training data)
        config: StrategyConfig instance
        backtest_service: BacktestService instance
        index: Current index (for logging)
        total: Total number of stocks (for logging)

    Returns:
        Dict with backtest results
    """
    try:
        logger.info(f"[{index}/{total}] Backtesting {ticker}...")

        # Run backtest directly with config (bypasses BacktestService to pass config)
        if disable_chart_quality:
            # Use core function directly with custom config
            from core.backtest_scoring import run_stock_backtest as core_run_stock_backtest

            backtest_result = core_run_stock_backtest(
                stock_symbol=ticker, years_back=years_back, dip_mode=dip_mode, config=config
            )
        else:
            # Use service (normal path)
            backtest_result = backtest_service.run_stock_backtest(
                stock_symbol=ticker, years_back=years_back, dip_mode=dip_mode
            )

        # Always save result, even if 0 trades (for analysis)
        if backtest_result:
            # Extract useful data for training
            result = {
                "ticker": ticker,
                "backtest_score": backtest_result.get("backtest_score", 0),
                "total_return_pct": backtest_result.get("total_return_pct", 0),
                "win_rate": backtest_result.get("win_rate", 0),
                "total_trades": backtest_result.get("total_trades", 0),
                "total_positions": backtest_result.get("total_positions", 0),
                "strategy_vs_buy_hold": backtest_result.get("strategy_vs_buy_hold", 0),
                "execution_rate": backtest_result.get("execution_rate", 0),
                "years_back": years_back,
                "dip_mode": dip_mode,
                "backtest_date": datetime.now().strftime("%Y-%m-%d"),
            }

            # Add chart quality info if available
            if "chart_quality" in backtest_result:
                chart_quality = backtest_result["chart_quality"]
                result["chart_quality_passed"] = chart_quality.get("passed", True)
                result["chart_quality_score"] = chart_quality.get("score", 0)
                result["chart_quality_reason"] = chart_quality.get("reason", "")

            # Add full results for detailed analysis
            if "full_results" in backtest_result:
                full_results = backtest_result["full_results"]
                result["full_results"] = full_results

            if result["total_trades"] > 0:
                logger.info(
                    f"  ? {ticker}: {result['total_trades']} trades, {result['total_return_pct']:.1f}% return, {result['win_rate']:.1f}% win rate"
                )
            else:
                # Log why no trades
                reason = result.get("chart_quality_reason", "No signals found")
                logger.warning(f"  [WARN]? {ticker}: 0 trades - {reason}")

            return result
        else:
            # Backtest failed completely
            result = {
                "ticker": ticker,
                "backtest_score": 0,
                "total_return_pct": 0,
                "win_rate": 0,
                "total_trades": 0,
                "total_positions": 0,
                "strategy_vs_buy_hold": 0,
                "execution_rate": 0,
                "years_back": years_back,
                "dip_mode": dip_mode,
                "backtest_date": datetime.now().strftime("%Y-%m-%d"),
                "error": "Backtest failed",
            }
            logger.error(f"  ? {ticker}: Backtest failed completely")
            return result

    except Exception as e:
        logger.error(f"  ? {ticker}: Backtest failed - {e}")
        return {
            "ticker": ticker,
            "backtest_score": 0,
            "total_return_pct": 0,
            "win_rate": 0,
            "total_trades": 0,
            "total_positions": 0,
            "strategy_vs_buy_hold": 0,
            "execution_rate": 0,
            "years_back": years_back,
            "dip_mode": dip_mode,
            "backtest_date": datetime.now().strftime("%Y-%m-%d"),
            "error": str(e),
        }


def run_bulk_backtest(
    stocks: List[str],
    years_back: int = 2,
    dip_mode: bool = False,
    max_stocks: int = None,
    output_file: str = "data/backtest_training_data.csv",
    disable_chart_quality: bool = False,
    skip_trade_agent_validation: bool = False,
    max_workers: int = None,
) -> pd.DataFrame:
    """
    Run backtest on multiple stocks and collect results (parallel processing)

    Args:
        stocks: List of stock symbols with .NS suffix
        years_back: Years of historical data for backtesting
        dip_mode: Enable dip-buying mode
        max_stocks: Maximum number of stocks to process (None = all)
        output_file: Path to save results
        disable_chart_quality: Whether to disable chart quality (FOR TESTING ONLY)
        skip_trade_agent_validation: Whether to skip trade agent validation (for training data)
        max_workers: Maximum number of concurrent workers (uses MAX_CONCURRENT_ANALYSES if None)

    Returns:
        DataFrame with backtest results
    """
    logger.info(f"Starting bulk backtest for {len(stocks)} stocks...")

    if max_stocks:
        stocks = stocks[:max_stocks]
        logger.info(f"Limited to first {max_stocks} stocks")

    # Use configurable concurrency (default: MAX_CONCURRENT_ANALYSES from settings)
    if max_workers is None:
        max_workers = MAX_CONCURRENT_ANALYSES
    logger.info(f"Using {max_workers} concurrent workers for parallel processing")

    # Create config with chart quality disabled if requested (FOR TESTING/DATA COLLECTION ONLY)
    from config.strategy_config import StrategyConfig

    config = StrategyConfig.default()
    if disable_chart_quality:
        config.chart_quality_enabled_in_backtest = False
        logger.warning("=" * 70)
        logger.warning("[WARN]?  WARNING: Chart quality filtering DISABLED")
        logger.warning("[WARN]?  This is ONLY for testing/data collection purposes")
        logger.warning("[WARN]?  Chart quality filtering is REQUIRED in live system")
        logger.warning("[WARN]?  DO NOT disable chart quality in production!")
        logger.warning("=" * 70)

    # Create backtest service (shared across workers)
    backtest_service = BacktestService(default_years_back=years_back, dip_mode=dip_mode)

    results = []
    total = len(stocks)

    # Process stocks in parallel using ThreadPoolExecutor
    # Rate limiting is handled automatically by the shared rate limiter in data_fetcher.py
    # Each thread will automatically wait between API calls to prevent rate limiting
    logger.info(f"Processing {total} stocks with {max_workers} concurrent workers...")
    logger.info(f"Rate limiting: Automatic (1.0s delay between API calls via shared rate limiter)")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(
                _process_single_stock,
                ticker,
                years_back,
                dip_mode,
                disable_chart_quality,
                skip_trade_agent_validation,
                config,
                backtest_service,
                i + 1,
                total,
            ): ticker
            for i, ticker in enumerate(stocks)
        }

        # Process completed tasks as they finish
        completed = 0
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
                completed += 1
                if completed % 10 == 0:
                    logger.info(
                        f"Progress: {completed}/{total} stocks processed ({completed*100//total}%)"
                    )
            except Exception as e:
                logger.error(f"  ? {ticker}: Unexpected error - {e}")
                completed += 1

    # Create DataFrame
    if results:
        df = pd.DataFrame(results)

        # Save to CSV
        os.makedirs(Path(output_file).parent, exist_ok=True)
        df.to_csv(output_file, index=False)
        logger.info(f"\n? Bulk backtest complete!")
        logger.info(f"   Processed: {len(results)}/{total} stocks")
        logger.info(f"   Stocks with trades > 0: {len(df[df['total_trades'] > 0])}")
        logger.info(f"   Stocks with 0 trades: {len(df[df['total_trades'] == 0])}")
        logger.info(f"   Results saved to: {output_file}")

        # Print summary
        if len(results) > 0:
            avg_return = df["total_return_pct"].mean()
            avg_win_rate = df["win_rate"].mean()
            avg_trades = df["total_trades"].mean()

            logger.info(f"\n? Summary Statistics:")
            logger.info(f"   Average Return: {avg_return:.2f}%")
            logger.info(f"   Average Win Rate: {avg_win_rate:.2f}%")
            logger.info(f"   Average Trades: {avg_trades:.1f}")
            logger.info(f"   Stocks with >5 trades: {len(df[df['total_trades'] >= 5])}")
            logger.info(f"   Stocks with >10% return: {len(df[df['total_return_pct'] >= 10])}")
    else:
        logger.warning("No valid backtest results collected")
        df = pd.DataFrame()

    return df


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Bulk backtest all NSE stocks for ML training")
    parser.add_argument(
        "--stocks-file",
        "-f",
        default="data/all_nse_stocks.txt",
        help="File with list of NSE stocks (one per line)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="data/backtest_training_data.csv",
        help="Output CSV file for training data",
    )
    parser.add_argument(
        "--years-back", "-y", type=int, default=2, help="Years of historical data (default: 2)"
    )
    parser.add_argument("--dip-mode", action="store_true", help="Enable dip-buying mode")
    parser.add_argument(
        "--max-stocks",
        "-m",
        type=int,
        default=None,
        help="Maximum number of stocks to process (for testing)",
    )
    parser.add_argument(
        "--fetch-stocks",
        action="store_true",
        help="Fetch all NSE stocks first (if file doesn't exist)",
    )
    parser.add_argument(
        "--disable-chart-quality",
        action="store_true",
        help="[WARN]? FOR TESTING ONLY: Disable chart quality filtering for data collection. "
        "Chart quality is REQUIRED in live system - DO NOT use in production!",
    )
    parser.add_argument(
        "--max-workers",
        "-w",
        type=int,
        default=None,
        help=f"Maximum number of concurrent workers (default: {MAX_CONCURRENT_ANALYSES} from settings)",
    )

    args = parser.parse_args()

    # Get stocks
    stocks = []
    if args.fetch_stocks or not Path(args.stocks_file).exists():
        logger.info("Fetching all NSE stocks...")
        stocks = get_all_nse_stocks(args.stocks_file)
    else:
        logger.info(f"Loading stocks from {args.stocks_file}...")
        stocks = get_nse_stocks_from_file(args.stocks_file)

    if not stocks:
        logger.error("No stocks found! Use --fetch-stocks to fetch stocks first.")
        return 1

    logger.info(f"Found {len(stocks)} stocks to backtest")

    # Run bulk backtest
    df = run_bulk_backtest(
        stocks=stocks,
        years_back=args.years_back,
        dip_mode=args.dip_mode,
        max_stocks=args.max_stocks,
        output_file=args.output,
        disable_chart_quality=args.disable_chart_quality,
        max_workers=args.max_workers,
    )

    return 0 if len(df) > 0 else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
