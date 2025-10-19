#!/usr/bin/env python3
"""
Backtesting Script for Trading Strategy

This script provides an easy-to-use interface for running backtests on the 
EMA200 + RSI10 pyramiding strategy.

Usage:
    python run_backtest.py SYMBOL START_DATE END_DATE [OPTIONS]

Examples:
    python run_backtest.py RELIANCE.NS 2022-01-01 2023-12-31
    python run_backtest.py AAPL 2020-01-01 2023-12-31 --export-trades --generate-report
    python run_backtest.py TCS.NS 2021-06-01 2023-06-01 --capital 200000
"""

import sys
import argparse
from datetime import datetime, timedelta
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest import BacktestEngine, PerformanceAnalyzer, BacktestConfig


def validate_date(date_string):
    """Validate date format"""
    try:
        return datetime.strptime(date_string, '%Y-%m-%d').strftime('%Y-%m-%d')
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_string}. Use YYYY-MM-DD")


def validate_symbol(symbol):
    """Basic symbol validation"""
    symbol = symbol.upper().strip()
    if not symbol:
        raise argparse.ArgumentTypeError("Symbol cannot be empty")
    return symbol


def create_custom_config(args):
    """Create custom configuration based on command line arguments"""
    config = BacktestConfig()
    
    # Override with custom values if provided
    if args.capital:
        config.POSITION_SIZE = args.capital
        config.INITIAL_CAPITAL = args.capital
        
    if args.rsi_period:
        config.RSI_PERIOD = args.rsi_period
        
    if args.ema_period:
        config.EMA_PERIOD = args.ema_period
        
    if args.max_positions:
        config.MAX_POSITIONS = args.max_positions
        
    if hasattr(args, 'no_pyramiding') and args.no_pyramiding:
        config.ENABLE_PYRAMIDING = False
        
    # Set logging level
    config.DETAILED_LOGGING = not args.quiet
    
    return config


def main():
    """Main backtesting function"""
    parser = argparse.ArgumentParser(
        description="Run backtest on EMA200 + RSI10 pyramiding strategy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_backtest.py RELIANCE.NS 2022-01-01 2023-12-31
  python run_backtest.py AAPL 2020-01-01 2023-12-31 --export-trades --generate-report
  python run_backtest.py TCS.NS 2021-06-01 2023-06-01 --capital 200000
        """
    )
    
    # Required arguments
    parser.add_argument('symbol', type=validate_symbol, 
                       help='Stock symbol (e.g., RELIANCE.NS, AAPL)')
    parser.add_argument('start_date', type=validate_date,
                       help='Backtest start date (YYYY-MM-DD)')
    parser.add_argument('end_date', type=validate_date,
                       help='Backtest end date (YYYY-MM-DD)')
    
    # Strategy configuration
    parser.add_argument('--capital', type=int, default=100000,
                       help='Capital per position (default: 100000)')
    parser.add_argument('--rsi-period', type=int, default=10,
                       help='RSI period (default: 10)')
    parser.add_argument('--ema-period', type=int, default=200,
                       help='EMA period (default: 200)')
    parser.add_argument('--max-positions', type=int, default=10,
                       help='Maximum positions for pyramiding (default: 10)')
    parser.add_argument('--no-pyramiding', action='store_true',
                       help='Disable pyramiding (only single entry)')
    
    # Output options
    parser.add_argument('--export-trades', action='store_true',
                       help='Export detailed trades to CSV')
    parser.add_argument('--generate-report', action='store_true',
                       help='Generate detailed performance report')
    parser.add_argument('--save-report', action='store_true',
                       help='Save report to file (implies --generate-report)')
    parser.add_argument('--quiet', action='store_true',
                       help='Suppress detailed logging during backtest')
    
    args = parser.parse_args()
    
    # Validate date range
    start = datetime.strptime(args.start_date, '%Y-%m-%d')
    end = datetime.strptime(args.end_date, '%Y-%m-%d')
    
    if start >= end:
        print("Error: Start date must be before end date")
        sys.exit(1)
        
    if end > datetime.now():
        print("Warning: End date is in the future. Using current date as end date.")
        args.end_date = datetime.now().strftime('%Y-%m-%d')
    
    # Create configuration
    config = create_custom_config(args)
    
    print(f"🚀 Starting Backtest")
    print(f"Symbol: {args.symbol}")
    print(f"Period: {args.start_date} to {args.end_date}")
    print(f"Capital per position: ₹{config.POSITION_SIZE:,}")
    print(f"Strategy: EMA{config.EMA_PERIOD} + RSI{config.RSI_PERIOD}")
    print(f"Pyramiding: {'Enabled' if config.ENABLE_PYRAMIDING else 'Disabled'}")
    print("=" * 60)
    
    try:
        # Initialize and run backtest
        engine = BacktestEngine(
            symbol=args.symbol,
            start_date=args.start_date,
            end_date=args.end_date,
            config=config
        )
        
        # Run the backtest
        results = engine.run_backtest()
        
        # Print summary
        engine.print_summary()
        
        # Initialize performance analyzer
        analyzer = PerformanceAnalyzer(engine)
        
        # Export trades if requested
        if args.export_trades:
            print(f"\\n📊 Exporting trades...")
            try:
                filepath = analyzer.export_trades_to_csv()
                print(f"✅ Trades exported successfully!")
            except Exception as e:
                print(f"❌ Failed to export trades: {e}")
        
        # Generate report if requested
        if args.generate_report or args.save_report:
            print(f"\\n📋 Generating performance report...")
            try:
                report = analyzer.generate_report(save_to_file=args.save_report)
                if not args.save_report:
                    print("\\n" + report)
                print(f"✅ Report generated successfully!")
            except Exception as e:
                print(f"❌ Failed to generate report: {e}")
        
        # Show quick stats
        if results.get('total_trades', 0) > 0:
            print(f"\\n📈 QUICK STATS")
            print(f"Total Return: {results['total_return_pct']:+.2f}%")
            print(f"Win Rate: {results['win_rate']:.1f}%")
            print(f"Best Trade: {results.get('best_trade_pct', 0):+.2f}%")
            print(f"Worst Trade: {results.get('worst_trade_pct', 0):+.2f}%")
            
            if results['strategy_vs_buy_hold'] > 0:
                print(f"🎉 Strategy outperformed buy & hold by {results['strategy_vs_buy_hold']:+.2f}%")
            else:
                print(f"📉 Strategy underperformed buy & hold by {abs(results['strategy_vs_buy_hold']):.2f}%")
        
        print(f"\\n✅ Backtest completed successfully!")
        
    except KeyboardInterrupt:
        print(f"\\n🛑 Backtest interrupted by user")
        sys.exit(1)
        
    except Exception as e:
        print(f"\\n❌ Error during backtest: {e}")
        if not args.quiet:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()