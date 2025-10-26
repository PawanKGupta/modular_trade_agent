"""
Price Value Object - Domain Layer

Immutable value object representing a price with validation and comparison.
"""

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class Price:
    """
    Immutable price value object
    
    Attributes:
        value: The price value
        currency: Currency code (default: INR for Indian Rupee)
    """
    value: float
    currency: str = "INR"
    
    def __post_init__(self):
        """Validate price"""
        if self.value < 0:
            raise ValueError("Price cannot be negative")
        if not self.currency:
            raise ValueError("Currency cannot be empty")
    
    def __eq__(self, other: Union['Price', float]) -> bool:
        """Compare prices"""
        if isinstance(other, Price):
            return self.value == other.value and self.currency == other.currency
        elif isinstance(other, (int, float)):
            return self.value == other
        return False
    
    def __lt__(self, other: Union['Price', float]) -> bool:
        """Less than comparison"""
        if isinstance(other, Price):
            if self.currency != other.currency:
                raise ValueError("Cannot compare prices with different currencies")
            return self.value < other.value
        elif isinstance(other, (int, float)):
            return self.value < other
        return NotImplemented
    
    def __le__(self, other: Union['Price', float]) -> bool:
        """Less than or equal comparison"""
        return self == other or self < other
    
    def __gt__(self, other: Union['Price', float]) -> bool:
        """Greater than comparison"""
        if isinstance(other, Price):
            if self.currency != other.currency:
                raise ValueError("Cannot compare prices with different currencies")
            return self.value > other.value
        elif isinstance(other, (int, float)):
            return self.value > other
        return NotImplemented
    
    def __ge__(self, other: Union['Price', float]) -> bool:
        """Greater than or equal comparison"""
        return self == other or self > other
    
    def add(self, amount: float) -> 'Price':
        """Add amount to price"""
        return Price(self.value + amount, self.currency)
    
    def subtract(self, amount: float) -> 'Price':
        """Subtract amount from price"""
        return Price(max(0, self.value - amount), self.currency)
    
    def multiply(self, factor: float) -> 'Price':
        """Multiply price by factor"""
        return Price(self.value * factor, self.currency)
    
    def percentage_change(self, other: 'Price') -> float:
        """Calculate percentage change from other price"""
        if other.value == 0:
            return 0.0
        return ((self.value - other.value) / other.value) * 100
    
    def is_between(self, low: 'Price', high: 'Price') -> bool:
        """Check if price is between two prices"""
        return low <= self <= high
    
    def __str__(self) -> str:
        return f"{self.currency} {self.value:.2f}"
    
    def __repr__(self) -> str:
        return f"Price({self.value}, '{self.currency}')"
