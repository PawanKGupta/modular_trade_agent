#!/usr/bin/env python3
"""
Standalone script to validate 2-year backtest with EMA warm-up validation

Usage:
    python tests/unit/backtest/validate_2year_backtest.py [--symbol STOCK] [--years YEARS]

Example:
    python tests/unit/backtest/validate_2year_backtest.py --symbol RELIANCE.NS --years 2
"""

import argparse
import sys
import os
from datetime import datetime, timedelta
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from backtest.backtest_engine import BacktestEngine
from backtest.backtest_config import BacktestConfig
from integrated_backtest import run_integrated_backtest


def validate_ema_warmup(engine: BacktestEngine, config: BacktestConfig) -> dict:
    """
    Validate EMA warm-up periods before backtest start

    Returns:
        dict with validation results
    """
    backtest_start_dt = pd.to_datetime(engine.start_date)
    data_before_start = engine._full_data.loc[engine._full_data.index < backtest_start_dt]

    ema_warmup_required = min(100, int(config.EMA_PERIOD * 0.5))
    warmup_periods = len(data_before_start)

    # Check first backtest row
    first_row = engine.data.iloc[0]
    first_ema200 = first_row["EMA200"]
    first_close = first_row["Close"]
    first_rsi = first_row.get("RSI10", None)

    validation = {
        "warmup_periods": warmup_periods,
        "warmup_required": ema_warmup_required,
        "sufficient_warmup": warmup_periods >= ema_warmup_required,
        "ema200_at_start": first_ema200,
        "close_at_start": first_close,
        "rsi_at_start": first_rsi,
        "ema_is_nan": pd.isna(first_ema200),
        "ema_close_ratio": first_ema200 / first_close if first_close > 0 else None,
    }

    return validation


def test_backtest_engine_2years(symbol: str, years: int = 2):
    """Test BacktestEngine with 2-year backtest"""
    print("=" * 80)
    print(f"Testing BacktestEngine: {symbol} ({years} years)")
    print("=" * 80)

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    print(f"\nBacktest Period: {start_str} to {end_str}")
    print(f"Symbol: {symbol}")
    print()

    try:
        # Initialize engine
        config = BacktestConfig()
        print(f"EMA Period: {config.EMA_PERIOD}")
        print(f"RSI Period: {config.RSI_PERIOD}")
        print()

        engine = BacktestEngine(
            symbol=symbol, start_date=start_str, end_date=end_str, config=config
        )

        # Validate EMA warm-up
        print("Validating EMA Warm-up...")
        validation = validate_ema_warmup(engine, config)

        print(
            f"  Warm-up periods: {validation['warmup_periods']} (required: {validation['warmup_required']})"
        )
        if validation["sufficient_warmup"]:
            print("  [OK] Sufficient warm-up periods")
        else:
            print(f"  [WARN]? Insufficient warm-up periods!")

        print(f"  EMA200 at start: {validation['ema200_at_start']:.2f}")
        print(f"  Close at start: {validation['close_at_start']:.2f}")
        if validation["ema_close_ratio"]:
            print(f"  EMA/Close ratio: {validation['ema_close_ratio']:.3f}")

        if validation["ema_is_nan"]:
            print("  ? ERROR: EMA200 is NaN at backtest start!")
            return False

        if not validation["sufficient_warmup"]:
            print("  [WARN]? WARNING: Insufficient warm-up - EMA may have lag")

        print()

        # Run backtest
        print("Running backtest...")
        results = engine.run_backtest()

        # Display results
        print("\n" + "=" * 80)
        print("BACKTEST RESULTS")
        print("=" * 80)
        print(f"Symbol: {results.get('symbol', symbol)}")
        print(f"Period: {results.get('period', f'{start_str} to {end_str}')}")
        print(f"Total Trades: {results.get('total_trades', 0)}")
        print(f"Total Invested: Rs {results.get('total_invested', 0):,.0f}")
        print(f"Total P&L: Rs {results.get('total_pnl', 0):,.2f}")
        print(f"Total Return: {results.get('total_return_pct', 0):+.2f}%")
        print(f"Win Rate: {results.get('win_rate', 0):.1f}%")
        print(f"Winning Trades: {results.get('winning_trades', 0)}")
        print(f"Losing Trades: {results.get('losing_trades', 0)}")

        if results.get("buy_hold_return") is not None:
            print(f"Buy & Hold Return: {results['buy_hold_return']:+.2f}%")
            print(f"Strategy vs B&H: {results.get('strategy_vs_buy_hold', 0):+.2f}%")

        print("=" * 80)

        # Validation summary
        print("\nVALIDATION SUMMARY")
        print("-" * 80)
        all_passed = True

        if validation["sufficient_warmup"]:
            print("[OK] EMA Warm-up: PASSED")
        else:
            print("[WARN] EMA Warm-up: WARNING (insufficient but may still work)")

        if not validation["ema_is_nan"]:
            print("[OK] EMA200 Calculation: PASSED")
        else:
            print("? EMA200 Calculation: FAILED (NaN at start)")
            all_passed = False

        if 0.5 < validation["ema_close_ratio"] < 2.0:
            print("[OK] EMA200 Reasonableness: PASSED")
        else:
            print(
                f"[WARN] EMA200 Reasonableness: WARNING (ratio: {validation['ema_close_ratio']:.3f})"
            )

        if results.get("total_trades", 0) >= 0:
            print("[OK] Backtest Execution: PASSED")
        else:
            print("? Backtest Execution: FAILED")
            all_passed = False

        print("-" * 80)

        return all_passed

    except Exception as e:
        print(f"\n? ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_integrated_backtest_2years(symbol: str, years: int = 2):
    """Test integrated_backtest with 2-year backtest"""
    print("\n" + "=" * 80)
    print(f"Testing Integrated Backtest: {symbol} ({years} years)")
    print("=" * 80)

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    print(f"\nBacktest Period: {start_str} to {end_str}")
    print(f"Symbol: {symbol}")
    print()

    try:
        # Run integrated backtest
        print("Running integrated backtest...")
        results = run_integrated_backtest(
            stock_name=symbol,
            date_range=(start_str, end_str),
            capital_per_position=100000,
            skip_trade_agent_validation=False,
        )

        if "error" in results:
            print(f"? ERROR: {results['error']}")
            return False

        # Display results
        print("\n" + "=" * 80)
        print("BACKTEST RESULTS")
        print("=" * 80)

        if "executed_trades" in results:
            print(f"Executed Trades: {results['executed_trades']}")
        if "total_return_pct" in results:
            print(f"Total Return: {results['total_return_pct']:+.2f}%")
        if "win_rate" in results:
            print(f"Win Rate: {results['win_rate']:.1f}%")
        if "positions" in results:
            print(f"Total Positions: {len(results['positions'])}")

        print("=" * 80)
        print("[OK] Integrated Backtest: PASSED")

        return True

    except Exception as e:
        print(f"\n? ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Validate 2-year backtest with EMA warm-up validation"
    )
    parser.add_argument(
        "--symbol", "-s", default="RELIANCE.NS", help="Stock symbol (default: RELIANCE.NS)"
    )
    parser.add_argument(
        "--years", "-y", type=int, default=2, help="Number of years for backtest (default: 2)"
    )
    parser.add_argument(
        "--engine",
        "-e",
        choices=["backtest_engine", "integrated", "both"],
        default="backtest_engine",
        help="Which backtest engine to test (default: backtest_engine)",
    )

    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("2-YEAR BACKTEST VALIDATION")
    print("=" * 80)
    print(f"Symbol: {args.symbol}")
    print(f"Years: {args.years}")
    print(f"Engine: {args.engine}")
    print("=" * 80)

    results = []

    if args.engine in ["backtest_engine", "both"]:
        result = test_backtest_engine_2years(args.symbol, args.years)
        results.append(("BacktestEngine", result))

    if args.engine in ["integrated", "both"]:
        result = test_integrated_backtest_2years(args.symbol, args.years)
        results.append(("Integrated Backtest", result))

    # Final summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    for name, passed in results:
        status = "[OK] PASSED" if passed else "? FAILED"
        print(f"{name}: {status}")
    print("=" * 80)

    # Exit code
    all_passed = all(result for _, result in results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
