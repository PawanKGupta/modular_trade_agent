"""
Trade Entity - Domain Layer

Represents a trade execution with entry, exit, and P&L tracking.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from enum import Enum


class TradeStatus(Enum):
    """Trade status"""
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TradeDirection(Enum):
    """Trade direction"""
    LONG = "long"
    SHORT = "short"


@dataclass
class Trade:
    """
    Trade entity representing a single trade execution
    
    Attributes:
        ticker: Stock symbol
        entry_date: Date of trade entry
        entry_price: Price at entry
        quantity: Number of shares
        capital: Capital deployed
        direction: Trade direction (long/short)
        status: Trade status (open/closed)
        exit_date: Date of trade exit (if closed)
        exit_price: Price at exit (if closed)
        stop_loss: Stop loss price
        target: Target price
        entry_reason: Reason for entry
    """
    ticker: str
    entry_date: datetime
    entry_price: float
    quantity: int
    capital: float
    direction: TradeDirection = TradeDirection.LONG
    status: TradeStatus = TradeStatus.OPEN
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    entry_reason: str = ""
    
    def __post_init__(self):
        """Validate trade attributes"""
        if self.entry_price <= 0:
            raise ValueError("Entry price must be positive")
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
        if self.capital <= 0:
            raise ValueError("Capital must be positive")
    
    def close(self, exit_date: datetime, exit_price: float):
        """Close the trade"""
        self.exit_date = exit_date
        self.exit_price = exit_price
        self.status = TradeStatus.CLOSED
    
    def cancel(self):
        """Cancel the trade"""
        self.status = TradeStatus.CANCELLED
    
    def is_open(self) -> bool:
        """Check if trade is open"""
        return self.status == TradeStatus.OPEN
    
    def is_closed(self) -> bool:
        """Check if trade is closed"""
        return self.status == TradeStatus.CLOSED
    
    def get_pnl(self) -> float:
        """Calculate profit/loss"""
        if not self.is_closed() or self.exit_price is None:
            return 0.0
        
        if self.direction == TradeDirection.LONG:
            return (self.exit_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.exit_price) * self.quantity
    
    def get_pnl_percentage(self) -> float:
        """Calculate profit/loss percentage"""
        if not self.is_closed():
            return 0.0
        
        pnl = self.get_pnl()
        return (pnl / self.capital) * 100
    
    def get_holding_days(self) -> int:
        """Calculate holding period in days"""
        if not self.is_closed() or self.exit_date is None:
            return 0
        return (self.exit_date - self.entry_date).days
    
    def is_winner(self) -> bool:
        """Check if trade was profitable"""
        return self.is_closed() and self.get_pnl() > 0
    
    def __str__(self) -> str:
        status_str = f"{self.status.value}"
        if self.is_closed():
            pnl_pct = self.get_pnl_percentage()
            status_str += f" ({pnl_pct:+.2f}%)"
        return f"Trade({self.ticker}, {self.entry_price}, {status_str})"
    
    def __repr__(self) -> str:
        return self.__str__()
