"""
Backtest Module Example

This script demonstrates how to use the backtesting module for evaluating
the EMA200 + RSI10 pyramiding strategy on different stocks and time periods.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest import BacktestEngine, PerformanceAnalyzer, BacktestConfig
from datetime import datetime, timedelta


def example_single_backtest():
    """
    Example 1: Simple single stock backtest
    """
    print("=" * 80)
    print("EXAMPLE 1: Single Stock Backtest")
    print("=" * 80)

    # Create backtest engine for RELIANCE.NS
    engine = BacktestEngine(symbol="RELIANCE.NS", start_date="2022-01-01", end_date="2023-12-31")

    # Run the backtest
    results = engine.run_backtest()

    # Print summary
    engine.print_summary()

    # Get trades dataframe
    trades_df = engine.get_trades_dataframe()
    if not trades_df.empty:
        print(f"\nFirst 5 trades:")
        print(trades_df.head())


def example_custom_config():
    """
    Example 2: Backtest with custom configuration
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Custom Configuration Backtest")
    print("=" * 80)

    # Create custom configuration
    config = BacktestConfig()
    config.POSITION_SIZE = 200000  # Larger position size
    config.RSI_PERIOD = 14  # Different RSI period
    config.EMA_PERIOD = 100  # Different EMA period
    config.MAX_POSITIONS = 5  # Less pyramiding
    config.DETAILED_LOGGING = True  # Enable detailed logs

    # Create backtest engine with custom config
    engine = BacktestEngine(
        symbol="TCS.NS", start_date="2021-01-01", end_date="2023-06-30", config=config
    )

    # Run backtest
    results = engine.run_backtest()
    engine.print_summary()


def example_performance_analysis():
    """
    Example 3: Detailed performance analysis and reporting
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Performance Analysis & Reporting")
    print("=" * 80)

    # Run backtest
    engine = BacktestEngine(symbol="INFY.NS", start_date="2020-01-01", end_date="2023-12-31")

    results = engine.run_backtest()

    # Create performance analyzer
    analyzer = PerformanceAnalyzer(engine)

    # Analyze performance
    detailed_metrics = analyzer.analyze_performance()

    # Generate and display report
    report = analyzer.generate_report(save_to_file=True)
    print("Report preview:")
    print(report[:1000] + "..." if len(report) > 1000 else report)

    # Export trades
    if not engine.get_trades_dataframe().empty:
        analyzer.export_trades_to_csv()

    # Show monthly performance if available
    monthly_perf = analyzer.get_monthly_performance()
    if not monthly_perf.empty:
        print(f"\nMonthly Performance:")
        print(monthly_perf)


def example_multiple_stocks():
    """
    Example 4: Compare multiple stocks
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Multiple Stock Comparison")
    print("=" * 80)

    stocks = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS"]
    results_comparison = {}

    for symbol in stocks:
        print(f"\n--- Analyzing {symbol} ---")

        try:
            # Run backtest for each stock
            engine = BacktestEngine(symbol=symbol, start_date="2022-01-01", end_date="2023-12-31")

            results = engine.run_backtest()
            results_comparison[symbol] = results

            # Quick summary
            if results.get("total_trades", 0) > 0:
                print(f"Total Return: {results['total_return_pct']:+.2f}%")
                print(f"Win Rate: {results['win_rate']:.1f}%")
                print(f"vs Buy & Hold: {results['strategy_vs_buy_hold']:+.2f}%")
            else:
                print("No trades executed")

        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")
            results_comparison[symbol] = None

    # Summary comparison
    print(f"\n? COMPARISON SUMMARY")
    print(f"{'Stock':<15} {'Return%':<10} {'Win%':<8} {'vs B&H%':<10} {'Trades':<8}")
    print("-" * 60)

    for symbol, result in results_comparison.items():
        if result and result.get("total_trades", 0) > 0:
            print(
                f"{symbol:<15} "
                f"{result['total_return_pct']:>7.1f}%   "
                f"{result['win_rate']:>6.1f}%  "
                f"{result['strategy_vs_buy_hold']:>8.1f}%  "
                f"{result['total_trades']:>6}"
            )
        else:
            print(f"{symbol:<15} {'No data'}")


def example_different_time_periods():
    """
    Example 5: Test same stock across different time periods
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Different Time Periods Analysis")
    print("=" * 80)

    symbol = "RELIANCE.NS"
    periods = [
        ("2020-01-01", "2020-12-31", "2020 (COVID Year)"),
        ("2021-01-01", "2021-12-31", "2021 (Recovery Year)"),
        ("2022-01-01", "2022-12-31", "2022 (Volatile Year)"),
        ("2023-01-01", "2023-12-31", "2023 (Recent Year)"),
    ]

    print(f"Testing {symbol} across different periods:")
    print(f"{'Period':<20} {'Return%':<10} {'Win%':<8} {'Trades':<8} {'vs B&H%':<10}")
    print("-" * 65)

    for start_date, end_date, description in periods:
        try:
            engine = BacktestEngine(symbol=symbol, start_date=start_date, end_date=end_date)

            results = engine.run_backtest()

            if results.get("total_trades", 0) > 0:
                print(
                    f"{description:<20} "
                    f"{results['total_return_pct']:>7.1f}%   "
                    f"{results['win_rate']:>6.1f}%  "
                    f"{results['total_trades']:>6}  "
                    f"{results['strategy_vs_buy_hold']:>8.1f}%"
                )
            else:
                print(f"{description:<20} No trades")

        except Exception as e:
            print(f"{description:<20} Error: {str(e)[:30]}...")


def main():
    """
    Run all examples
    """
    print("? BACKTESTING MODULE EXAMPLES")
    print("This script demonstrates various ways to use the backtesting module.")
    print("Note: All examples use real data from Yahoo Finance.")

    try:
        # Run examples
        example_single_backtest()
        example_custom_config()
        example_performance_analysis()
        example_multiple_stocks()
        example_different_time_periods()

        print(f"\n? All examples completed successfully!")
        print(f"\n? Check the following directories for outputs:")
        print(f"   - backtest_reports/ (for detailed reports)")
        print(f"   - backtest_exports/ (for CSV trade data)")

    except KeyboardInterrupt:
        print(f"\n? Examples interrupted by user")

    except Exception as e:
        print(f"\n? Error running examples: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
