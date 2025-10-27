"""
Stock Entity - Domain Layer

Represents a stock with its fundamental attributes.
This is a core business entity independent of any infrastructure concerns.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Stock:
    """
    Stock entity representing a tradable security
    
    Attributes:
        ticker: Stock symbol (e.g., "RELIANCE.NS")
        name: Company name (optional)
        exchange: Exchange name (e.g., "NSE", "BSE")
        last_close: Most recent closing price
        last_updated: Timestamp of last data update
    """
    ticker: str
    exchange: str
    last_close: float
    last_updated: datetime
    name: Optional[str] = None
    
    def __post_init__(self):
        """Validate stock attributes"""
        if not self.ticker:
            raise ValueError("Ticker cannot be empty")
        if self.last_close <= 0:
            raise ValueError("Last close price must be positive")
    
    def get_display_symbol(self) -> str:
        """Get formatted display symbol"""
        return self.ticker
    
    def is_valid(self) -> bool:
        """Check if stock data is valid"""
        return bool(self.ticker) and self.last_close > 0
    
    def __str__(self) -> str:
        return f"Stock({self.ticker}, {self.last_close})"
    
    def __repr__(self) -> str:
        return self.__str__()
