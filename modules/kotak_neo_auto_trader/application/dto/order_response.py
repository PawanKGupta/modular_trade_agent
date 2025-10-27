"""
Order Response DTO
Data Transfer Object for order placement responses
"""

from dataclasses import dataclass, field
from typing import Optional, List
from ...domain import Order


@dataclass
class OrderResponse:
    """
    DTO for order placement response
    
    Used to transfer order placement results from application to presentation layer
    """
    
    success: bool
    order_id: Optional[str] = None
    order: Optional[Order] = None
    errors: List[str] = field(default_factory=list)
    message: str = ""
    
    @classmethod
    def success_response(cls, order_id: str, order: Order, message: str = "Order placed successfully") -> 'OrderResponse':
        """
        Create success response
        
        Args:
            order_id: Broker-assigned order ID
            order: Order entity
            message: Success message
            
        Returns:
            OrderResponse indicating success
        """
        return cls(
            success=True,
            order_id=order_id,
            order=order,
            message=message
        )
    
    @classmethod
    def failure_response(cls, errors: List[str], message: str = "Order placement failed") -> 'OrderResponse':
        """
        Create failure response
        
        Args:
            errors: List of error messages
            message: Failure message
            
        Returns:
            OrderResponse indicating failure
        """
        return cls(
            success=False,
            errors=errors,
            message=message
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "order_id": self.order_id,
            "order": self.order.to_dict() if self.order else None,
            "errors": self.errors,
            "message": self.message,
        }


@dataclass
class HoldingsResponse:
    """
    DTO for holdings retrieval response
    """
    
    success: bool
    holdings: List = field(default_factory=list)  # List[Holding]
    total_value: Optional['Money'] = None
    total_pnl: Optional['Money'] = None
    errors: List[str] = field(default_factory=list)
    message: str = ""
    
    @classmethod
    def success_response(cls, holdings: List, total_value: 'Money', total_pnl: 'Money') -> 'HoldingsResponse':
        """Create success response"""
        return cls(
            success=True,
            holdings=holdings,
            total_value=total_value,
            total_pnl=total_pnl,
            message=f"Retrieved {len(holdings)} holdings"
        )
    
    @classmethod
    def failure_response(cls, errors: List[str]) -> 'HoldingsResponse':
        """Create failure response"""
        return cls(
            success=False,
            errors=errors,
            message="Failed to retrieve holdings"
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "holdings": [h.to_dict() for h in self.holdings],
            "total_value": str(self.total_value) if self.total_value else None,
            "total_pnl": str(self.total_pnl) if self.total_pnl else None,
            "count": len(self.holdings),
            "errors": self.errors,
            "message": self.message,
        }


@dataclass
class StrategyExecutionResult:
    """
    DTO for trading strategy execution result
    """
    
    success: bool
    orders_placed: List[dict] = field(default_factory=list)
    orders_skipped: List[dict] = field(default_factory=list)
    orders_failed: List[dict] = field(default_factory=list)
    message: str = ""
    
    def get_summary(self) -> dict:
        """Get execution summary"""
        return {
            "success": self.success,
            "placed_count": len(self.orders_placed),
            "skipped_count": len(self.orders_skipped),
            "failed_count": len(self.orders_failed),
            "total_processed": len(self.orders_placed) + len(self.orders_skipped) + len(self.orders_failed),
            "message": self.message,
        }
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "orders_placed": self.orders_placed,
            "orders_skipped": self.orders_skipped,
            "orders_failed": self.orders_failed,
            "summary": self.get_summary(),
            "message": self.message,
        }
