#!/usr/bin/env python3
"""
Integrated Backtest-Trade Agent Workflow

This module coordinates the backtesting engine with the trade agent to provide
a comprehensive testing and analysis framework that combines historical backtesting
with live trade evaluation.

Key Features:
- Identifies potential buy/re-entry dates using backtest logic
- Validates each signal through trade agent analysis
- Executes trades only on confirmed "BUY" signals
- Resets indicators after successful target achievement
- Maintains complete separation from main project logic
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

from backtest import BacktestEngine, BacktestConfig
from core.analysis import analyze_ticker


class SignalResult:
    """Container for trade agent signal results"""
    
    def __init__(self, signal_type: str, buy_price: float, target_price: float, 
                 confidence: str = "medium", stop_loss: float = None):
        self.signal_type = signal_type  # "BUY" or "WATCH"
        self.buy_price = buy_price
        self.target_price = target_price
        self.confidence = confidence
        self.stop_loss = stop_loss
        
    def __repr__(self):
        return f"SignalResult(type={self.signal_type}, buy={self.buy_price}, target={self.target_price})"


def run_backtest(stock_name: str, date_range: Tuple[str, str]) -> List[Dict]:
    """
    Performs backtest logic and identifies entry/re-entry dates based on strategy.
    
    Args:
        stock_name: Stock symbol (e.g., "RELIANCE.NS", "AAPL")
        date_range: Tuple of (start_date, end_date) in YYYY-MM-DD format
        
    Returns:
        List of potential trade signals (dates when buy conditions are met)
    """
    start_date, end_date = date_range
    
    print(f"🔍 Running backtest analysis for {stock_name}")
    print(f"Period: {start_date} to {end_date}")
    
    # Create a modified backtest engine that returns signals instead of executing trades
    config = BacktestConfig()
    config.DETAILED_LOGGING = False  # Keep it quiet for signal generation
    
    engine = BacktestEngine(
        symbol=stock_name,
        start_date=start_date,
        end_date=end_date,
        config=config
    )
    
    # Extract potential entry dates from the backtest engine
    potential_signals = []
    
    try:
        # Iterate through the data to identify buy signals
        for current_date, row in engine.data.iterrows():
            # Update RSI state tracking (same logic as backtest engine)
            if not pd.isna(row['RSI10']):
                engine._update_rsi_state(row['RSI10'], current_date)
            
            # Check entry conditions
            should_enter, entry_reason = engine._check_entry_conditions(row, current_date)
            
            if should_enter:
                # Find next trading day for execution price
                next_day_data = engine.data.loc[engine.data.index > current_date]
                if not next_day_data.empty:
                    next_day = next_day_data.index[0]
                    execution_price = next_day_data.iloc[0]['Open']
                    
                    signal = {
                        'signal_date': current_date,
                        'execution_date': next_day, 
                        'execution_price': execution_price,
                        'reason': entry_reason,
                        'rsi': row['RSI10'],
                        'close_price': row['Close'],
                        'ema200': row['EMA200']
                    }
                    potential_signals.append(signal)
                    
                    # Update engine state to track subsequent entries properly
                    engine.first_entry_made = True
        
        print(f"✅ Found {len(potential_signals)} potential entry signals")
        return potential_signals
        
    except Exception as e:
        print(f"❌ Error in backtest analysis: {e}")
        return []


def trade_agent(stock_name: str, buy_date: str) -> SignalResult:
    """
    Ask the analysis engine to compute BUY/WATCH and prices strictly as-of buy_date.
    Returns the trade_agent's buy_range midpoint, target, and stop without modification.
    """
    print(f"🤖 Trade Agent analyzing {stock_name} for date {buy_date}")

    try:
        analysis_result = analyze_ticker(
            stock_name,
            enable_multi_timeframe=True,
            export_to_csv=False,
            as_of_date=buy_date
        )

        if analysis_result.get('status') != 'success':
            print(f"⚠️ Trade agent analysis failed: {analysis_result.get('status', 'unknown')}")
            return SignalResult("WATCH", 0, 0, "low")

        verdict = analysis_result.get('verdict', 'avoid')
        buy_range = analysis_result.get('buy_range', [0, 0])
        target = analysis_result.get('target', 0)
        stop = analysis_result.get('stop', 0)
        last_close = analysis_result.get('last_close', 0)

        buy_px = (buy_range[0] + buy_range[1]) / 2 if buy_range else last_close

        sentiment = analysis_result.get('news_sentiment')
        def _print_sentiment_info(s: dict):
            if not s or not s.get('enabled'):
                return
            lbl = s.get('label', 'neutral')
            sc = s.get('score', 0.0)
            used = s.get('used', 0)
            print(f"   📰 News sentiment: {lbl} ({sc:+.2f}) from {used} recent articles")

        if verdict in ['buy', 'strong_buy']:
            confidence = 'high' if verdict == 'strong_buy' else 'medium'

            if sentiment:
                _print_sentiment_info(sentiment)

            print(f"✅ Trade Agent: BUY signal (confidence: {confidence})")
            print(f"   Buy Price: {buy_px:.2f}, Target: {target:.2f}, Stop: {stop:.2f}")
            return SignalResult("BUY", buy_px, target, confidence, stop)
        else:
            if sentiment:
                _print_sentiment_info(sentiment)
            print(f"⏸️ Trade Agent: WATCH signal (verdict: {verdict})")
            return SignalResult("WATCH", buy_px or last_close, (buy_px or last_close) * 1.05, "low")

    except Exception as e:
        print(f"❌ Trade agent error: {e}")
        return SignalResult("WATCH", 0, 0, "low")


class IntegratedPosition:
    """Represents a position in the integrated backtest system"""
    
    def __init__(self, stock_name: str, entry_date: str, entry_price: float, 
                 target_price: float, stop_loss: float, capital: float = 100000):
        self.stock_name = stock_name
        self.entry_date = pd.to_datetime(entry_date)
        self.entry_price = entry_price
        self.target_price = target_price
        self.stop_loss = stop_loss
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
        
    def add_reentry(self, add_date: str, add_price: float, add_capital: float, new_target: float):
        """Add a re-entry fill and recompute average entry and target"""
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
        # Update target to latest EMA9-derived target
        self.target_price = new_target
        # Track fill
        self.fills.append({
            'date': pd.to_datetime(add_date),
            'price': add_price,
            'capital': add_capital,
            'quantity': add_qty
        })
        
    def close_position(self, exit_date: str, exit_price: float, exit_reason: str):
        """Close the position"""
        self.exit_date = pd.to_datetime(exit_date)
        self.exit_price = exit_price
        self.exit_reason = exit_reason
        self.is_closed = True
        
    def get_pnl(self) -> float:
        """Calculate P&L for the position"""
        if not self.is_closed:
            return 0
        return (self.exit_price - self.entry_price) * self.quantity
        
    def get_return_pct(self) -> float:
        """Calculate return percentage"""
        if not self.is_closed:
            return 0
        return ((self.exit_price - self.entry_price) / self.entry_price) * 100


def run_integrated_backtest(stock_name: str, date_range: Tuple[str, str], 
                          capital_per_position: float = 100000) -> Dict:
    """
    Integrated method that coordinates backtesting and trade agent modules.
    
    Args:
        stock_name: Stock symbol to analyze
        date_range: Tuple of (start_date, end_date) in YYYY-MM-DD format
        capital_per_position: Capital to allocate per position
        
    Returns:
        Dictionary containing integrated backtest results
    """
    start_date, end_date = date_range
    
    print(f"🚀 Starting Integrated Backtest for {stock_name}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Capital per position: ${capital_per_position:,.0f}")
    print("=" * 60)
    
    # Step 1: Run backtest to get potential buy/re-entry dates
    potential_signals = run_backtest(stock_name, date_range)
    
    if not potential_signals:
        return {
            'stock_name': stock_name,
            'period': f"{start_date} to {end_date}",
            'total_signals': 0,
            'executed_trades': 0,
            'message': 'No potential signals found in backtest period'
        }
    
    print(f"\n📊 Processing {len(potential_signals)} potential signals...")
    
    # Track positions and performance
    positions = []
    executed_trades = 0
    skipped_signals = 0
    
    # Get market data for position tracking
    import yfinance as yf
    market_data = yf.download(stock_name, start=start_date, end=end_date, progress=False)
    if isinstance(market_data.columns, pd.MultiIndex):
        market_data.columns = market_data.columns.get_level_values(0)
    # Compute EMA9 for target setting
    try:
        market_data['EMA9'] = ta.ema(market_data['Close'], length=9)
    except Exception:
        market_data['EMA9'] = pd.Series(index=market_data.index, dtype=float)
    
    # Step 2: For each identified buy date, validate with trade agent
    for i, signal in enumerate(potential_signals, 1):
        signal_date = signal['signal_date'].strftime('%Y-%m-%d')
        execution_date = signal['execution_date'].strftime('%Y-%m-%d')
        
        # Determine current position state
        has_open_position = any(not p.is_closed for p in positions)
        
        # If this is labeled as Pyramiding but we have no open position, treat as potential initial
        if signal['reason'].startswith('Pyramiding') and not has_open_position:
            if not (signal['close_price'] > signal['ema200']):
                # Not eligible as initial (below EMA200) — silently skip
                skipped_signals += 1
                continue
            # Eligible as initial — proceed
            derived_reason = 'Initial entry'
        else:
            derived_reason = signal['reason']
        
        print(f"\n🔄 Signal {i}/{len(potential_signals)}: {signal_date}")
        print(f"   Reason: {derived_reason}")
        
        # Validate with trade agent strictly as-of the signal date
        trade_signal = trade_agent(stock_name, signal_date)
        
        if trade_signal.signal_type == "BUY":
            # Determine EMA9 target at execution date
            exec_dt = pd.to_datetime(execution_date)
            ema9_target = None
            if exec_dt in market_data.index and 'EMA9' in market_data.columns:
                ema9_target = market_data.loc[exec_dt]['EMA9']
            if pd.isna(ema9_target) if ema9_target is not None else True:
                ema9_target = trade_signal.target_price or (signal['execution_price'] * 1.08)
            
            # Re-entry vs initial logic
            open_positions = [p for p in positions if not p.is_closed]
            if open_positions:
                # Add to existing position (averaging)
                pos = open_positions[0]
                pos.add_reentry(
                    add_date=execution_date,
                    add_price=signal['execution_price'],
                    add_capital=capital_per_position,
                    new_target=float(ema9_target)
                )
                print(f"   ➕ RE-ENTRY: Add at {signal['execution_price']:.2f} | New Avg: {pos.entry_price:.2f} | Target: {pos.target_price:.2f}")
                # Continue tracking only up to next signal (if any)
                # Next tracking will be scheduled below after we compute until_date
            else:
                # Execute new initial position using EMA9 target (no stop-loss)
                position = IntegratedPosition(
                    stock_name=stock_name,
                    entry_date=execution_date,
                    entry_price=signal['execution_price'],
                    target_price=float(ema9_target),
                    stop_loss=None,
                    capital=capital_per_position
                )
                positions.append(position)
                executed_trades += 1
                
                print(f"   ✅ TRADE EXECUTED: Buy at {signal['execution_price']:.2f}")
                print(f"      Target: {position.target_price:.2f}")
                
                # Tracking is deferred until we know the next signal date
            
        else:
            print(f"   ⏸️ TRADE SKIPPED: Trade agent returned {trade_signal.signal_type}")
            skipped_signals += 1
    
        # After processing this signal, incrementally track any open position up to next signal's execution date
        next_until = None
        if i < len(potential_signals):
            next_until = pd.to_datetime(potential_signals[i]['execution_date'])
        open_positions = [p for p in positions if not p.is_closed]
        if open_positions:
            track_position_to_exit(open_positions[0], market_data, until_date=next_until)
    
    # Generate final results
    results = generate_integrated_results(
        stock_name, date_range, potential_signals, positions, 
        executed_trades, skipped_signals, market_data
    )
    
    # Finalize: track remaining open positions to end of period
    open_positions = [p for p in positions if not p.is_closed]
    if open_positions:
        track_position_to_exit(open_positions[0], market_data, until_date=None)
    
    print(f"\n" + "=" * 60)
    print(f"🏁 Integrated Backtest Complete!")
    print(f"Total Signals: {len(potential_signals)}")
    print(f"Executed Trades: {executed_trades}")
    print(f"Skipped Signals: {skipped_signals}")
    
    if positions:
        total_pnl = sum(pos.get_pnl() for pos in positions if pos.is_closed)
        total_invested = sum(pos.capital for pos in positions)
        total_return_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
        
        print(f"Total P&L: ${total_pnl:,.0f}")
        print(f"Total Return: {total_return_pct:+.2f}%")
    
    return results


def track_position_to_exit(position: IntegratedPosition, market_data: pd.DataFrame, until_date: pd.Timestamp | None = None):
    """Track a position until target is reached or until a specified date.
    If until_date is None, track to the end of the backtest period and close at period end.
    """
    
    # Build slice starting from entry
    data = market_data.loc[market_data.index >= position.entry_date]
    if until_date is not None:
        data = data.loc[data.index <= until_date]
    
    if data.empty:
        print(f"      ⚠️ No market data available for tracking position")
        return
        
    # Track each day until exit condition
    for date, row in data.iterrows():
        high_price = row['High']
        if high_price >= position.target_price:
            position.close_position(
                exit_date=date.strftime('%Y-%m-%d'),
                exit_price=position.target_price,
                exit_reason="Target reached"
            )
            print(f"      🎯 TARGET HIT on {date.strftime('%Y-%m-%d')}: Exit at {position.target_price:.2f}")
            print(f"         P&L: ${position.get_pnl():,.0f} ({position.get_return_pct():+.1f}%)")
            return
    
    # If no exit and we're doing a final pass (no until_date), close at period end
    if until_date is None:
        final_date = data.index[-1]
        final_price = data.iloc[-1]['Close']
        position.close_position(
            exit_date=final_date.strftime('%Y-%m-%d'),
            exit_price=final_price,
            exit_reason="End of period"
        )
        print(f"      ⏰ POSITION CLOSED at period end: Exit at {final_price:.2f}")
        print(f"         P&L: ${position.get_pnl():,.0f} ({position.get_return_pct():+.1f}%)")


def generate_integrated_results(stock_name: str, date_range: Tuple[str, str], 
                              signals: List[Dict], positions: List[IntegratedPosition],
                              executed_trades: int, skipped_signals: int,
                              market_data: pd.DataFrame) -> Dict:
    """Generate comprehensive results for the integrated backtest"""
    
    start_date, end_date = date_range
    
    results = {
        'stock_name': stock_name,
        'period': f"{start_date} to {end_date}",
        'total_signals': len(signals),
        'executed_trades': executed_trades,
        'skipped_signals': skipped_signals,
        'trade_agent_accuracy': executed_trades / len(signals) * 100 if signals else 0
    }
    
    if positions:
        # Calculate performance metrics
        total_invested = sum(pos.capital for pos in positions)
        total_pnl = sum(pos.get_pnl() for pos in positions if pos.is_closed)
        
        winning_positions = [pos for pos in positions if pos.is_closed and pos.get_pnl() > 0]
        losing_positions = [pos for pos in positions if pos.is_closed and pos.get_pnl() < 0]
        
        results.update({
            'total_positions': len(positions),
            'closed_positions': len([pos for pos in positions if pos.is_closed]),
            'total_invested': total_invested,
            'total_pnl': total_pnl,
            'total_return_pct': (total_pnl / total_invested * 100) if total_invested > 0 else 0,
            'winning_trades': len(winning_positions),
            'losing_trades': len(losing_positions),
            'win_rate': len(winning_positions) / len(positions) * 100 if positions else 0,
            'avg_win': sum(pos.get_pnl() for pos in winning_positions) / len(winning_positions) if winning_positions else 0,
            'avg_loss': sum(pos.get_pnl() for pos in losing_positions) / len(losing_positions) if losing_positions else 0
        })
        
        # Calculate buy-and-hold comparison
        if not market_data.empty:
            first_price = market_data.iloc[0]['Close']
            last_price = market_data.iloc[-1]['Close']
            buy_hold_return = (last_price - first_price) / first_price * 100
            
            results.update({
                'buy_hold_return': buy_hold_return,
                'strategy_vs_buy_hold': results['total_return_pct'] - buy_hold_return
            })
        
        # Add position details
        results['positions'] = [
            {
                'entry_date': pos.entry_date.strftime('%Y-%m-%d'),
                'entry_price': pos.entry_price,
                'target_price': pos.target_price,
                'stop_loss': pos.stop_loss,
                'exit_date': pos.exit_date.strftime('%Y-%m-%d') if pos.exit_date else None,
                'exit_price': pos.exit_price,
                'exit_reason': pos.exit_reason,
                'pnl': pos.get_pnl(),
                'return_pct': pos.get_return_pct()
            } for pos in positions
        ]
    
    return results


def print_integrated_results(results: Dict):
    """Print formatted results of the integrated backtest"""
    
    print(f"\n📈 INTEGRATED BACKTEST RESULTS")
    print(f"Stock: {results['stock_name']}")
    print(f"Period: {results['period']}")
    print(f"=" * 50)
    
    print(f"Signal Analysis:")
    print(f"  Total Signals Found: {results['total_signals']}")
    print(f"  Executed Trades: {results['executed_trades']}")
    print(f"  Skipped Signals: {results['skipped_signals']}")
    print(f"  Trade Agent Approval Rate: {results['trade_agent_accuracy']:.1f}%")
    
    if results.get('total_positions', 0) > 0:
        print(f"\nTrading Performance:")
        print(f"  Total Invested: ${results['total_invested']:,.0f}")
        print(f"  Total P&L: ${results['total_pnl']:,.0f}")
        print(f"  Total Return: {results['total_return_pct']:+.2f}%")
        print(f"  Win Rate: {results['win_rate']:.1f}%")
        print(f"  Winning Trades: {results['winning_trades']}")
        print(f"  Losing Trades: {results['losing_trades']}")
        
        if results.get('buy_hold_return'):
            print(f"\nComparison:")
            print(f"  Buy & Hold Return: {results['buy_hold_return']:+.2f}%")
            print(f"  Strategy vs B&H: {results['strategy_vs_buy_hold']:+.2f}%")
            
            if results['strategy_vs_buy_hold'] > 0:
                print(f"  🎉 Strategy OUTPERFORMED buy & hold!")
            else:
                print(f"  📉 Strategy UNDERPERFORMED buy & hold.")


# Example usage
if __name__ == "__main__":
    # Example: Run integrated backtest on RELIANCE.NS
    stock = "RELIANCE.NS"
    date_range = ("2022-01-01", "2023-12-31")
    
    results = run_integrated_backtest(stock, date_range)
    print_integrated_results(results)