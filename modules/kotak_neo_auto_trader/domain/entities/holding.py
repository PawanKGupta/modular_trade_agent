"""
Holding Entity
Represents a portfolio holding with P&L calculations
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from ..value_objects import Money, Exchange


@dataclass
class Holding:
    """
    Domain entity representing a portfolio holding
    
    Tracks ownership of securities with cost basis and current value
    """
    
    # Identity
    symbol: str
    exchange: Exchange = Exchange.NSE
    
    # Quantity
    quantity: int = 0
    
    # Pricing
    average_price: Money = Money.zero()
    current_price: Money = Money.zero()
    
    # Metadata
    last_updated: datetime = None
    isin: Optional[str] = None
    product_type: str = "CNC"
    
    def __post_init__(self):
        """Validate holding constraints"""
        if not self.symbol or len(self.symbol.strip()) == 0:
            raise ValueError("Symbol cannot be empty")
        
        if self.quantity < 0:
            raise ValueError(f"Quantity cannot be negative: {self.quantity}")
        
        if self.last_updated is None:
            self.last_updated = datetime.now()
    
    # Calculation methods
    
    def calculate_cost_basis(self) -> Money:
        """Calculate total cost basis (what was paid)"""
        return self.average_price * self.quantity
    
    def calculate_market_value(self) -> Money:
        """Calculate current market value"""
        return self.current_price * self.quantity
    
    def calculate_pnl(self) -> Money:
        """Calculate unrealized profit and loss"""
        return self.calculate_market_value() - self.calculate_cost_basis()
    
    def calculate_pnl_percentage(self) -> float:
        """
        Calculate P&L as percentage
        
        Returns:
            P&L percentage (e.g., 15.5 for 15.5% gain)
        """
        if self.average_price.amount == 0:
            return 0.0
        
        pnl = self.calculate_pnl()
        cost = self.calculate_cost_basis()
        
        if cost.amount == 0:
            return 0.0
        
        return float((pnl.amount / cost.amount) * 100)
    
    def calculate_price_change(self) -> Money:
        """Calculate price change per share"""
        return self.current_price - self.average_price
    
    def calculate_price_change_percentage(self) -> float:
        """Calculate price change percentage per share"""
        if self.average_price.amount == 0:
            return 0.0
        
        change = self.calculate_price_change()
        return float((change.amount / self.average_price.amount) * 100)
    
    # Query methods
    
    def is_profitable(self) -> bool:
        """Check if holding is in profit"""
        return self.calculate_pnl().amount > 0
    
    def is_at_loss(self) -> bool:
        """Check if holding is in loss"""
        return self.calculate_pnl().amount < 0
    
    def is_break_even(self) -> bool:
        """Check if holding is at break-even"""
        return self.calculate_pnl().amount == 0
    
    def has_quantity(self) -> bool:
        """Check if holding has quantity"""
        return self.quantity > 0
    
    # Update methods
    
    def update_price(self, new_price: Money, update_time: Optional[datetime] = None) -> None:
        """
        Update current price
        
        Args:
            new_price: New market price
            update_time: Time of update (defaults to now)
        """
        if new_price.amount < 0:
            raise ValueError(f"Price cannot be negative: {new_price}")
        
        self.current_price = new_price
        self.last_updated = update_time or datetime.now()
    
    def add_quantity(self, quantity: int, price: Money) -> None:
        """
        Add quantity with price averaging
        
        Args:
            quantity: Quantity to add
            price: Price at which quantity was acquired
        """
        if quantity <= 0:
            raise ValueError(f"Quantity to add must be positive: {quantity}")
        
        # Calculate new average price
        total_cost = self.calculate_cost_basis() + (price * quantity)
        new_quantity = self.quantity + quantity
        self.average_price = total_cost / new_quantity
        self.quantity = new_quantity
        self.last_updated = datetime.now()
    
    def reduce_quantity(self, quantity: int) -> None:
        """
        Reduce quantity (e.g., after selling)
        
        Args:
            quantity: Quantity to reduce
            
        Raises:
            ValueError: If quantity to reduce exceeds held quantity
        """
        if quantity <= 0:
            raise ValueError(f"Quantity to reduce must be positive: {quantity}")
        
        if quantity > self.quantity:
            raise ValueError(
                f"Cannot reduce {quantity} shares: only {self.quantity} held"
            )
        
        self.quantity -= quantity
        self.last_updated = datetime.now()
    
    # Display methods
    
    def __str__(self) -> str:
        """Human-readable string representation"""
        pnl = self.calculate_pnl()
        pnl_pct = self.calculate_pnl_percentage()
        pnl_sign = "+" if pnl.amount >= 0 else ""
        
        return (
            f"Holding({self.symbol}: {self.quantity} @ {self.average_price} "
            f"→ {self.current_price} | P&L: {pnl_sign}{pnl} ({pnl_sign}{pnl_pct:.2f}%))"
        )
    
    def __repr__(self) -> str:
        """Developer representation"""
        return (
            f"Holding(symbol='{self.symbol}', quantity={self.quantity}, "
            f"average_price={self.average_price}, current_price={self.current_price})"
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange.value,
            "quantity": self.quantity,
            "average_price": str(self.average_price),
            "current_price": str(self.current_price),
            "cost_basis": str(self.calculate_cost_basis()),
            "market_value": str(self.calculate_market_value()),
            "pnl": str(self.calculate_pnl()),
            "pnl_percentage": self.calculate_pnl_percentage(),
            "last_updated": self.last_updated.isoformat(),
            "isin": self.isin,
            "product_type": self.product_type,
        }
