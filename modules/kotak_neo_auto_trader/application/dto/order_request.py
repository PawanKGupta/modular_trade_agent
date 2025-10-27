"""
Order Request DTO
Data Transfer Object for order placement requests
"""

from dataclasses import dataclass
from typing import Optional
from ...domain import (
    Money,
    OrderType,
    TransactionType,
    ProductType,
    OrderVariety,
    Exchange
)


@dataclass
class OrderRequest:
    """
    DTO for order placement request
    
    Used to transfer order data from presentation to application layer
    """
    
    # Required fields
    symbol: str
    quantity: int
    order_type: OrderType
    transaction_type: TransactionType
    
    # Optional fields with defaults
    price: Optional[Money] = None
    product_type: ProductType = ProductType.CNC
    variety: OrderVariety = OrderVariety.AMO
    exchange: Exchange = Exchange.NSE
    validity: str = "DAY"
    remarks: str = ""
    
    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate request data
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Symbol validation
        if not self.symbol or len(self.symbol.strip()) == 0:
            errors.append("Symbol is required and cannot be empty")
        elif len(self.symbol) > 50:
            errors.append("Symbol too long (max 50 characters)")
        
        # Quantity validation
        if self.quantity <= 0:
            errors.append(f"Quantity must be positive: {self.quantity}")
        elif self.quantity > 100000:
            errors.append(f"Quantity too large (max 100,000): {self.quantity}")
        
        # Price validation for LIMIT orders
        if self.order_type == OrderType.LIMIT:
            if self.price is None:
                errors.append("Price is required for LIMIT orders")
            elif self.price.amount <= 0:
                errors.append(f"Price must be positive: {self.price}")
        
        # Market orders should not have price
        if self.order_type == OrderType.MARKET and self.price is not None:
            errors.append("Price should not be specified for MARKET orders")
        
        return len(errors) == 0, errors
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
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
            "remarks": self.remarks,
        }
    
    @classmethod
    def market_buy(
        cls,
        symbol: str,
        quantity: int,
        variety: OrderVariety = OrderVariety.AMO,
        product_type: ProductType = ProductType.CNC
    ) -> 'OrderRequest':
        """
        Factory method for market buy order
        
        Args:
            symbol: Stock symbol
            quantity: Number of shares
            variety: Order variety (default AMO)
            product_type: Product type (default CNC)
            
        Returns:
            OrderRequest configured for market buy
        """
        return cls(
            symbol=symbol,
            quantity=quantity,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=variety,
            product_type=product_type
        )
    
    @classmethod
    def limit_buy(
        cls,
        symbol: str,
        quantity: int,
        price: Money,
        variety: OrderVariety = OrderVariety.AMO,
        product_type: ProductType = ProductType.CNC
    ) -> 'OrderRequest':
        """
        Factory method for limit buy order
        
        Args:
            symbol: Stock symbol
            quantity: Number of shares
            price: Limit price
            variety: Order variety (default AMO)
            product_type: Product type (default CNC)
            
        Returns:
            OrderRequest configured for limit buy
        """
        return cls(
            symbol=symbol,
            quantity=quantity,
            price=price,
            order_type=OrderType.LIMIT,
            transaction_type=TransactionType.BUY,
            variety=variety,
            product_type=product_type
        )
