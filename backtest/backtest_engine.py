"""
Backtesting Engine Module

This module implements the core backtesting logic for the trading strategy.
It handles the day-by-day iteration, signal detection, and trade execution.
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

from .backtest_config import BacktestConfig
from .position_manager import PositionManager
from core.indicators import wilder_rsi
import pandas_ta as ta


class BacktestEngine:
    """
    Main backtesting engine that executes the trading strategy
    
    Strategy Rules:
    1. Entry: Price > EMA200 AND RSI10 < 30
    2. Buy at next day's opening price with 100,000 capital
    3. Pyramiding:
       - If RSI10 < 20: buy again
       - If RSI10 < 10: buy again  
       - If RSI10 > 30, then < 30 again: buy again
    4. Continue until target condition is met (to be implemented separately)
    """
    
    def __init__(self, symbol: str, start_date: str, end_date: str, config: BacktestConfig = None):
        """
        Initialize the backtesting engine
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "RELIANCE.NS")
            start_date: Start date for backtest (YYYY-MM-DD format)
            end_date: End date for backtest (YYYY-MM-DD format) 
            config: Backtesting configuration
        """
        self.symbol = symbol
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.config = config or BacktestConfig()
        
        # Core components
        self.position_manager = PositionManager(symbol, self.config)
        self.data = None
        self.results = {}
        
        # State tracking for RSI reset conditions
        self.last_rsi_above_30_date = None
        self.rsi_10_trade_made = False  # Track if RSI < 10 trade was made
        self.rsi_20_trade_made = False  # Track if RSI < 20 trade was made
        self.first_entry_made = False
        
        # Load and prepare data
        self._load_data()
        
    def _load_data(self):
        """
        Load and prepare market data with auto-adjustment for sufficient EMA data
        Uses fetch_multi_timeframe_data() for consistency with main system
        """
        try:
            from core.data_fetcher import fetch_multi_timeframe_data
            from config.strategy_config import StrategyConfig
            
            # Get config for data fetching strategy
            strategy_config = StrategyConfig.default()
            
            # Calculate required buffer for EMA200: need ~300+ trading days for reliable EMA200
            # Assuming ~252 trading days per year, we need ~1.5 years of data minimum
            required_trading_days = max(self.config.EMA_PERIOD * 1.5, 300)
            
            # Convert to calendar days (accounting for weekends/holidays)
            required_calendar_days = int(required_trading_days * 1.4)  # ~1.4 calendar days per trading day
            
            # Auto-adjust start date to ensure sufficient data
            auto_start_date = self.start_date - timedelta(days=required_calendar_days)
            data_end = self.end_date + timedelta(days=10)  # Buffer for next day execution
            
            print(f"Auto-calculating start date for EMA{self.config.EMA_PERIOD} reliability...")
            print(f"Requested backtest period: {self.start_date.date()} to {self.end_date.date()}")
            print(f"Data fetch period: {auto_start_date.date()} to {data_end.date()} (auto-adjusted)")
            
            # Use fetch_multi_timeframe_data() for consistency
            # Calculate minimum days needed (use configurable max years)
            min_days = max(required_calendar_days, strategy_config.data_fetch_daily_max_years * 365)
            
            # Fetch data using configurable data fetching strategy
            multi_data = fetch_multi_timeframe_data(
                ticker=self.symbol,
                days=min_days,
                end_date=data_end.strftime('%Y-%m-%d'),
                add_current_day=False,  # Backtesting mode - no current day data
                config=strategy_config
            )
            
            if multi_data is None or multi_data.get('daily') is None:
                raise ValueError(f"No data available for {self.symbol}")
            
            # Use daily data (weekly not needed for backtest)
            self.data = multi_data['daily']
            
            if self.data.empty:
                raise ValueError(f"No data available for {self.symbol}")
            
            # Ensure date column is set as index for filtering
            if 'date' in self.data.columns:
                self.data['date'] = pd.to_datetime(self.data['date'])
                self.data = self.data.set_index('date')
            
            # Ensure we have required columns (convert to proper case)
            required_cols_lower = ['open', 'high', 'low', 'close', 'volume']
            required_cols_upper = ['Open', 'High', 'Low', 'Close', 'Volume']
            
            # Check if columns are lowercase (from fetch_multi_timeframe_data)
            if all(col in self.data.columns for col in required_cols_lower):
                # Rename to uppercase for compatibility
                self.data = self.data.rename(columns={
                    'open': 'Open',
                    'high': 'High',
                    'low': 'Low',
                    'close': 'Close',
                    'volume': 'Volume'
                })
            elif not all(col in self.data.columns for col in required_cols_upper):
                missing_cols = [col for col in required_cols_upper if col not in self.data.columns]
                raise ValueError(f"Missing required columns: {missing_cols}")
            
            # Calculate technical indicators
            self._calculate_indicators()
            
            # Check if we have data for the requested backtest period before filtering
            backtest_period_data = self.data.loc[self.start_date:self.end_date]
            
            if backtest_period_data.empty:
                raise ValueError(f"No data available for requested backtest period: {self.start_date.date()} to {self.end_date.date()}")
            
            print(f"Indicators calculated. Total historical data: {len(self.data)} points")
            print(f"Backtest period data: {len(backtest_period_data)} trading days")
            
            # Filter to backtest period
            self.data = backtest_period_data
            
            if len(self.data) < 20:  # Minimum reasonable backtest period
                raise ValueError(f"Insufficient backtest period data: {len(self.data)} days (need at least 20 days)")
                
            print(f"Data loaded successfully for backtest period: {len(self.data)} trading days")
            
        except Exception as e:
            print(f"Error loading data: {e}")
            raise
            
    def _calculate_indicators(self):
        """Calculate technical indicators using pandas_ta (standardized method)"""
        try:
            # Calculate RSI using pandas_ta (standardized method)
            rsi_col = f'RSI{self.config.RSI_PERIOD}'
            self.data[rsi_col] = ta.rsi(self.data['Close'], length=self.config.RSI_PERIOD)
            
            # Also keep 'RSI10' for backward compatibility if period is 10
            if self.config.RSI_PERIOD == 10:
                self.data['RSI10'] = self.data[rsi_col]
            
            # Calculate EMA200 using pandas_ta (standardized method)
            self.data['EMA200'] = ta.ema(self.data['Close'], length=self.config.EMA_PERIOD)
            
            # Drop NaN values
            self.data = self.data.dropna()
            
            print(f"Technical indicators calculated. Data points after cleanup: {len(self.data)}")
            
        except Exception as e:
            print(f"Error calculating indicators: {e}")
            raise
    
    def _check_entry_conditions(self, row: pd.Series, current_date: pd.Timestamp) -> Tuple[bool, str]:
        """
        Check if entry conditions are met
        
        Args:
            row: Current day's data
            current_date: Current date
            
        Returns:
            Tuple of (should_enter, entry_reason)
        """
        close_price = row['Close']
        # Use configurable RSI column name
        rsi_col = f'RSI{self.config.RSI_PERIOD}'
        rsi = row[rsi_col] if rsi_col in row.index else row.get('RSI10')
        ema200 = row['EMA200']
        
        # Skip if missing data
        if pd.isna(rsi) or pd.isna(ema200):
            return False, "Missing indicator data"
            
        if not self.first_entry_made:
            # Adaptive initial entry condition based on EMA200 position
            # Above EMA200: RSI < 30, Below EMA200: RSI < 20 (more selective)
            
            if close_price > ema200:
                # Above EMA200: Standard uptrend dip buying (RSI < 30)
                if rsi < self.config.RSI_OVERSOLD_LEVEL_1:  # RSI < 30
                    return True, f"Initial entry: RSI {rsi:.1f} < 30 (above EMA200)"
                return False, f"RSI {rsi:.1f} not oversold enough for uptrend dip (need < 30)"
            else:
                # Below EMA200: Extreme oversold required (RSI < 20)
                if rsi < self.config.RSI_OVERSOLD_LEVEL_2:  # RSI < 20
                    return True, f"Initial entry: RSI {rsi:.1f} < 20 (below EMA200 - extreme oversold)"
                return False, f"RSI {rsi:.1f} not extreme oversold for below-trend entry (need < 20)"
            
        else:
            # Pyramiding conditions - NO EMA200 check for re-entries (averaging down)
            open_positions = len(self.position_manager.get_open_positions())
            
            if open_positions >= self.config.MAX_POSITIONS:
                return False, "Maximum positions reached"
            
            # Check pyramiding conditions with proper averaging logic (no EMA200 requirement)
            # First time at RSI level = immediate trade
            # Subsequent times at RSI level = need RSI > 30 reset first
            
            if rsi < self.config.RSI_OVERSOLD_LEVEL_3:  # RSI < 10
                if not self.rsi_10_trade_made:
                    # First time RSI reaches < 10, execute immediately
                    self.rsi_10_trade_made = True
                    return True, f"Pyramiding: Extreme RSI {rsi:.1f} < 10 (first time)"
                elif self.last_rsi_above_30_date is not None:
                    # Subsequent times, need RSI > 30 reset first
                    self.last_rsi_above_30_date = None
                    self.rsi_10_trade_made = True
                    return True, f"Pyramiding: Extreme RSI {rsi:.1f} < 10 (after reset)"
                return False, f"RSI {rsi:.1f} < 10 but already traded at this level (need RSI > 30 reset)"
                
            elif rsi < self.config.RSI_OVERSOLD_LEVEL_2:  # RSI < 20
                if not self.rsi_20_trade_made:
                    # First time RSI reaches < 20, execute immediately
                    self.rsi_20_trade_made = True
                    return True, f"Pyramiding: High RSI {rsi:.1f} < 20 (first time)"
                elif self.last_rsi_above_30_date is not None:
                    # Subsequent times, need RSI > 30 reset first
                    self.last_rsi_above_30_date = None
                    self.rsi_20_trade_made = True
                    return True, f"Pyramiding: High RSI {rsi:.1f} < 20 (after reset)"
                return False, f"RSI {rsi:.1f} < 20 but already traded at this level (need RSI > 30 reset)"
                
            elif rsi < self.config.RSI_OVERSOLD_LEVEL_1:  # RSI < 30
                # RSI < 30 always needs reset (since initial entry was already at RSI < 30)
                if self.last_rsi_above_30_date is not None:
                    self.last_rsi_above_30_date = None
                    return True, f"Pyramiding: RSI {rsi:.1f} < 30 (after reset)"
                return False, f"RSI {rsi:.1f} < 30 but no reset signal (need RSI > 30 first)"
                
        return False, "No entry conditions met"
        
    def _update_rsi_state(self, rsi: float, current_date: pd.Timestamp):
        """Update RSI state tracking - only track RSI > 30 for reset"""
        # Track RSI > 30 transitions (this resets all trade flags)
        if rsi > self.config.RSI_OVERSOLD_LEVEL_1:  # RSI > 30
            if self.last_rsi_above_30_date is None:
                self.last_rsi_above_30_date = current_date
                # Reset trade flags when RSI goes above 30
                self.rsi_10_trade_made = False
                self.rsi_20_trade_made = False
                
    def _execute_trade(self, entry_date: pd.Timestamp, entry_reason: str) -> bool:
        """
        Execute a trade at next trading day's open price
        
        Args:
            entry_date: Date when signal was generated
            entry_reason: Reason for the entry
            
        Returns:
            True if trade was executed successfully
        """
        try:
            # Find next trading day
            next_day_data = self.data.loc[self.data.index > entry_date]
            
            if next_day_data.empty:
                print(f"No next day data available for trade execution on {entry_date.date()}")
                return False
                
            next_day = next_day_data.index[0]
            entry_price = next_day_data.iloc[0]['Open']
            
            if pd.isna(entry_price) or entry_price <= 0:
                print(f"Invalid entry price {entry_price} on {next_day.date()}")
                return False
                
            # Execute the trade
            position = self.position_manager.add_position(
                entry_date=next_day,
                entry_price=entry_price,
                entry_reason=entry_reason
            )
            
            if position:
                self.first_entry_made = True
                if self.config.DETAILED_LOGGING:
                    print(f"🟢 TRADE EXECUTED: {next_day.date()} | "
                          f"Price: {entry_price:.2f} | "
                          f"Quantity: {position.quantity} | "
                          f"Capital: {position.capital:.0f} | "
                          f"Reason: {entry_reason}")
                return True
            else:
                print(f"Failed to add position on {next_day.date()}")
                return False
                
        except Exception as e:
            print(f"Error executing trade: {e}")
            return False
            
    def run_backtest(self) -> Dict:
        """
        Run the complete backtest
        
        Returns:
            Dictionary containing backtest results
        """
        print(f"Starting backtest for {self.symbol}")
        print(f"Period: {self.start_date.date()} to {self.end_date.date()}")
        print(f"Strategy: EMA200 + RSI10 with Pyramiding")
        print("-" * 50)
        
        trade_count = 0
        
        try:
            # Get RSI column name from config
            rsi_col = f'RSI{self.config.RSI_PERIOD}'
            
            # Iterate through each trading day
            for current_date, row in self.data.iterrows():
                
                # Update RSI state tracking
                rsi_value = row[rsi_col] if rsi_col in row.index else row.get('RSI10')
                if not pd.isna(rsi_value):
                    self._update_rsi_state(rsi_value, current_date)
                
                # Check entry conditions
                should_enter, entry_reason = self._check_entry_conditions(row, current_date)
                
                if should_enter:
                    # Execute trade at next day's open
                    if self._execute_trade(current_date, entry_reason):
                        trade_count += 1
                        
            # Close all remaining positions at end of backtest period
            if self.position_manager.get_open_positions():
                final_date = self.data.index[-1]
                final_price = self.data.iloc[-1]['Close']
                self.position_manager.close_all_positions(
                    exit_date=final_date,
                    exit_price=final_price,
                    exit_reason="End of backtest period"
                )
                
            # Generate results
            self.results = self._generate_results()
            
            print("-" * 50)
            print(f"Backtest completed!")
            print(f"Total trades executed: {trade_count}")
            print(f"Total positions created: {len(self.position_manager.positions)}")
            
            return self.results
            
        except Exception as e:
            print(f"Error during backtesting: {e}")
            raise
            
    def _generate_results(self) -> Dict:
        """Generate comprehensive backtest results"""
        try:
            positions = self.position_manager.positions
            
            if not positions:
                return {
                    'symbol': self.symbol,
                    'period': f"{self.start_date.date()} to {self.end_date.date()}",
                    'total_trades': 0,
                    'message': 'No trades executed during backtest period'
                }
            
            # Calculate performance metrics
            total_invested = sum(p.capital for p in positions)
            total_pnl = sum(p.get_pnl() for p in positions)
            total_return_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
            
            winning_trades = [p for p in positions if p.get_pnl() > 0]
            losing_trades = [p for p in positions if p.get_pnl() < 0]
            
            win_rate = len(winning_trades) / len(positions) * 100 if positions else 0
            
            avg_win = sum(p.get_pnl() for p in winning_trades) / len(winning_trades) if winning_trades else 0
            avg_loss = sum(p.get_pnl() for p in losing_trades) / len(losing_trades) if losing_trades else 0
            
            # Get first and last prices for buy-and-hold comparison
            first_price = self.data.iloc[0]['Close']
            last_price = self.data.iloc[-1]['Close'] 
            buy_hold_return = (last_price - first_price) / first_price * 100
            
            results = {
                'symbol': self.symbol,
                'period': f"{self.start_date.date()} to {self.end_date.date()}",
                'total_trades': len(positions),
                'total_invested': total_invested,
                'total_pnl': total_pnl,
                'total_return_pct': total_return_pct,
                'win_rate': win_rate,
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else float('inf'),
                'buy_hold_return': buy_hold_return,
                'strategy_vs_buy_hold': total_return_pct - buy_hold_return,
                'open_positions': len(self.position_manager.get_open_positions()),
                'closed_positions': len(self.position_manager.get_closed_positions())
            }
            
            return results
            
        except Exception as e:
            print(f"Error generating results: {e}")
            return {'error': str(e)}
            
    def get_trades_dataframe(self) -> pd.DataFrame:
        """Get detailed trades as DataFrame"""
        return self.position_manager.get_trades_dataframe()
        
    def print_summary(self):
        """Print a formatted summary of backtest results"""
        if not self.results:
            print("No results available. Run backtest first.")
            return
            
        print("\n" + "="*60)
        print(f"BACKTEST SUMMARY - {self.symbol}")
        print("="*60)
        print(f"Period: {self.results['period']}")
        print(f"Total Trades: {self.results['total_trades']}")
        
        if self.results['total_trades'] > 0:
            print(f"Total Invested: ₹{self.results['total_invested']:,.0f}")
            print(f"Total P&L: ₹{self.results['total_pnl']:,.0f}")
            print(f"Total Return: {self.results['total_return_pct']:+.2f}%")
            print(f"Win Rate: {self.results['win_rate']:.1f}%")
            print(f"Winning Trades: {self.results['winning_trades']}")
            print(f"Losing Trades: {self.results['losing_trades']}")
            print(f"Average Win: ₹{self.results['avg_win']:,.0f}")
            print(f"Average Loss: ₹{self.results['avg_loss']:,.0f}")
            
            if self.results['profit_factor'] != float('inf'):
                print(f"Profit Factor: {self.results['profit_factor']:.2f}")
            
            print(f"\nBuy & Hold Return: {self.results['buy_hold_return']:+.2f}%")
            print(f"Strategy vs B&H: {self.results['strategy_vs_buy_hold']:+.2f}%")
            
            if self.results['strategy_vs_buy_hold'] > 0:
                print("🎉 Strategy OUTPERFORMED buy & hold!")
            else:
                print("📉 Strategy UNDERPERFORMED buy & hold.")
        
        print("="*60)