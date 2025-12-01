#!/usr/bin/env python3
"""
Collect Training Data with Minimal Filters (For ML Training)

This script collects training data using ONLY essential filters:
- RSI10 < 30
- Price > EMA200
- Minimal chart quality (movement only - flat charts won't bounce)

SKIPS:
- Trade agent validation
- Volume filters
- Fundamental filters
- Verdict filters
- Gap analysis
- Extreme candle analysis

Purpose:
- Collect unbiased training data for ML model
- Let ML learn which dips bounce to EMA9 regardless of gaps/volatility
- As ML improves, gradually remove filters

Usage:
    python scripts/collect_training_data_unfiltered.py --stocks-file data/all_nse_stocks.txt --output data/ml_training_data_unfiltered.csv --years-back 10
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import argparse
from typing import List, Dict, Optional
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger
from services.data_service import DataService
from services.indicator_service import IndicatorService
from services.chart_quality_service import ChartQualityService
from services.backtest_service import BacktestService
from core.feature_engineering import calculate_all_dip_features
from scripts.get_all_nse_stocks import get_all_nse_stocks, get_nse_stocks_from_file
from config.settings import MAX_CONCURRENT_ANALYSES
from config.strategy_config import StrategyConfig

# Import market regime service for features
try:
    from services.market_regime_service import MarketRegimeService

    MARKET_REGIME_AVAILABLE = True
except ImportError:
    MARKET_REGIME_AVAILABLE = False
    logger.warning("MarketRegimeService not available, skipping market regime features")


def check_minimal_entry_conditions(
    ticker: str,
    data_service: DataService,
    indicator_service: IndicatorService,
    chart_quality_service: ChartQualityService,
    date: str,
    config: StrategyConfig,
) -> Optional[Dict]:
    """
    Check if stock meets minimal entry conditions:
    - RSI10 < 30
    - Price > EMA200
    - Minimal chart quality (movement only)

    Returns dict with entry info if conditions met, None otherwise
    """
    try:
        # Fetch data up to date (fetches enough for EMA200 by default)
        df = data_service.fetch_single_timeframe(
            ticker=ticker, end_date=date, add_current_day=False
        )

        if df is None or df.empty:
            return None

        # Check minimal chart quality (movement only)
        chart_quality = chart_quality_service.assess_chart_quality(df)
        if not chart_quality.get("passed", True):
            return None

        # Calculate indicators (using RSI10 as per strategy)
        rsi_period = config.rsi_period  # Default: 10 (RSI10)
        df["RSI10"] = indicator_service.calculate_rsi(df["close"], period=rsi_period)
        df["EMA200"] = indicator_service.calculate_ema(df["close"], period=200)

        # Get latest values
        latest = df.iloc[-1]
        rsi = latest["RSI10"]
        price = latest["close"]
        ema200 = latest["EMA200"]

        # Check conditions
        if pd.isna(rsi) or pd.isna(ema200):
            return None

        if rsi < 30 and price > ema200:
            return {
                "ticker": ticker,
                "date": date,
                "rsi": rsi,
                "price": price,
                "ema200": ema200,
                "chart_quality_passed": True,
            }

        return None

    except Exception as e:
        logger.debug(f"{ticker}: Error checking entry conditions: {e}")
        return None


def extract_features_at_date(
    ticker: str,
    entry_date: str,
    data_service: DataService,
    indicator_service: IndicatorService,
    config: StrategyConfig,
    signal_service=None,
    verdict_service=None,
) -> Optional[Dict]:
    """
    Extract features at signal date (entry_date - 1 trading day)

    LOOK-AHEAD BIAS FIX: Uses signal date, not entry date
    """
    try:
        # LOOK-AHEAD BIAS FIX: Calculate signal date (day before entry)
        entry_datetime = datetime.strptime(entry_date, "%Y-%m-%d")
        signal_date = entry_datetime - timedelta(days=1)

        # Skip weekends
        while signal_date.weekday() >= 5:
            signal_date -= timedelta(days=1)

        signal_date_str = signal_date.strftime("%Y-%m-%d")

        # Fetch data up to SIGNAL date (not entry date!) to avoid look-ahead bias
        # IMPORTANT: Fetch enough data for accurate EMA200 calculation
        # EMA200 needs ~300 trading days (200 + 100 warmup) = ~420 calendar days
        from core.data_fetcher import fetch_ohlcv_yf

        df = fetch_ohlcv_yf(
            ticker=ticker,
            days=420 + 100,  # EMA200 buffer + extra safety margin
            interval="1d",
            end_date=signal_date_str,
            add_current_day=False,
        )

        if df is None or df.empty:
            return None

        # Calculate indicators (using RSI10 as per strategy)
        df = indicator_service.compute_indicators(df)
        if df is None or df.empty:
            return None

        latest = df.iloc[-1]

        # Extract dip features
        dip_features = calculate_all_dip_features(df)

        # Base features
        features = {
            "ticker": ticker,
            "entry_date": entry_date,
            "signal_date": signal_date_str,
            "rsi_10": latest["rsi10"],  # Note: lowercase from compute_indicators()
            "price": latest["close"],
            "ema200": latest["ema200"],  # Note: lowercase from compute_indicators()
            "volume": latest["volume"],
            "volume_ratio": (
                latest["volume"] / df["volume"].rolling(20).mean().iloc[-1]
                if len(df) >= 20
                else 1.0
            ),
        }

        # Add dip features
        features.update(dip_features)

        # Re-entry context (default for initial entry)
        features["is_reentry"] = 0.0
        features["fill_number"] = 1.0
        features["total_fills_in_position"] = 1.0
        features["fill_price_vs_initial_pct"] = 0.0

        # Market regime features
        if MARKET_REGIME_AVAILABLE:
            try:
                market_regime_service = MarketRegimeService()
                market_features = market_regime_service.get_market_regime(signal_date_str)
                features.update(market_features)
            except Exception as e:
                logger.debug(f"{ticker}: Market regime failed: {e}")
                features["nifty_trend"] = 0.0
                features["nifty_vs_sma20_pct"] = 0.0
                features["nifty_vs_sma50_pct"] = 0.0
                features["india_vix"] = 20.0
                features["sector_strength"] = 0.0

        # Time-based features
        try:
            signal_datetime = datetime.strptime(signal_date_str, "%Y-%m-%d")
            features["day_of_week"] = signal_datetime.weekday()
            features["is_monday"] = 1.0 if signal_datetime.weekday() == 0 else 0.0
            features["is_friday"] = 1.0 if signal_datetime.weekday() == 4 else 0.0
            features["month"] = signal_datetime.month
            features["quarter"] = (signal_datetime.month - 1) // 3 + 1
            features["is_q4"] = 1.0 if signal_datetime.month >= 10 else 0.0
            features["is_month_end"] = 1.0 if signal_datetime.day >= 25 else 0.0
            features["is_quarter_end"] = (
                1.0
                if (signal_datetime.month in [3, 6, 9, 12] and signal_datetime.day >= 25)
                else 0.0
            )
        except Exception as e:
            logger.debug(f"{ticker}: Time features failed: {e}")
            features["day_of_week"] = 0
            features["is_monday"] = 0.0
            features["is_friday"] = 0.0
            features["month"] = 1
            features["quarter"] = 1
            features["is_q4"] = 0.0
            features["is_month_end"] = 0.0
            features["is_quarter_end"] = 0.0

        # Feature interactions
        try:
            features["rsi_volume_interaction"] = features.get("rsi_10", 50.0) * features.get(
                "volume_ratio", 1.0
            )
            features["dip_support_interaction"] = features.get(
                "dip_depth_from_20d_high_pct", 0.0
            ) * features.get("support_distance_pct", 0.0)
            features["extreme_dip_high_volume"] = (
                1.0
                if (
                    features.get("dip_depth_from_20d_high_pct", 0.0) > 10.0
                    and features.get("volume_ratio", 1.0) > 1.5
                )
                else 0.0
            )
            features["bearish_deep_dip"] = (
                1.0 if features.get("nifty_trend", 0.0) == -1.0 else 0.0
            ) * features.get("dip_depth_from_20d_high_pct", 0.0)
        except Exception as e:
            logger.debug(f"{ticker}: Feature interactions failed: {e}")
            features["rsi_volume_interaction"] = 0.0
            features["dip_support_interaction"] = 0.0
            features["extreme_dip_high_volume"] = 0.0
            features["bearish_deep_dip"] = 0.0

        return features

    except Exception as e:
        logger.debug(f"{ticker}: Feature extraction failed: {e}")
        return None


def process_stock_for_training(
    ticker: str,
    years_back: int,
    data_service: DataService,
    indicator_service: IndicatorService,
    chart_quality_service: ChartQualityService,
    backtest_service: BacktestService,
    config: StrategyConfig,
    index: int,
    total: int,
) -> Dict:
    """
    Process a single stock: run backtest with minimal filters, return backtest result
    """
    try:
        logger.info(f"[{index}/{total}] Processing {ticker}...")

        # Check minimal chart quality first (fetches enough data by default)
        df = data_service.fetch_single_timeframe(
            ticker=ticker, end_date=datetime.now().strftime("%Y-%m-%d"), add_current_day=False
        )

        if df is None or df.empty:
            logger.warning(f"  {ticker}: No data available")
            return None

        # Check minimal chart quality (movement only)
        chart_quality = chart_quality_service.assess_chart_quality(df)
        if not chart_quality.get("passed", True):
            logger.debug(f"  {ticker}: Chart quality failed (movement check)")
            return None

        # Run backtest with minimal filters (skip trade agent validation)
        # Note: We'll need to modify integrated_backtest to support this
        # For now, use the backtest service with chart quality disabled
        # and manually skip trade agent validation

        # Use integrated backtest directly with skip_trade_agent_validation
        from integrated_backtest import run_integrated_backtest

        end_date = datetime.now()
        start_date = end_date - timedelta(days=years_back * 365)
        date_range = (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

        # Use capital from config (same as actual trading)
        capital_per_position = config.user_capital  # Default: 200000 (2L)

        backtest_result = run_integrated_backtest(
            stock_name=ticker,
            date_range=date_range,
            capital_per_position=capital_per_position,
            skip_trade_agent_validation=True,  # Skip trade agent for training data
        )

        if backtest_result and backtest_result.get("positions"):
            # Format for create_labels_from_backtest_results_with_reentry
            # It expects 'full_results' to contain the positions and other data
            return {
                "ticker": ticker,
                "backtest_score": backtest_result.get("backtest_score", 0),
                "total_return_pct": backtest_result.get("total_return_pct", 0),
                "win_rate": backtest_result.get("win_rate", 0),
                "total_trades": backtest_result.get("executed_trades", 0),
                "full_results": {
                    "positions": backtest_result.get("positions", []),
                    "total_return_pct": backtest_result.get("total_return_pct", 0),
                    "win_rate": backtest_result.get("win_rate", 0),
                    "executed_trades": backtest_result.get("executed_trades", 0),
                },
            }
        else:
            logger.debug(f"  {ticker}: No positions found")
            return None

    except Exception as e:
        logger.error(f"  {ticker}: Error processing: {e}")
        import traceback

        logger.debug(traceback.format_exc())
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Collect ML training data with minimal filters (RSI<30, price>EMA200, movement only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--stocks-file",
        "-f",
        default="data/all_nse_stocks.txt",
        help="File with list of NSE stocks (one per line)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output CSV file (default: data/ml_training_data_unfiltered_YYYYMMDD_HHMMSS.csv)",
    )
    parser.add_argument(
        "--years-back", "-y", type=int, default=10, help="Years of historical data (default: 10)"
    )
    parser.add_argument(
        "--max-stocks",
        "-m",
        type=int,
        default=None,
        help="Maximum number of stocks to process (for testing)",
    )
    parser.add_argument(
        "--max-workers",
        "-w",
        type=int,
        default=None,
        help=f"Maximum concurrent workers (default: {MAX_CONCURRENT_ANALYSES})",
    )

    args = parser.parse_args()

    # Setup output file
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"data/ml_training_data_unfiltered_{timestamp}.csv"

    logger.info("=" * 80)
    logger.info("COLLECTING ML TRAINING DATA (MINIMAL FILTERS)")
    logger.info("=" * 80)
    logger.info(f"Filters: RSI<30, Price>EMA200, Movement only (minimal chart quality)")
    logger.info(f"Skips: Trade agent, Volume, Fundamentals, Verdict, Gaps, Extreme candles")
    logger.info(f"Output: {args.output}")
    logger.info(f"Years back: {args.years_back}")
    logger.info("=" * 80)
    logger.info("")

    # Get stocks
    if not Path(args.stocks_file).exists():
        logger.info(f"Stocks file not found, fetching all NSE stocks...")
        stocks = get_all_nse_stocks(args.stocks_file)
    else:
        logger.info(f"Loading stocks from {args.stocks_file}...")
        stocks = get_nse_stocks_from_file(args.stocks_file)

    if not stocks:
        logger.error("No stocks found!")
        return 1

    if args.max_stocks:
        stocks = stocks[: args.max_stocks]
        logger.info(f"Limited to first {args.max_stocks} stocks")

    logger.info(f"Processing {len(stocks)} stocks...")
    logger.info("")

    # Initialize services
    config = StrategyConfig.default()
    data_service = DataService()
    indicator_service = IndicatorService(config=config)
    chart_quality_service = ChartQualityService(config=config, minimal_mode=True)  # Minimal mode!
    backtest_service = BacktestService(default_years_back=args.years_back, dip_mode=True)

    # Step 1: Run backtests with minimal filters
    logger.info("Step 1: Running backtests with minimal filters...")
    logger.info(f"Capital per position: Rs {config.user_capital:,.0f} (from config)")
    logger.info("")

    max_workers = args.max_workers or MAX_CONCURRENT_ANALYSES
    backtest_results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                process_stock_for_training,
                ticker,
                args.years_back,
                data_service,
                indicator_service,
                chart_quality_service,
                backtest_service,
                config,  # Pass config for capital_per_position
                i + 1,
                len(stocks),
            ): ticker
            for i, ticker in enumerate(stocks)
        }

        for future in as_completed(futures):
            ticker = futures[future]
            try:
                result = future.result()
                if result:
                    backtest_results.append(result)
            except Exception as e:
                logger.error(f"{ticker}: Failed: {e}")

    if not backtest_results:
        logger.warning("No backtest results collected!")
        return 1

    # Save intermediate backtest results
    intermediate_file = args.output.replace(".csv", "_backtest_results.csv")
    backtest_df = pd.DataFrame(backtest_results)
    backtest_df.to_csv(intermediate_file, index=False)
    logger.info(f"Saved {len(backtest_results)} backtest results to {intermediate_file}")
    logger.info("")

    # Step 2: Extract features and labels from backtest results
    logger.info("Step 2: Extracting features and labels from backtest results...")
    logger.info("")

    # CRITICAL FIX: Reset circuit breaker before feature extraction
    # Feature extraction makes many API calls and circuit breaker can block all calls
    from core.data_fetcher import yfinance_circuit_breaker

    yfinance_circuit_breaker.reset()
    logger.info("? Circuit breaker reset for feature extraction phase")
    logger.info("")

    # Import the existing function from collect_training_data.py
    from scripts.collect_training_data import (
        extract_features_at_date,
        create_labels_from_backtest_results_with_reentry,
    )
    from services.signal_service import SignalService
    from services.verdict_service import VerdictService

    signal_service = SignalService()
    verdict_service = VerdictService()

    all_training_data = []
    processed_count = 0

    for backtest_result in backtest_results:
        try:
            # Reset circuit breaker every 50 stocks to prevent blocking
            if processed_count > 0 and processed_count % 50 == 0:
                yfinance_circuit_breaker.reset()
                logger.info(f"? Circuit breaker reset after {processed_count} stocks")

            labeled_examples = create_labels_from_backtest_results_with_reentry(backtest_result)
            all_training_data.extend(labeled_examples)
            processed_count += 1
        except Exception as e:
            logger.error(f"{backtest_result.get('ticker')}: Failed to extract features: {e}")

    # Save final training data
    if all_training_data:
        df = pd.DataFrame(all_training_data)
        df.to_csv(args.output, index=False)
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"? Training data collected: {len(all_training_data)} examples")
        logger.info(f"Saved to: {args.output}")
        logger.info("")
        logger.info("Label distribution:")
        logger.info(df["label"].value_counts().to_string())
        logger.info("=" * 80)
    else:
        logger.warning("No training data extracted!")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
