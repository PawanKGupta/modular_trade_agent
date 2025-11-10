"""
Test script for backtest verdict validation with stocks that have better chart quality.

RECOMMENDATION 3: Test with stocks that have better chart quality to validate trade execution.

This script tests stocks that are more likely to pass chart quality filters,
ensuring we can validate trade execution properly.
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from tests.integration.test_backtest_verdict_validation import (
    BacktestVerdictValidator,
    VerdictValidationResult,
    TradeExecutionValidationResult,
    run_comprehensive_backtest_validation
)


def test_stocks_with_better_chart_quality():
    """
    Test backtest validation with stocks that have better chart quality.
    
    These stocks are selected based on:
    - Large-cap stocks with high liquidity
    - Stocks that typically have cleaner charts (fewer gaps)
    - Stocks with consistent trading volumes
    """
    
    # Stocks with better chart quality (large-cap, high liquidity)
    test_stocks = [
        "INFY.NS",  # Infosys - Large-cap IT stock, high liquidity
        "TCS.NS",   # TCS - Large-cap IT stock, high liquidity
        "HDFCBANK.NS",  # HDFC Bank - Large-cap bank, high liquidity
        "ICICIBANK.NS",  # ICICI Bank - Large-cap bank, high liquidity
        "HINDUNILVR.NS",  # Hindustan Unilever - Large-cap FMCG, high liquidity
    ]
    
    # Test with 2 years of data (shorter period for faster testing)
    years = 2
    capital_per_position = 100000
    
    print("=" * 80)
    print("RECOMMENDATION 3: Testing with stocks that have better chart quality")
    print("=" * 80)
    print(f"Test period: {years} years")
    print(f"Capital per position: ${capital_per_position:,.0f}")
    print(f"Test stocks: {', '.join(test_stocks)}")
    print("=" * 80)
    print()
    
    results = []
    
    for stock_symbol in test_stocks:
        print(f"\n{'='*80}")
        print(f"Testing: {stock_symbol}")
        print(f"{'='*80}\n")
        
        try:
            result = run_comprehensive_backtest_validation(
                stock_symbol=stock_symbol,
                years=years,
                capital_per_position=capital_per_position
            )
            results.append((stock_symbol, result))
            
            # Print summary
            print(f"\n{'='*80}")
            print(f"Summary for {stock_symbol}:")
            print(f"{'='*80}")
            print(f"Total signals: {result.get('total_signals', 0)}")
            verdict_validations = result.get('verdict_validations', {})
            trade_validations = result.get('trade_validations', {})
            print(f"Verdict validations passed: {verdict_validations.get('passed', 0)}/{result.get('total_signals', 0)}")
            print(f"Trade validations passed: {trade_validations.get('passed', 0)}/{result.get('total_signals', 0)}")
            print(f"Errors: {len(verdict_validations.get('errors', [])) + len(trade_validations.get('errors', []))}")
            print(f"Warnings: {len(verdict_validations.get('warnings', [])) + len(trade_validations.get('warnings', []))}")
            
            if verdict_validations.get('errors'):
                print(f"\nVerdict Errors (showing first 5):")
                for error in verdict_validations['errors'][:5]:
                    print(f"  - {error}")
            
            if verdict_validations.get('warnings'):
                print(f"\nVerdict Warnings (showing first 5):")
                for warning in verdict_validations['warnings'][:5]:
                    print(f"  - {warning}")
            
        except Exception as e:
            print(f"❌ Error testing {stock_symbol}: {e}")
            import traceback
            traceback.print_exc()
            results.append((stock_symbol, {'error': str(e)}))
    
    # Overall summary
    print(f"\n{'='*80}")
    print("OVERALL SUMMARY")
    print(f"{'='*80}")
    
    total_signals = 0
    total_verdict_passed = 0
    total_trade_passed = 0
    total_errors = 0
    total_warnings = 0
    
    for stock_symbol, result in results:
        if 'error' in result:
            print(f"{stock_symbol}: ERROR - {result['error']}")
            continue
        
        verdict_validations = result.get('verdict_validations', {})
        trade_validations = result.get('trade_validations', {})
        
        total_signals += result.get('total_signals', 0)
        total_verdict_passed += verdict_validations.get('passed', 0)
        total_trade_passed += trade_validations.get('passed', 0)
        total_errors += len(verdict_validations.get('errors', [])) + len(trade_validations.get('errors', []))
        total_warnings += len(verdict_validations.get('warnings', [])) + len(trade_validations.get('warnings', []))
        
        print(f"{stock_symbol}:")
        print(f"  Signals: {result.get('total_signals', 0)}")
        print(f"  Verdict passed: {verdict_validations.get('passed', 0)}/{result.get('total_signals', 0)}")
        print(f"  Trade passed: {trade_validations.get('passed', 0)}/{result.get('total_signals', 0)}")
        print(f"  Errors: {len(verdict_validations.get('errors', [])) + len(trade_validations.get('errors', []))}")
        print(f"  Warnings: {len(verdict_validations.get('warnings', [])) + len(trade_validations.get('warnings', []))}")
    
    print(f"\n{'='*80}")
    print("TOTALS:")
    print(f"{'='*80}")
    print(f"Total signals: {total_signals}")
    print(f"Verdict validations passed: {total_verdict_passed}/{total_signals} ({100*total_verdict_passed/max(total_signals,1):.1f}%)")
    print(f"Trade validations passed: {total_trade_passed}/{total_signals} ({100*total_trade_passed/max(total_signals,1):.1f}%)")
    print(f"Total errors: {total_errors}")
    print(f"Total warnings: {total_warnings}")
    
    # Test conclusion
    if total_signals > 0:
        verdict_pass_rate = 100 * total_verdict_passed / total_signals
        trade_pass_rate = 100 * total_trade_passed / total_signals
        
        print(f"\n{'='*80}")
        print("TEST CONCLUSION:")
        print(f"{'='*80}")
        print(f"Verdict validation pass rate: {verdict_pass_rate:.1f}%")
        print(f"Trade validation pass rate: {trade_pass_rate:.1f}%")
        
        if verdict_pass_rate >= 90 and trade_pass_rate >= 90:
            print("✅ TEST PASSED: Both verdict and trade validations have high pass rates")
        elif verdict_pass_rate >= 80 and trade_pass_rate >= 80:
            print("⚠️ TEST PARTIALLY PASSED: Pass rates are acceptable but could be improved")
        else:
            print("❌ TEST FAILED: Pass rates are too low")
    
    return results


if __name__ == "__main__":
    test_stocks_with_better_chart_quality()
