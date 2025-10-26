"""
Money Value Object
Represents monetary values with proper validation and operations
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Union


@dataclass(frozen=True)
class Money:
    """Value object for money amounts with currency"""
    
    amount: Decimal
    currency: str = "INR"
    
    def __post_init__(self):
        """Validate money constraints"""
        # Convert to Decimal if needed
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, 'amount', Decimal(str(self.amount)))
        
        # Round to 2 decimal places for currency
        rounded = self.amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        object.__setattr__(self, 'amount', rounded)
        
        if self.amount < 0:
            raise ValueError(f"Money amount cannot be negative: {self.amount}")
        
        if not self.currency:
            raise ValueError("Currency must be specified")
    
    def __add__(self, other: 'Money') -> 'Money':
        """Add two money amounts"""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot add Money with {type(other)}")
        if self.currency != other.currency:
            raise ValueError(f"Cannot add money with different currencies: {self.currency} and {other.currency}")
        return Money(self.amount + other.amount, self.currency)
    
    def __sub__(self, other: 'Money') -> 'Money':
        """Subtract two money amounts"""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot subtract {type(other)} from Money")
        if self.currency != other.currency:
            raise ValueError(f"Cannot subtract money with different currencies: {self.currency} and {other.currency}")
        return Money(self.amount - other.amount, self.currency)
    
    def __mul__(self, scalar: Union[int, float, Decimal]) -> 'Money':
        """Multiply money by a scalar"""
        if not isinstance(scalar, (int, float, Decimal)):
            raise TypeError(f"Cannot multiply Money by {type(scalar)}")
        return Money(self.amount * Decimal(str(scalar)), self.currency)
    
    def __truediv__(self, scalar: Union[int, float, Decimal]) -> 'Money':
        """Divide money by a scalar"""
        if not isinstance(scalar, (int, float, Decimal)):
            raise TypeError(f"Cannot divide Money by {type(scalar)}")
        if scalar == 0:
            raise ValueError("Cannot divide by zero")
        return Money(self.amount / Decimal(str(scalar)), self.currency)
    
    def __lt__(self, other: 'Money') -> bool:
        """Less than comparison"""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot compare Money with {type(other)}")
        if self.currency != other.currency:
            raise ValueError(f"Cannot compare money with different currencies")
        return self.amount < other.amount
    
    def __le__(self, other: 'Money') -> bool:
        """Less than or equal comparison"""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot compare Money with {type(other)}")
        if self.currency != other.currency:
            raise ValueError(f"Cannot compare money with different currencies")
        return self.amount <= other.amount
    
    def __gt__(self, other: 'Money') -> bool:
        """Greater than comparison"""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot compare Money with {type(other)}")
        if self.currency != other.currency:
            raise ValueError(f"Cannot compare money with different currencies")
        return self.amount > other.amount
    
    def __ge__(self, other: 'Money') -> bool:
        """Greater than or equal comparison"""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot compare Money with {type(other)}")
        if self.currency != other.currency:
            raise ValueError(f"Cannot compare money with different currencies")
        return self.amount >= other.amount
    
    def __eq__(self, other: object) -> bool:
        """Equality comparison"""
        if not isinstance(other, Money):
            return False
        return self.amount == other.amount and self.currency == other.currency
    
    def __hash__(self) -> int:
        """Hash for use in sets and dicts"""
        return hash((self.amount, self.currency))
    
    def __str__(self) -> str:
        """String representation"""
        if self.currency == "INR":
            return f"₹{self.amount:,.2f}"
        return f"{self.amount:,.2f} {self.currency}"
    
    def __repr__(self) -> str:
        """Developer representation"""
        return f"Money(amount=Decimal('{self.amount}'), currency='{self.currency}')"
    
    def to_float(self) -> float:
        """Convert to float (use with caution - may lose precision)"""
        return float(self.amount)
    
    @classmethod
    def zero(cls, currency: str = "INR") -> 'Money':
        """Create zero money"""
        return cls(Decimal('0.00'), currency)
    
    @classmethod
    def from_float(cls, amount: float, currency: str = "INR") -> 'Money':
        """Create Money from float"""
        return cls(Decimal(str(amount)), currency)
    
    @classmethod
    def from_int(cls, amount: int, currency: str = "INR") -> 'Money':
        """Create Money from int"""
        return cls(Decimal(amount), currency)
