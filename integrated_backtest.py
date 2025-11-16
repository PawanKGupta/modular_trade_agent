#!/usr/bin/env python3
"""
Integrated Backtest - Single-Pass Daily Iteration

Iterates through trading days once, checking RSI conditions daily and executing
trades inline. This eliminates the redundancy between BacktestEngine signal
generation and daily monitoring that existed in the previous implementation.

Thread-safe: All state is local to function calls, no shared/global variables.

FIXED BUG: Previous implementation had a critical bug where exit conditions
(High >= Target OR RSI > 50) were checked but never acted upon during daily
monitoring, causing positions to stay open indefinitely and accumulate re-entries
when they should have exited. This version properly exits positions immediately
when exit conditions are met.
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')
import pandas_ta as ta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.analysis import analyze_ticker
from core.data_fetcher import fetch_ohlcv_yf


class Position:
    """Represents a trading position"""

    def __init__(self, stock_name: str, entry_date: str, entry_price: float,
                 target_price: float, capital: float = 100000, entry_rsi: float = None):
        self.stock_name = stock_name
        self.entry_date = pd.to_datetime(entry_date)
        self.entry_price = entry_price
        self.target_price = target_price
        self.capital = capital
        self.quantity = int(capital / entry_price)
        self.fills = [{
            'date': pd.to_datetime(entry_date),
            'price': entry_price,
            'capital': capital,
            'quantity': self.quantity
        }]
        self.exit_date = None
        self.exit_price = None
        self.exit_reason = None
        self.is_closed = False

        # ML Outcome tracking (Phase 3: ML Enhanced Features)
        self.max_drawdown_pct = 0.0  # Maximum Adverse Excursion (MAE)
        self.daily_lows = []  # Track daily lows for drawdown calculation

        # RSI level tracking (matches auto trader)
        # CRITICAL: Mark ALL levels above entry RSI as taken
        if entry_rsi is not None:
            if entry_rsi < 10:
                self.levels_taken = {"30": True, "20": True, "10": True}
            elif entry_rsi < 20:
                self.levels_taken = {"30": True, "20": True, "10": False}
            elif entry_rsi < 30:
                self.levels_taken = {"30": True, "20": False, "10": False}
            else:
                self.levels_taken = {"30": False, "20": False, "10": False}
        else:
            # Default: assume entry at RSI < 30
            self.levels_taken = {"30": True, "20": False, "10": False}

        self.reset_ready = False

    def add_reentry(self, add_date: str, add_price: float, add_capital: float, new_target: float, rsi_level: int):
        """Add a re-entry fill"""
        add_qty = int(add_capital / add_price) if add_price > 0 else 0
        if add_qty <= 0:
            return

        prev_qty = self.quantity
        prev_avg = self.entry_price

        # Update capital/qty
        self.capital += add_capital
        self.quantity += add_qty

        # Recompute average entry
        self.entry_price = ((prev_avg * prev_qty) + (add_price * add_qty)) / max(self.quantity, 1)

        # Update target
        self.target_price = new_target

        # Mark level as taken
        self.levels_taken[str(rsi_level)] = True

        # Track fill
        self.fills.append({
            'date': pd.to_datetime(add_date),
            'price': add_price,
            'capital': add_capital,
            'quantity': add_qty,
            'rsi_level': rsi_level
        })

    def update_drawdown(self, current_date: str, low_price: float):
        """
        Update max drawdown tracking (ML Enhanced Features - Phase 3).

        Tracks the worst unrealized loss during position lifetime.
        This helps ML learn risk patterns.

        Args:
            current_date: Current date (YYYY-MM-DD)
            low_price: Intraday low price
        """
        # Track daily low for MAE calculation
        self.daily_lows.append(low_price)

        # Calculate unrealized loss from entry
        unrealized_pnl_pct = ((low_price - self.entry_price) / self.entry_price) * 100

        # Update max drawdown if this is worse
        if unrealized_pnl_pct < self.max_drawdown_pct:
            self.max_drawdown_pct = unrealized_pnl_pct

    def close_position(self, exit_date: str, exit_price: float, exit_reason: str):
        """Close the position"""
        self.exit_date = pd.to_datetime(exit_date)
        self.exit_price = exit_price
        self.exit_reason = exit_reason
        self.is_closed = True

    def get_pnl(self) -> float:
        if not self.is_closed:
            return 0
        return (self.exit_price - self.entry_price) * self.quantity

    def get_return_pct(self) -> float:
        if not self.is_closed:
            return 0
        return ((self.exit_price - self.entry_price) / self.entry_price) * 100

    def get_days_to_exit(self) -> int:
        """Get number of days from entry to exit (ML Enhanced Features - Phase 3)"""
        if not self.is_closed or self.exit_date is None:
            return 0
        return (self.exit_date - self.entry_date).days


def validate_initial_entry_with_trade_agent(stock_name: str, signal_date: str,
                                            rsi: float, ema200: float,
                                            full_market_data: pd.DataFrame) -> Optional[Dict]:
    """
    Validate initial entry with trade agent.
    Returns dict with buy_price, target if approved, None if rejected.

    Uses the same approach as integrated_backtest.py trade_agent() wrapper.
    """
    try:
        # Call analyze_ticker using AnalysisService (same as old implementation)
        from services.analysis_service import AnalysisService
        from config.strategy_config import StrategyConfig

        # Convert column names to lowercase for AnalysisService
        market_data_for_agent = full_market_data.copy()
        if 'Close' in market_data_for_agent.columns:
            market_data_for_agent = market_data_for_agent.rename(columns={
                'Open': 'open', 'High': 'high', 'Low': 'low',
                'Close': 'close', 'Volume': 'volume'
            })

        service = AnalysisService(config=StrategyConfig.default())
        result = service.analyze_ticker(
            ticker=stock_name,
            enable_multi_timeframe=True,
            export_to_csv=False,
            as_of_date=signal_date,
            pre_fetched_daily=market_data_for_agent,
            pre_fetched_weekly=None,
            pre_calculated_indicators={'rsi': rsi, 'ema200': ema200}
        )

        if result.get('status') != 'success':
            print(f"      ⏸️ Analysis failed: {result.get('status', 'unknown')}")
            return None

        verdict = result.get('verdict', 'avoid')

        if verdict in ['buy', 'strong_buy']:
            confidence = 'high' if verdict == 'strong_buy' else 'medium'
            target = result.get('target', 0)
            print(f"      ✅ Trade Agent: BUY signal (confidence: {confidence})")
            return {
                'approved': True,
                'target': target
            }
        else:
            print(f"      ⏸️ Trade Agent: WATCH signal (verdict: {verdict})")
            return None

    except Exception as e:
        print(f"      ⚠️ Trade agent error: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_integrated_backtest(stock_name: str, date_range: Tuple[str, str],
                            capital_per_position: float = 50000,
                            skip_trade_agent_validation: bool = False) -> Dict:
    """
    Single-pass integrated backtest - checks RSI daily and executes trades inline.

    Thread-safe: All state is local, no shared variables.

    Args:
        stock_name: Stock symbol
        date_range: (start_date, end_date)
        capital_per_position: Capital per position
        skip_trade_agent_validation: If True, skip trade agent validation and execute
                                     all signals that meet RSI<30 & price>EMA200.
                                     Use for ML training data collection. Default: False

    Returns:
        Backtest results dictionary
    """
    start_date, end_date = date_range

    print(f"🚀 Starting Integrated Backtest for {stock_name}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Capital per position: ${capital_per_position:,.0f}")
    print(f"Target: EMA9 at entry/re-entry date")
    print(f"Exit: High >= Target OR RSI > 50")
    print("=" * 60)

    # Fetch market data with buffer for indicators
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    # EMA200 needs: 200 periods + ~100 warm-up = 300 trading days ≈ 420 calendar days
    ema_buffer_days = int((200 + 100) * 1.4)  # EMA200 + warm-up, converted to calendar days
    days_needed = (end_dt - start_dt).days + ema_buffer_days

    market_data = fetch_ohlcv_yf(
        ticker=stock_name,
        days=days_needed,
        interval='1d',
        end_date=end_date,
        add_current_day=False
    )

    if market_data is None or market_data.empty:
        return {'error': 'Failed to fetch market data'}

    # Prepare data
    if 'date' in market_data.columns:
        market_data = market_data.set_index('date')

    market_data = market_data.rename(columns={
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume'
    })

    # Calculate indicators
    market_data['RSI10'] = ta.rsi(market_data['Close'], length=10)
    market_data['EMA9'] = ta.ema(market_data['Close'], length=9)
    market_data['EMA200'] = ta.ema(market_data['Close'], length=200)

    # EMA WARM-UP FIX: Check for sufficient warm-up period before backtest start
    # EMA needs time to stabilize after initialization - first ~50-100 values may have lag
    ema_warmup_periods = min(100, int(200 * 0.5))  # 50% of EMA200 period or 100
    data_before_start = market_data.loc[market_data.index < start_dt]

    if len(data_before_start) < ema_warmup_periods:
        available_warmup = len(data_before_start)
        print(f"   ⚠️ EMA Warm-up Warning: Only {available_warmup} periods before backtest start (recommended: {ema_warmup_periods})")
        print(f"   ⚠️ EMA values at backtest start may have lag")

        # If critical, adjust start date to allow warm-up
        if available_warmup < 20:
            earliest_valid = market_data.index.min()
            adjusted_start = earliest_valid + pd.Timedelta(days=int(ema_warmup_periods * 1.4))
            if adjusted_start < start_dt:
                print(f"   ⚠️ Adjusting backtest start to {adjusted_start.date()} for EMA warm-up")
                start_dt = adjusted_start
    else:
        print(f"   ✓ EMA Warm-up: {len(data_before_start)} periods before backtest start (sufficient)")

    # Filter to backtest period
    backtest_data = market_data.loc[(market_data.index >= start_dt) & (market_data.index <= end_dt)]

    if backtest_data.empty:
        return {'error': 'No data in backtest period'}

    print(f"   ✓ Data loaded: {len(backtest_data)} trading days in backtest period")
    print(f"   ✓ Total historical data: {len(market_data)} days")
    print()

    # Track state
    position: Optional[Position] = None
    all_positions: List[Position] = []  # Track all positions for results
    executed_trades = 0
    skipped_signals = 0
    signal_count = 0  # Counter for signal numbering
    reentries_by_date = {}  # {date: count} for daily cap

    # Iterate through each trading day
    for current_date, row in backtest_data.iterrows():
        date_str = current_date.strftime('%Y-%m-%d')

        # Validate trading day: Check if date is a weekday (Monday=0, Sunday=6)
        weekday = current_date.weekday()
        if weekday >= 5:  # Saturday (5) or Sunday (6)
            print(f"   ⚠️ WARNING: Skipping non-trading day {date_str} (weekend)")
            continue

        rsi = row['RSI10']
        ema200 = row['EMA200']
        ema9 = row['EMA9']
        close = row['Close']
        high = row['High']
        low = row['Low']

        # Skip if RSI is NaN
        if pd.isna(rsi):
            continue

        # Update drawdown tracking for open positions (ML Enhanced Features - Phase 3)
        if position and not position.is_closed:
            position.update_drawdown(date_str, low)

        # Check exit conditions first (if position is open)
        if position and not position.is_closed:
            # Exit condition 1: High >= Target
            # Note: Can exit same day as re-entry if High hits target during the day
            if high >= position.target_price:
                position.close_position(date_str, position.target_price, "Target reached")
                print(f"   🎯 TARGET HIT on {date_str}: Exit at {position.target_price:.2f}")
                print(f"      Entry: {position.entry_date.strftime('%Y-%m-%d')} | Exit: {position.exit_date.strftime('%Y-%m-%d')} | Days: {(position.exit_date - position.entry_date).days}")
                print(f"      P&L: ${position.get_pnl():,.0f} ({position.get_return_pct():+.1f}%)")
                all_positions.append(position)  # Save closed position
                position = None  # Clear position
                continue

            # Exit condition 2: RSI > 50
            elif rsi > 50:
                position.close_position(date_str, close, "RSI > 50")
                print(f"   📊 RSI EXIT on {date_str}: RSI {rsi:.1f} > 50, Exit at {close:.2f}")
                print(f"      Entry: {position.entry_date.strftime('%Y-%m-%d')} | Exit: {position.exit_date.strftime('%Y-%m-%d')} | Days: {(position.exit_date - position.entry_date).days}")
                print(f"      P&L: ${position.get_pnl():,.0f} ({position.get_return_pct():+.1f}%)")
                all_positions.append(position)  # Save closed position
                position = None  # Clear position
                continue

        # RSI state tracking (for reset mechanism)
        if position and not position.is_closed:
            if rsi > 30:
                position.reset_ready = True

        # Check entry/re-entry conditions
        if position and not position.is_closed:
            # We have an open position - check for re-entry opportunities
            next_level = None
            levels = position.levels_taken

            # Reset cycle: RSI > 30 then < 30 again
            if rsi < 30 and position.reset_ready:
                position.levels_taken = {"30": False, "20": False, "10": False}
                position.reset_ready = False
                levels = position.levels_taken
                next_level = 30
            # Normal progression through levels
            elif levels.get('30') and not levels.get('20') and rsi < 20:
                next_level = 20
            elif levels.get('20') and not levels.get('10') and rsi < 10:
                next_level = 10

            if next_level:
                # Check daily cap
                reentries_today = reentries_by_date.get(date_str, 0)
                if reentries_today >= 1:
                    print(f"   ⏸️ RE-ENTRY SKIPPED on {date_str}: Daily cap reached (RSI {rsi:.1f} < {next_level})")
                    continue

                # Find execution date (next trading day)
                next_days = backtest_data.loc[backtest_data.index > current_date]
                if next_days.empty:
                    continue

                exec_date = next_days.index[0]
                exec_date_str = exec_date.strftime('%Y-%m-%d')
                exec_price = next_days.iloc[0]['Open']
                exec_ema9 = next_days.iloc[0]['EMA9']

                # Target is EMA9 (exit condition: High >= EMA9 OR RSI > 50)
                new_target = exec_ema9

                # Execute re-entry (no trade agent validation)
                position.add_reentry(exec_date_str, exec_price, capital_per_position, new_target, next_level)
                reentries_by_date[exec_date_str] = reentries_today + 1

                print(f"   ➕ RE-ENTRY on {exec_date_str}: RSI {rsi:.1f} < {next_level} | Add at {exec_price:.2f}")
                print(f"      New Avg: {position.entry_price:.2f} | New Target: {position.target_price:.2f}")
                executed_trades += 1

        elif not position:
            # No position - check for initial entry
            # Entry conditions: RSI < 30 AND Close > EMA200
            if rsi < 30 and close > ema200:
                signal_count += 1

                # Find execution date (next trading day)
                next_days = backtest_data.loc[backtest_data.index > current_date]
                if next_days.empty:
                    continue

                exec_date = next_days.index[0]
                exec_date_str = exec_date.strftime('%Y-%m-%d')
                exec_price = next_days.iloc[0]['Open']
                exec_ema9 = next_days.iloc[0]['EMA9']

                # Validate with trade agent (unless skipped for training data collection)
                # Additional validation: Verify this is actually a trading day (weekday check already done above)
                weekday_name = current_date.strftime('%A')
                print(f"\n🔄 Signal #{signal_count} detected on {date_str} ({weekday_name})")
                print(f"   RSI: {rsi:.1f} < 30 | Close: {close:.2f} > EMA200: {ema200:.2f}")

                if skip_trade_agent_validation:
                    # For training data: Skip trade agent validation, execute all RSI<30 & price>EMA200
                    print(f"   ⚠️  Training mode: Skipping trade agent validation")
                    validation = {'approved': True, 'target': exec_ema9}
                else:
                    # Normal mode: Validate with trade agent
                    print(f"   🤖 Trade Agent analyzing...")
                    validation = validate_initial_entry_with_trade_agent(
                        stock_name, date_str, rsi, ema200, market_data
                    )

                if validation and validation.get('approved'):
                    # Execute initial entry
                    # Target is EMA9 (exit condition: High >= EMA9 OR RSI > 50)
                    target = exec_ema9

                    position = Position(
                        stock_name=stock_name,
                        entry_date=exec_date_str,
                        entry_price=exec_price,
                        target_price=target,
                        capital=capital_per_position,
                        entry_rsi=rsi  # Pass entry RSI to mark correct levels
                    )

                    print(f"   ✅ INITIAL ENTRY on {exec_date_str}: Buy at {exec_price:.2f}")
                    print(f"      Target: {position.target_price:.2f}")
                    executed_trades += 1
                else:
                    print(f"   ⏸️ SKIPPED: Trade agent rejected")
                    skipped_signals += 1

    # Close any remaining open position at period end
    if position and not position.is_closed:
        final_date = backtest_data.index[-1]
        final_price = backtest_data.iloc[-1]['Close']
        position.close_position(final_date.strftime('%Y-%m-%d'), final_price, "End of period")
        print(f"\n   ⏰ POSITION CLOSED at period end: {final_date.strftime('%Y-%m-%d')}")
        print(f"      P&L: ${position.get_pnl():,.0f} ({position.get_return_pct():+.1f}%)")
        all_positions.append(position)

    # Generate results
    print(f"\n" + "=" * 60)
    print(f"🏁 Integrated Backtest Complete!")
    print(f"Total Signals: {signal_count}")
    print(f"Executed Trades: {executed_trades}")
    print(f"Skipped Signals: {skipped_signals}")
    print(f"Total Positions: {len(all_positions)}")

    # Calculate performance from all positions
    if all_positions:
        total_pnl = sum(p.get_pnl() for p in all_positions)
        total_invested = sum(p.capital for p in all_positions)
        total_return = (total_pnl / total_invested * 100) if total_invested > 0 else 0

        winning = [p for p in all_positions if p.get_pnl() > 0]
        losing = [p for p in all_positions if p.get_pnl() < 0]

        print(f"Total P&L: ${total_pnl:,.0f}")
        print(f"Total Return: {total_return:+.2f}%")
        print(f"Win Rate: {len(winning)/len(all_positions)*100:.1f}%")

        # Convert Position objects to dicts for backward compatibility
        positions_list = []
        for p in all_positions:
            positions_list.append({
                'entry_date': p.entry_date.strftime('%Y-%m-%d'),
                'entry_price': p.entry_price,
                'exit_date': p.exit_date.strftime('%Y-%m-%d') if p.exit_date else None,
                'exit_price': p.exit_price,
                'exit_reason': p.exit_reason,
                'target_price': p.target_price,
                'capital': p.capital,
                'quantity': p.quantity,
                'pnl': p.get_pnl(),
                'return_pct': p.get_return_pct(),
                # ML ENHANCED OUTCOME FEATURES (Phase 3)
                'days_to_exit': p.get_days_to_exit(),
                'max_drawdown_pct': round(p.max_drawdown_pct, 2),
                'fills': p.fills,
                'is_pyramided': len(p.fills) > 1  # Backward compatibility
            })

        results = {
            'stock_name': stock_name,
            'period': f"{start_date} to {end_date}",
            'total_signals': signal_count,  # Backward compatibility
            'executed_trades': executed_trades,
            'skipped_signals': skipped_signals,
            'total_pnl': total_pnl,
            'total_return_pct': total_return,
            'total_positions': len(all_positions),
            'closed_positions': len(all_positions),
            'win_rate': len(winning)/len(all_positions)*100,
            'total_invested': total_invested,
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'positions': positions_list  # Backward compatibility
        }
    else:
        results = {
            'stock_name': stock_name,
            'period': f"{start_date} to {end_date}",
            'total_signals': signal_count,  # Backward compatibility
            'executed_trades': executed_trades,
            'skipped_signals': skipped_signals,
            'total_positions': 0,
            'positions': []  # Backward compatibility
        }

    return results


def print_integrated_results(results: Dict):
    """
    Print formatted results from integrated backtest.
    Compatible with old interface for backwards compatibility.
    """
    if not results:
        print("No results to display")
        return

    print(f"\n{'=' * 60}")
    print(f"📊 BACKTEST RESULTS:")
    print(f"{'=' * 60}")
    print(f"  Stock: {results.get('stock_name', 'N/A')}")
    print(f"  Period: {results.get('period', 'N/A')}")
    print(f"  Executed Trades: {results.get('executed_trades', 0)}")
    print(f"  Skipped Signals: {results.get('skipped_signals', 0)}")

    if 'total_pnl' in results:
        print(f"  Total P&L: ${results.get('total_pnl', 0):,.0f}")
        print(f"  Total Return: {results.get('total_return_pct', 0):+.2f}%")
        print(f"  Win Rate: {results.get('win_rate', 0):.1f}%")
        print(f"  Total Positions: {results.get('total_positions', 0)}")
        print(f"  Winning Trades: {results.get('winning_trades', 0)}")
        print(f"  Losing Trades: {results.get('losing_trades', 0)}")


# Test the new version
if __name__ == "__main__":
    import sys

    stock = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE.NS"
    years = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=years * 365)).strftime('%Y-%m-%d')
    date_range = (start_date, end_date)

    results = run_integrated_backtest(stock, date_range)
    print("\n" + "=" * 60)
    print("RESULTS:")
    print(f"  Executed Trades: {results.get('executed_trades', 0)}")
    print(f"  Skipped Signals: {results.get('skipped_signals', 0)}")
    if results.get('total_pnl'):
        print(f"  Total P&L: ${results.get('total_pnl', 0):,.0f}")
        print(f"  Total Return: {results.get('total_return_pct', 0):+.2f}%")
