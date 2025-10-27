"""
Order-related enums as value objects
"""

from enum import Enum


class OrderType(Enum):
    """Type of order"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "SL"
    STOP_LOSS_MARKET = "SL-M"
    
    @classmethod
    def from_string(cls, value: str) -> 'OrderType':
        """Convert string to OrderType with common aliases"""
        mapping = {
            "MARKET": cls.MARKET,
            "MKT": cls.MARKET,
            "M": cls.MARKET,
            "LIMIT": cls.LIMIT,
            "L": cls.LIMIT,
            "LMT": cls.LIMIT,
            "SL": cls.STOP_LOSS,
            "STOP_LOSS": cls.STOP_LOSS,
            "SL-M": cls.STOP_LOSS_MARKET,
            "SLM": cls.STOP_LOSS_MARKET,
            "STOP_LOSS_MARKET": cls.STOP_LOSS_MARKET,
        }
        return mapping.get(value.upper(), cls.MARKET)


class TransactionType(Enum):
    """Type of transaction"""
    BUY = "BUY"
    SELL = "SELL"
    
    @classmethod
    def from_string(cls, value: str) -> 'TransactionType':
        """Convert string to TransactionType with common aliases"""
        mapping = {
            "BUY": cls.BUY,
            "B": cls.BUY,
            "SELL": cls.SELL,
            "S": cls.SELL,
        }
        return mapping.get(value.upper(), cls.BUY)


class OrderStatus(Enum):
    """Status of an order"""
    PENDING = "PENDING"
    OPEN = "OPEN"
    EXECUTED = "EXECUTED"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    TRIGGER_PENDING = "TRIGGER_PENDING"
    
    @classmethod
    def from_string(cls, value: str) -> 'OrderStatus':
        """Convert string to OrderStatus"""
        mapping = {
            "PENDING": cls.PENDING,
            "OPEN": cls.OPEN,
            "EXECUTED": cls.EXECUTED,
            "COMPLETE": cls.COMPLETE,
            "FILLED": cls.COMPLETE,
            "CANCELLED": cls.CANCELLED,
            "CANCELED": cls.CANCELLED,
            "REJECTED": cls.REJECTED,
            "PARTIALLY_FILLED": cls.PARTIALLY_FILLED,
            "PARTIAL": cls.PARTIALLY_FILLED,
            "TRIGGER_PENDING": cls.TRIGGER_PENDING,
        }
        return mapping.get(value.upper(), cls.PENDING)
    
    def is_terminal(self) -> bool:
        """Check if this is a terminal status"""
        return self in {self.EXECUTED, self.COMPLETE, self.CANCELLED, self.REJECTED}
    
    def is_active(self) -> bool:
        """Check if order is still active"""
        return self in {self.PENDING, self.OPEN, self.PARTIALLY_FILLED, self.TRIGGER_PENDING}


class ProductType(Enum):
    """Product type for order"""
    CNC = "CNC"  # Cash and Carry
    MIS = "MIS"  # Margin Intraday Square off
    NRML = "NRML"  # Normal
    
    @classmethod
    def from_string(cls, value: str) -> 'ProductType':
        """Convert string to ProductType"""
        mapping = {
            "CNC": cls.CNC,
            "DELIVERY": cls.CNC,
            "MIS": cls.MIS,
            "INTRADAY": cls.MIS,
            "NRML": cls.NRML,
            "NORMAL": cls.NRML,
        }
        return mapping.get(value.upper(), cls.CNC)


class OrderVariety(Enum):
    """Variety of order"""
    REGULAR = "REGULAR"
    AMO = "AMO"  # After Market Order
    
    @classmethod
    def from_string(cls, value: str) -> 'OrderVariety':
        """Convert string to OrderVariety"""
        mapping = {
            "REGULAR": cls.REGULAR,
            "REG": cls.REGULAR,
            "NORMAL": cls.REGULAR,
            "AMO": cls.AMO,
            "AFTER_MARKET": cls.AMO,
        }
        return mapping.get(value.upper(), cls.REGULAR)


class Exchange(Enum):
    """Stock exchange"""
    NSE = "NSE"
    BSE = "BSE"
    
    @classmethod
    def from_string(cls, value: str) -> 'Exchange':
        """Convert string to Exchange"""
        return cls.NSE if value.upper() == "NSE" else cls.BSE
