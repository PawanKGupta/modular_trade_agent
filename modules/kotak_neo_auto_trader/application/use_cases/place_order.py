"""
Place Order Use Case
Business logic for placing orders with broker
"""

from dataclasses import dataclass
from ...domain import Order, IBrokerGateway
from ..dto import OrderRequest, OrderResponse


@dataclass
class PlaceOrderUseCase:
    """
    Use case for placing an order
    
    Handles validation, order creation, and broker interaction
    """
    
    broker_gateway: IBrokerGateway
    
    def execute(self, request: OrderRequest) -> OrderResponse:
        """
        Execute the place order use case
        
        Args:
            request: OrderRequest DTO with order details
            
        Returns:
            OrderResponse with result
        """
        # 1. Validate request
        is_valid, errors = request.validate()
        if not is_valid:
            return OrderResponse.failure_response(
                errors=errors,
                message="Order validation failed"
            )
        
        # 2. Check broker connection
        if not self.broker_gateway.is_connected():
            if not self.broker_gateway.connect():
                return OrderResponse.failure_response(
                    errors=["Failed to connect to broker"],
                    message="Broker connection failed"
                )
        
        # 3. Create domain entity from request
        try:
            order = Order(
                symbol=request.symbol,
                quantity=request.quantity,
                order_type=request.order_type,
                transaction_type=request.transaction_type,
                price=request.price,
                product_type=request.product_type,
                variety=request.variety,
                exchange=request.exchange,
                validity=request.validity,
                remarks=request.remarks
            )
        except ValueError as e:
            return OrderResponse.failure_response(
                errors=[str(e)],
                message="Failed to create order"
            )
        
        # 4. Place order via broker gateway
        try:
            order_id = self.broker_gateway.place_order(order)
            
            # Broker gateway has already updated the order entity
            # Just return the response
            return OrderResponse.success_response(
                order_id=order_id,
                order=order,
                message=f"Order placed successfully: {order_id}"
            )
            
        except ConnectionError as e:
            return OrderResponse.failure_response(
                errors=[f"Connection error: {str(e)}"],
                message="Failed to connect to broker"
            )
        except ValueError as e:
            return OrderResponse.failure_response(
                errors=[f"Validation error: {str(e)}"],
                message="Order rejected by broker"
            )
        except Exception as e:
            return OrderResponse.failure_response(
                errors=[f"Unexpected error: {str(e)}"],
                message="Order placement failed"
            )
