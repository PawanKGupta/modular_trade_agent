"""
Position Manager Module

This module manages positions, tracks pyramiding, and handles multiple entries.
"""

import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from .backtest_config import BacktestConfig


class Position:
    """Represents a single position/trade entry"""
    
    def __init__(self, entry_date: datetime, entry_price: float, quantity: int, capital: float, entry_reason: str):
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.quantity = quantity
        self.capital = capital
        self.entry_reason = entry_reason
        self.exit_date = None
        self.exit_price = None
        self.exit_reason = None
        self.is_open = True
        
    def close_position(self, exit_date: datetime, exit_price: float, exit_reason: str):
        """Close the position"""
        self.exit_date = exit_date
        self.exit_price = exit_price
        self.exit_reason = exit_reason
        self.is_open = False
        
    def get_current_value(self, current_price: float) -> float:
        """Get current value of the position"""
        return self.quantity * current_price
        
    def get_pnl(self, current_price: float = None) -> float:
        """Get P&L of the position"""
        if self.is_open and current_price:
            return (current_price - self.entry_price) * self.quantity
        elif not self.is_open:
            return (self.exit_price - self.entry_price) * self.quantity
        return 0
        
    def get_pnl_pct(self, current_price: float = None) -> float:
        """Get P&L percentage"""
        if self.is_open and current_price:
            return ((current_price - self.entry_price) / self.entry_price) * 100
        elif not self.is_open:
            return ((self.exit_price - self.entry_price) / self.entry_price) * 100
        return 0


class PositionManager:
    """Manages all positions for a stock during backtesting"""
    
    def __init__(self, symbol: str, config: BacktestConfig = None):
        self.symbol = symbol
        self.config = config or BacktestConfig()
        self.positions: List[Position] = []
        self.total_invested = 0
        self.last_rsi_above_30 = False  # Track RSI state for re-entry conditions
        
    def can_add_position(self) -> bool:
        """Check if we can add another position (pyramiding rules)"""
        if not self.config.ENABLE_PYRAMIDING:
            return len(self.get_open_positions()) == 0
        return len(self.get_open_positions()) < self.config.MAX_POSITIONS
        
    def add_position(self, entry_date: datetime, entry_price: float, entry_reason: str) -> Optional[Position]:
        """Add a new position"""
        if not self.can_add_position():
            return None
            
        # Calculate quantity based on fixed capital amount
        quantity = int(self.config.POSITION_SIZE / entry_price)
        if quantity <= 0:
            return None
            
        actual_capital = quantity * entry_price
        
        position = Position(
            entry_date=entry_date,
            entry_price=entry_price,
            quantity=quantity,
            capital=actual_capital,
            entry_reason=entry_reason
        )
        
        self.positions.append(position)
        self.total_invested += actual_capital
        
        return position
        
    def get_open_positions(self) -> List[Position]:
        """Get all open positions"""
        return [p for p in self.positions if p.is_open]
        
    def get_closed_positions(self) -> List[Position]:
        """Get all closed positions"""
        return [p for p in self.positions if not p.is_open]
        
    def get_total_quantity(self) -> int:
        """Get total quantity across all open positions"""
        return sum(p.quantity for p in self.get_open_positions())
        
    def get_average_entry_price(self) -> float:
        """Get average entry price across all open positions"""
        open_positions = self.get_open_positions()
        if not open_positions:
            return 0
            
        total_value = sum(p.entry_price * p.quantity for p in open_positions)
        total_quantity = sum(p.quantity for p in open_positions)
        
        return total_value / total_quantity if total_quantity > 0 else 0
        
    def get_total_invested(self) -> float:
        """Get total capital invested in open positions"""
        return sum(p.capital for p in self.get_open_positions())
        
    def get_current_value(self, current_price: float) -> float:
        """Get current value of all open positions"""
        return sum(p.get_current_value(current_price) for p in self.get_open_positions())
        
    def get_unrealized_pnl(self, current_price: float) -> float:
        """Get unrealized P&L for all open positions"""
        return sum(p.get_pnl(current_price) for p in self.get_open_positions())
        
    def get_unrealized_pnl_pct(self, current_price: float) -> float:
        """Get unrealized P&L percentage"""
        total_invested = self.get_total_invested()
        if total_invested == 0:
            return 0
        return (self.get_unrealized_pnl(current_price) / total_invested) * 100
        
    def close_all_positions(self, exit_date: datetime, exit_price: float, exit_reason: str):
        """Close all open positions"""
        for position in self.get_open_positions():
            position.close_position(exit_date, exit_price, exit_reason)
            
    def get_position_summary(self) -> Dict:
        """Get summary of all positions"""
        open_positions = self.get_open_positions()
        closed_positions = self.get_closed_positions()
        
        return {
            'symbol': self.symbol,
            'total_positions': len(self.positions),
            'open_positions': len(open_positions),
            'closed_positions': len(closed_positions),
            'total_invested': self.get_total_invested(),
            'average_entry_price': self.get_average_entry_price(),
            'total_quantity': self.get_total_quantity()
        }
        
    def get_trades_dataframe(self) -> pd.DataFrame:
        """Convert positions to DataFrame for analysis"""
        trades_data = []
        
        for i, position in enumerate(self.positions):
            trades_data.append({
                'symbol': self.symbol,
                'position_id': i + 1,
                'entry_date': position.entry_date,
                'entry_price': position.entry_price,
                'quantity': position.quantity,
                'capital': position.capital,
                'entry_reason': position.entry_reason,
                'exit_date': position.exit_date,
                'exit_price': position.exit_price,
                'exit_reason': position.exit_reason,
                'is_open': position.is_open,
                'pnl': position.get_pnl(),
                'pnl_pct': position.get_pnl_pct()
            })
            
        return pd.DataFrame(trades_data) if trades_data else pd.DataFrame()
