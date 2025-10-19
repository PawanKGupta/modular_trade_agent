#!/usr/bin/env python3
"""
Generic Integrated Backtest Test Script

This script allows testing any stock with the integrated backtest-trade agent workflow
using command line arguments for stock symbol and date range.

Usage:
    python test_integrated.py STOCK_SYMBOL START_DATE END_DATE [CAPITAL]

Examples:
    python test_integrated.py ICICIBANK.NS 2025-01-01 2025-10-01
    python test_integrated.py RELIANCE.NS 2024-01-01 2024-12-31 200000
    python test_integrated.py ORIENTCEM.NS 2025-01-15 2025-06-15
    python test_integrated.py TCS.NS 2023-01-01 2023-12-31 150000
"""

import sys
import os
import argparse
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from integrated_backtest import run_integrated_backtest, print_integrated_results


def validate_date(date_string):
    """Validate date format"""
    try:
        return datetime.strptime(date_string, '%Y-%m-%d').strftime('%Y-%m-%d')
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_string}. Use YYYY-MM-DD")


def validate_stock_symbol(symbol):
    """Basic stock symbol validation"""
    symbol = symbol.upper().strip()
    if not symbol:
        raise argparse.ArgumentTypeError("Stock symbol cannot be empty")
    
    # Add .NS suffix if it's an Indian stock without suffix
    if '.' not in symbol and len(symbol) <= 12:  # Likely NSE symbol
        print(f"Note: Adding .NS suffix to {symbol} (assuming NSE stock)")
        symbol = f"{symbol}.NS"
    
    return symbol


def get_stock_sector_info(symbol):
    """Get basic sector information for known stocks"""
    sector_map = {
        'ICICIBANK.NS': 'Banking & Financial Services',
        'HDFCBANK.NS': 'Banking & Financial Services', 
        'SBIN.NS': 'Banking & Financial Services',
        'RELIANCE.NS': 'Oil & Gas, Petrochemicals',
        'TCS.NS': 'Information Technology',
        'INFY.NS': 'Information Technology',
        'ORIENTCEM.NS': 'Cement Manufacturing',
        'ULTRACEM.NS': 'Cement Manufacturing',
        'WIPRO.NS': 'Information Technology',
        'LT.NS': 'Engineering & Construction',
        'MARUTI.NS': 'Automobiles',
        'TATASTEEL.NS': 'Steel & Metals',
    }
    
    return sector_map.get(symbol, 'Unknown Sector')


def print_stock_specific_analysis(results, symbol):
    """Print stock-specific analysis based on the results"""
    
    if not results:
        return
        
    print(f"\n📊 {symbol} SPECIFIC ANALYSIS")
    print("=" * 60)
    
    # Basic metrics
    total_signals = results.get('total_signals', 0)
    executed_trades = results.get('executed_trades', 0)
    approval_rate = results.get('trade_agent_accuracy', 0)
    sector = get_stock_sector_info(symbol)
    
    print(f"Stock Information:")
    print(f"  • Symbol: {symbol}")
    print(f"  • Sector: {sector}")
    print(f"  • Test Period: {results.get('period', 'N/A')}")
    
    print(f"\nSignal Quality Analysis:")
    print(f"  • Backtest identified {total_signals} potential entry opportunities")
    print(f"  • Trade agent approved {executed_trades} signals for execution")
    print(f"  • Signal approval rate: {approval_rate:.1f}%")
    
    if executed_trades > 0:
        print(f"\n💰 Trading Performance:")
        total_return = results.get('total_return_pct', 0)
        win_rate = results.get('win_rate', 0)
        winning_trades = results.get('winning_trades', 0)
        losing_trades = results.get('losing_trades', 0)
        
        print(f"  • Strategy return: {total_return:+.2f}%")
        print(f"  • Win rate: {win_rate:.1f}%")
        print(f"  • Winning trades: {winning_trades}")
        print(f"  • Losing trades: {losing_trades}")
        
        if results.get('buy_hold_return'):
            buy_hold = results['buy_hold_return']
            alpha = results.get('strategy_vs_buy_hold', 0)
            print(f"  • Buy & Hold return: {buy_hold:+.2f}%")
            print(f"  • Strategy alpha: {alpha:+.2f}%")
            
            if alpha > 0:
                print(f"  🎉 Strategy OUTPERFORMED buy & hold by {alpha:.2f}%!")
            elif alpha < 0:
                print(f"  📉 Strategy underperformed buy & hold by {abs(alpha):.2f}%")
            else:
                print(f"  📊 Strategy matched buy & hold performance")
        
        # Position analysis
        if 'positions' in results and results['positions']:
            positions = results['positions']
            
            print(f"\n📈 Trade Details:")
            for i, pos in enumerate(positions, 1):
                entry_date = pos['entry_date']
                exit_date = pos['exit_date']
                return_pct = pos['return_pct']
                exit_reason = pos['exit_reason']
                entry_price = pos['entry_price']
                exit_price = pos['exit_price']
                
                status = "🟢" if return_pct > 0 else "🔴" if return_pct < 0 else "⚪"
                print(f"  {status} Trade {i}: {entry_date} → {exit_date}")
                print(f"      Entry: ₹{entry_price:.2f} | Exit: ₹{exit_price:.2f} | Return: {return_pct:+.1f}%")
                print(f"      Exit Reason: {exit_reason}")
                
    else:
        print(f"\n⏸️ No trades executed during the test period.")
        print(f"This indicates:")
        print(f"  • Conservative trade agent filtering (good risk management)")
        print(f"  • Possibly challenging market conditions for the strategy")
        print(f"  • High-quality screening preventing marginal trades")
        
        if total_signals > 0:
            print(f"  • The strategy did identify {total_signals} potential opportunities")
            print(f"  • All were filtered out by advanced multi-timeframe analysis")
    
    # Sector-specific insights
    print(f"\n🏭 SECTOR INSIGHTS ({sector}):")
    if 'BANK' in symbol or 'Banking' in sector:
        print(f"  • Banking stocks are sensitive to interest rate changes")
        print(f"  • Monitor RBI policy decisions and credit growth")
        print(f"  • Consider asset quality and NPA trends")
    elif 'IT' in sector or symbol in ['TCS.NS', 'INFY.NS', 'WIPRO.NS']:
        print(f"  • IT stocks sensitive to USD/INR exchange rates")
        print(f"  • Monitor global technology spending trends")
        print(f"  • Consider client concentration and deal pipeline")
    elif 'CEMENT' in symbol or 'Cement' in sector:
        print(f"  • Cement stocks sensitive to infrastructure spending")
        print(f"  • Monitor government capex and real estate demand")
        print(f"  • Consider seasonal construction activity patterns")
    elif symbol == 'RELIANCE.NS':
        print(f"  • Sensitive to crude oil prices and refining margins")
        print(f"  • Monitor petrochemical spreads and retail expansion")
        print(f"  • Consider digital services (Jio) performance")
    else:
        print(f"  • Monitor sector-specific trends and regulations")
        print(f"  • Consider macroeconomic factors affecting the industry")


def main():
    """Main function to run integrated backtest with command line arguments"""
    
    parser = argparse.ArgumentParser(
        description="Run integrated backtest for any stock",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_integrated.py ICICIBANK.NS 2025-01-01 2025-10-01
  python test_integrated.py RELIANCE.NS 2024-01-01 2024-12-31 200000
  python test_integrated.py TCS 2023-01-01 2023-12-31
  python test_integrated.py ORIENTCEM.NS 2025-01-15 2025-06-15 150000
        """
    )
    
    # Required arguments
    parser.add_argument('symbol', type=validate_stock_symbol,
                       help='Stock symbol (e.g., ICICIBANK.NS, RELIANCE.NS, TCS)')
    parser.add_argument('start_date', type=validate_date,
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('end_date', type=validate_date,
                       help='End date (YYYY-MM-DD)')
    
    # Optional arguments
    parser.add_argument('capital', type=int, nargs='?', default=100000,
                       help='Capital per position (default: 100000)')
    parser.add_argument('--sector-info', action='store_true',
                       help='Show detailed sector-specific analysis')
    parser.add_argument('--quiet', action='store_true',
                       help='Reduce output verbosity')
    
    args = parser.parse_args()
    
    # Validate date range
    start = datetime.strptime(args.start_date, '%Y-%m-%d')
    end = datetime.strptime(args.end_date, '%Y-%m-%d')
    
    if start >= end:
        print("❌ Error: Start date must be before end date")
        sys.exit(1)
    
    if end > datetime.now():
        print("⚠️  Warning: End date is in the future. Market data may not be available.")
    
    # Print test information
    if not args.quiet:
        print("🧪 INTEGRATED BACKTEST TEST")
        print("=" * 80)
        print(f"Stock: {args.symbol}")
        print(f"Period: {args.start_date} to {args.end_date}")
        print(f"Capital per Position: ₹{args.capital:,}")
        print(f"Sector: {get_stock_sector_info(args.symbol)}")
        
        days = (end - start).days
        print(f"Duration: {days} calendar days (~{days//30} months)")
        print()
        
        print("Testing Workflow:")
        print("1. 🔍 Identify potential buy signals using EMA200 + RSI10 strategy")
        print("2. 🤖 Validate each signal through advanced trade agent analysis")
        print("3. ✅ Execute trades only on confirmed 'BUY' signals")
        print("4. 🎯 Track positions until target/stop conditions are met")
        print("5. 📊 Generate comprehensive performance analysis")
        print()
    
    try:
        # Run the integrated backtest
        print("🚀 Starting integrated backtest analysis...")
        results = run_integrated_backtest(args.symbol, (args.start_date, args.end_date), args.capital)
        
        if not args.quiet:
            # Print standard results
            print_integrated_results(results)
            
            # Print stock-specific analysis
            print_stock_specific_analysis(results, args.symbol)
        else:
            # Quiet mode - just essential info
            if results:
                signals = results.get('total_signals', 0)
                trades = results.get('executed_trades', 0)
                approval = results.get('trade_agent_accuracy', 0)
                return_pct = results.get('total_return_pct', 0)
                
                print(f"✅ {args.symbol}: {signals} signals, {trades} trades ({approval:.1f}% approval), {return_pct:+.1f}% return")
            else:
                print(f"❌ {args.symbol}: Test failed")
        
        print(f"\n✅ Test completed successfully for {args.symbol}!")
        return results
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        if not args.quiet:
            print(f"This might be due to:")
            print(f"  • Future dates (data not yet available)")
            print(f"  • Network connectivity issues")
            print(f"  • Invalid stock symbol")
            print(f"  • Insufficient market data")
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()