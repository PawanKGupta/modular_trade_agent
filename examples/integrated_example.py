#!/usr/bin/env python3
"""
Integrated Backtest-Trade Agent Example

This script demonstrates how to use the integrated backtest-trade agent workflow
to test the combination of backtesting strategy signals with live trade agent validation.
"""

import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from integrated_backtest import run_integrated_backtest, print_integrated_results


def example_single_stock():
    """Example 1: Single stock integrated backtest"""
    print("=" * 80)
    print("EXAMPLE 1: Single Stock Integrated Backtest")
    print("=" * 80)

    # Test with RELIANCE.NS over a 2-year period
    stock = "RELIANCE.NS"
    date_range = ("2022-01-01", "2023-12-31")
    capital_per_position = 100000

    print(f"Testing integrated workflow on {stock}")
    print(f"This will:")
    print(f"  1. Run backtest to identify potential buy signals")
    print(f"  2. Validate each signal through trade agent analysis")
    print(f"  3. Execute trades only on confirmed BUY signals")
    print(f"  4. Track positions until target/stop is reached")
    print()

    # Run the integrated backtest
    results = run_integrated_backtest(stock, date_range, capital_per_position)

    # Print detailed results
    print_integrated_results(results)

    return results


def example_multiple_stocks():
    """Example 2: Compare multiple stocks using integrated approach"""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Multiple Stock Comparison")
    print("=" * 80)

    stocks = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
    date_range = ("2023-01-01", "2023-12-31")
    capital_per_position = 100000

    comparison_results = {}

    for stock in stocks:
        print(f"\n? Running integrated backtest for {stock}...")

        try:
            results = run_integrated_backtest(stock, date_range, capital_per_position)
            comparison_results[stock] = results

        except Exception as e:
            print(f"? Error analyzing {stock}: {e}")
            comparison_results[stock] = None

    # Print comparison summary
    print_comparison_summary(comparison_results)

    return comparison_results


def example_different_time_periods():
    """Example 3: Test same stock across different time periods"""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Different Time Periods Analysis")
    print("=" * 80)

    stock = "RELIANCE.NS"
    periods = [
        ("2020-01-01", "2020-12-31", "2020 (COVID Year)"),
        ("2021-01-01", "2021-12-31", "2021 (Recovery Year)"),
        ("2022-01-01", "2022-12-31", "2022 (Volatile Year)"),
        ("2023-01-01", "2023-12-31", "2023 (Recent Year)"),
    ]

    period_results = {}

    print(f"Testing {stock} across different market conditions:")

    for start_date, end_date, description in periods:
        print(f"\n? Testing period: {description}")

        try:
            results = run_integrated_backtest(
                stock, (start_date, end_date), capital_per_position=100000
            )
            period_results[description] = results

        except Exception as e:
            print(f"? Error analyzing {description}: {e}")
            period_results[description] = None

    # Print period comparison
    print_period_comparison(period_results)

    return period_results


def example_strategy_validation():
    """Example 4: Validate strategy effectiveness"""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Strategy Validation Analysis")
    print("=" * 80)

    # Compare integrated approach vs pure backtest approach
    stock = "RELIANCE.NS"
    date_range = ("2022-01-01", "2023-12-31")

    print(f"Comparing integrated approach (backtest + trade agent) vs pure signals")
    print(f"This shows how trade agent filtering affects performance:")
    print()

    # Run integrated backtest
    integrated_results = run_integrated_backtest(stock, date_range)

    # Show effectiveness metrics
    if integrated_results.get("total_signals", 0) > 0:
        approval_rate = integrated_results["trade_agent_accuracy"]
        total_signals = integrated_results["total_signals"]
        executed_trades = integrated_results["executed_trades"]

        print(f"? STRATEGY VALIDATION RESULTS:")
        print(f"  Total Backtest Signals: {total_signals}")
        print(f"  Trade Agent Approved: {executed_trades}")
        print(f"  Approval Rate: {approval_rate:.1f}%")
        print(f"  Filter Effectiveness: {100 - approval_rate:.1f}% of signals filtered out")

        if integrated_results.get("total_return_pct"):
            print(f"  Strategy Return: {integrated_results['total_return_pct']:+.2f}%")
            if integrated_results.get("buy_hold_return"):
                print(f"  Buy & Hold Return: {integrated_results['buy_hold_return']:+.2f}%")
                print(f"  Alpha Generated: {integrated_results['strategy_vs_buy_hold']:+.2f}%")

    return integrated_results


def print_comparison_summary(comparison_results):
    """Print formatted comparison of multiple stocks"""
    print(f"\n? MULTI-STOCK COMPARISON SUMMARY")
    print(f"{'Stock':<15} {'Signals':<8} {'Trades':<8} {'Return%':<10} {'vs B&H%':<10} {'Win%':<8}")
    print("-" * 70)

    for stock, results in comparison_results.items():
        if results and results.get("total_signals", 0) > 0:
            signals = results["total_signals"]
            trades = results["executed_trades"]
            return_pct = results.get("total_return_pct", 0)
            vs_bh = results.get("strategy_vs_buy_hold", 0)
            win_rate = results.get("win_rate", 0)

            print(
                f"{stock:<15} {signals:<8} {trades:<8} {return_pct:>7.1f}%   {vs_bh:>8.1f}%   {win_rate:>6.1f}%"
            )
        else:
            print(f"{stock:<15} No data available")


def print_period_comparison(period_results):
    """Print formatted comparison across time periods"""
    print(f"\n? TIME PERIOD COMPARISON")
    print(
        f"{'Period':<20} {'Signals':<8} {'Trades':<8} {'Return%':<10} {'Win%':<8} {'vs B&H%':<10}"
    )
    print("-" * 75)

    for period, results in period_results.items():
        if results and results.get("total_signals", 0) > 0:
            signals = results["total_signals"]
            trades = results["executed_trades"]
            return_pct = results.get("total_return_pct", 0)
            win_rate = results.get("win_rate", 0)
            vs_bh = results.get("strategy_vs_buy_hold", 0)

            print(
                f"{period:<20} {signals:<8} {trades:<8} {return_pct:>7.1f}%   {win_rate:>6.1f}%   {vs_bh:>8.1f}%"
            )
        else:
            print(f"{period:<20} No data available")


def main():
    """Run all integrated backtest examples"""
    print("? INTEGRATED BACKTEST-TRADE AGENT EXAMPLES")
    print(
        "This demonstrates the coordinated workflow between backtesting and trade agent analysis."
    )
    print("=" * 80)

    try:
        # Run examples
        print("\n? Starting Example 1: Single Stock Analysis...")
        example_single_stock()

        print("\n? Starting Example 2: Multiple Stock Comparison...")
        example_multiple_stocks()

        print("\n? Starting Example 3: Different Time Periods...")
        example_different_time_periods()

        print("\n? Starting Example 4: Strategy Validation...")
        example_strategy_validation()

        print(f"\n? All examples completed successfully!")
        print(f"\n? Key Insights from Integrated Approach:")
        print(f"  - Backtest identifies potential entry points based on technical strategy")
        print(f"  - Trade agent validates each signal with advanced multi-timeframe analysis")
        print(f"  - Only high-confidence signals result in actual trades")
        print(f"  - Positions are tracked until target/stop conditions are met")
        print(f"  - This reduces false signals and improves risk-adjusted returns")

    except KeyboardInterrupt:
        print(f"\n? Examples interrupted by user")

    except Exception as e:
        print(f"\n? Error running examples: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
