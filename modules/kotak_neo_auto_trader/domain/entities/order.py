"""
Order Entity
Represents a trading order with business logic and lifecycle
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from ..value_objects import (
    Money,
    OrderType,
    TransactionType,
    OrderStatus,
    ProductType,
    OrderVariety,
    Exchange
)


@dataclass
class Order:
    """
    Domain entity representing a trading order
    
    Encapsulates order lifecycle and business rules
    """
    
    # Identity
    symbol: str
    
    # Order details
    quantity: int
    order_type: OrderType
    transaction_type: TransactionType
    
    # Optional details
    price: Optional[Money] = None
    product_type: ProductType = ProductType.CNC
    variety: OrderVariety = OrderVariety.REGULAR
    exchange: Exchange = Exchange.NSE
    validity: str = "DAY"
    
    # Lifecycle tracking
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    placed_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    
    # Execution details
    executed_price: Optional[Money] = None
    executed_quantity: int = 0
    
    # Metadata
    remarks: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate order constraints"""
        self._validate()
    
    def _validate(self):
        """Validate order business rules"""
        if not self.symbol or len(self.symbol.strip()) == 0:
            raise ValueError("Symbol cannot be empty")
        
        if self.quantity <= 0:
            raise ValueError(f"Quantity must be positive: {self.quantity}")
        
        if self.order_type == OrderType.LIMIT and self.price is None:
            raise ValueError("Price required for LIMIT orders")
        
        if self.price and self.price.amount <= 0:
            raise ValueError(f"Price must be positive: {self.price}")
    
    # Lifecycle methods
    
    def place(self, order_id: str) -> None:
        """
        Mark order as placed with broker
        
        Args:
            order_id: Broker-assigned order ID
            
        Raises:
            ValueError: If order is not in PENDING status
        """
        if self.status != OrderStatus.PENDING:
            raise ValueError(f"Cannot place order in {self.status} status")
        
        self.order_id = order_id
        self.status = OrderStatus.OPEN
        self.placed_at = datetime.now()
    
    def execute(self, execution_price: Money, executed_quantity: int, execution_time: Optional[datetime] = None) -> None:
        """
        Mark order as executed
        
        Args:
            execution_price: Price at which order was executed
            executed_quantity: Quantity executed
            execution_time: Time of execution (defaults to now)
            
        Raises:
            ValueError: If order is not in executable status
        """
        if not self.status.is_active():
            raise ValueError(f"Cannot execute order in {self.status} status")
        
        if executed_quantity <= 0:
            raise ValueError(f"Executed quantity must be positive: {executed_quantity}")
        
        if executed_quantity > self.quantity:
            raise ValueError(f"Executed quantity ({executed_quantity}) exceeds order quantity ({self.quantity})")
        
        self.executed_price = execution_price
        self.executed_quantity += executed_quantity
        self.executed_at = execution_time or datetime.now()
        
        # Update status based on execution
        if self.executed_quantity >= self.quantity:
            self.status = OrderStatus.COMPLETE
        else:
            self.status = OrderStatus.PARTIALLY_FILLED
    
    def cancel(self, cancellation_time: Optional[datetime] = None) -> None:
        """
        Cancel the order
        
        Args:
            cancellation_time: Time of cancellation (defaults to now)
            
        Raises:
            ValueError: If order cannot be cancelled
        """
        if not self.status.is_active():
            raise ValueError(f"Cannot cancel order in {self.status} status")
        
        self.status = OrderStatus.CANCELLED
        self.cancelled_at = cancellation_time or datetime.now()
    
    def reject(self, reason: str = "") -> None:
        """
        Mark order as rejected
        
        Args:
            reason: Reason for rejection
            
        Raises:
            ValueError: If order is not in PENDING or OPEN status
        """
        if self.status not in [OrderStatus.PENDING, OrderStatus.OPEN]:
            raise ValueError(f"Cannot reject order in {self.status} status")
        
        self.status = OrderStatus.REJECTED
        if reason:
            self.remarks = f"{self.remarks} | Rejected: {reason}".strip(" |")
    
    # Query methods
    
    def is_buy_order(self) -> bool:
        """Check if this is a buy order"""
        return self.transaction_type == TransactionType.BUY
    
    def is_sell_order(self) -> bool:
        """Check if this is a sell order"""
        return self.transaction_type == TransactionType.SELL
    
    def is_market_order(self) -> bool:
        """Check if this is a market order"""
        return self.order_type == OrderType.MARKET
    
    def is_limit_order(self) -> bool:
        """Check if this is a limit order"""
        return self.order_type == OrderType.LIMIT
    
    def is_amo_order(self) -> bool:
        """Check if this is an AMO (After Market Order)"""
        return self.variety == OrderVariety.AMO
    
    def is_pending(self) -> bool:
        """Check if order is pending"""
        return self.status == OrderStatus.PENDING
    
    def is_executed(self) -> bool:
        """Check if order is fully executed"""
        return self.status in [OrderStatus.EXECUTED, OrderStatus.COMPLETE]
    
    def is_cancelled(self) -> bool:
        """Check if order is cancelled"""
        return self.status == OrderStatus.CANCELLED
    
    def is_active(self) -> bool:
        """Check if order is still active"""
        return self.status.is_active()
    
    def is_terminal(self) -> bool:
        """Check if order is in terminal state"""
        return self.status.is_terminal()
    
    # Calculation methods
    
    def calculate_value(self) -> Money:
        """
        Calculate total order value
        
        Returns:
            Total value of the order
            
        Raises:
            ValueError: If price is not set
        """
        price = self.executed_price if self.executed_price else self.price
        
        if not price:
            raise ValueError("Cannot calculate value: price not set")
        
        return price * self.quantity
    
    def calculate_executed_value(self) -> Money:
        """
        Calculate value of executed portion
        
        Returns:
            Value of executed quantity
            
        Raises:
            ValueError: If order is not executed
        """
        if not self.executed_price:
            raise ValueError("Cannot calculate executed value: order not executed")
        
        return self.executed_price * self.executed_quantity
    
    def get_remaining_quantity(self) -> int:
        """Get quantity remaining to be executed"""
        return self.quantity - self.executed_quantity
    
    def get_fill_percentage(self) -> float:
        """Get percentage of order filled"""
        if self.quantity == 0:
            return 0.0
        return (self.executed_quantity / self.quantity) * 100.0
    
    # Display methods
    
    def __str__(self) -> str:
        """Human-readable string representation"""
        direction = "BUY" if self.is_buy_order() else "SELL"
        price_str = str(self.price) if self.price else "MKT"
        status_str = self.status.value
        
        return f"Order({direction} {self.quantity} {self.symbol} @ {price_str} [{status_str}])"
    
    def __repr__(self) -> str:
        """Developer representation"""
        return (
            f"Order(symbol='{self.symbol}', quantity={self.quantity}, "
            f"order_type={self.order_type}, transaction_type={self.transaction_type}, "
            f"status={self.status}, order_id='{self.order_id}')"
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "order_type": self.order_type.value,
            "transaction_type": self.transaction_type.value,
            "price": str(self.price) if self.price else None,
            "product_type": self.product_type.value,
            "variety": self.variety.value,
            "exchange": self.exchange.value,
            "validity": self.validity,
            "order_id": self.order_id,
            "status": self.status.value,
            "placed_at": self.placed_at.isoformat() if self.placed_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "executed_price": str(self.executed_price) if self.executed_price else None,
            "executed_quantity": self.executed_quantity,
            "remarks": self.remarks,
            "created_at": self.created_at.isoformat(),
        }
