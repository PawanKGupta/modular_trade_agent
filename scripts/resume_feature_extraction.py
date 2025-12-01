#!/usr/bin/env python3
"""
Resume Feature Extraction from Existing Backtest Results

Use this when backtest completed but feature extraction failed (e.g., circuit breaker).
"""

import sys
import pandas as pd
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger
from scripts.collect_training_data import create_labels_from_backtest_results_with_reentry
from core.data_fetcher import yfinance_circuit_breaker


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Resume feature extraction from backtest results")
    parser.add_argument("--backtest-file", required=True, help="Backtest results CSV file")
    parser.add_argument("--output", required=True, help="Output training data CSV file")

    args = parser.parse_args()

    # Load backtest results
    logger.info(f"Loading backtest results from {args.backtest_file}...")
    backtest_df = pd.read_csv(args.backtest_file)
    logger.info(f"Found {len(backtest_df)} backtest results")
    logger.info("")

    # Reset circuit breaker to start fresh
    yfinance_circuit_breaker.reset()
    logger.info("? Circuit breaker reset")
    logger.info("")

    all_training_data = []
    processed_count = 0
    failed_count = 0

    for idx, backtest_result in backtest_df.iterrows():
        ticker = backtest_result.get("ticker", "Unknown")

        try:
            # Reset circuit breaker every 25 stocks to prevent blocking
            if processed_count > 0 and processed_count % 25 == 0:
                yfinance_circuit_breaker.reset()
                logger.info(f"? Circuit breaker reset after {processed_count} stocks")
                logger.info(
                    f"Progress: {processed_count}/{len(backtest_df)} ({processed_count*100//len(backtest_df)}%)"
                )

            # Extract features and labels
            labeled_examples = create_labels_from_backtest_results_with_reentry(backtest_result)

            if labeled_examples:
                all_training_data.extend(labeled_examples)
                processed_count += 1
            else:
                logger.debug(f"{ticker}: No training examples extracted")
                failed_count += 1

        except Exception as e:
            logger.warning(f"{ticker}: Failed to extract features: {e}")
            failed_count += 1
            # Continue processing other stocks
            continue

    # Save final training data
    if all_training_data:
        df = pd.DataFrame(all_training_data)
        df.to_csv(args.output, index=False)

        logger.info("")
        logger.info("=" * 80)
        logger.info(f"? Training data collected: {len(all_training_data)} examples")
        logger.info(f"Saved to: {args.output}")
        logger.info("")
        logger.info(f"Successfully processed: {processed_count}/{len(backtest_df)} stocks")
        logger.info(f"Failed: {failed_count}/{len(backtest_df)} stocks")
        logger.info("")
        logger.info("Label distribution:")
        logger.info(df["label"].value_counts())
        logger.info("=" * 80)

        return 0
    else:
        logger.error("? No training data extracted!")
        logger.error(f"Processed: {processed_count}, Failed: {failed_count}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
