"""
Mock Broker Adapter
Test implementation of IBrokerGateway for unit testing
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from ...domain import Order, Holding, Money, IBrokerGateway, OrderStatus


class MockBrokerAdapter(IBrokerGateway):
    """
    Mock broker adapter for testing
    
    Simulates broker behavior without external dependencies
    """
    
    def __init__(self):
        self._connected = False
        self._orders: Dict[str, Order] = {}
        self._holdings: Dict[str, Holding] = {}
        self._order_counter = 1
        self._available_cash = Money.from_int(1000000)  # ₹10 lakh
    
    def connect(self) -> bool:
        self._connected = True
        return True
    
    def disconnect(self) -> bool:
        self._connected = False
        return True
    
    def is_connected(self) -> bool:
        return self._connected
    
    def place_order(self, order: Order) -> str:
        if not self._connected:
            raise ConnectionError("Not connected")
        
        order_id = f"MOCK{self._order_counter:06d}"
        self._order_counter += 1
        
        # Clone order and assign ID
        order.place(order_id)
        self._orders[order_id] = order
        
        return order_id
    
    def cancel_order(self, order_id: str) -> bool:
        if order_id in self._orders:
            self._orders[order_id].cancel()
            return True
        return False
    
    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)
    
    def get_all_orders(self) -> List[Order]:
        return list(self._orders.values())
    
    def get_pending_orders(self) -> List[Order]:
        return [order for order in self._orders.values() if order.is_active()]
    
    def get_holdings(self) -> List[Holding]:
        return list(self._holdings.values())
    
    def get_holding(self, symbol: str) -> Optional[Holding]:
        return self._holdings.get(symbol.upper())
    
    def get_account_limits(self) -> Dict[str, Any]:
        return {
            "available_cash": self._available_cash,
            "margin_used": Money.zero(),
            "margin_available": self._available_cash,
            "collateral": Money.zero()
        }
    
    def get_available_balance(self) -> Money:
        return self._available_cash
    
    def search_orders_by_symbol(self, symbol: str) -> List[Order]:
        return [order for order in self._orders.values() 
                if order.symbol.upper() == symbol.upper()]
    
    def cancel_pending_buys_for_symbol(self, symbol: str) -> int:
        cancelled = 0
        for order in self.get_pending_orders():
            if order.symbol.upper() == symbol.upper() and order.is_buy_order():
                if self.cancel_order(order.order_id):
                    cancelled += 1
        return cancelled
    
    # Test helpers
    
    def add_holding(self, symbol: str, quantity: int, avg_price: float, current_price: float):
        """Add a holding for testing"""
        holding = Holding(
            symbol=symbol,
            quantity=quantity,
            average_price=Money.from_float(avg_price),
            current_price=Money.from_float(current_price),
            last_updated=datetime.now()
        )
        self._holdings[symbol.upper()] = holding
    
    def set_available_cash(self, amount: float):
        """Set available cash for testing"""
        self._available_cash = Money.from_float(amount)
    
    def execute_order(self, order_id: str, execution_price: float):
        """Execute an order for testing"""
        if order_id in self._orders:
            order = self._orders[order_id]
            order.execute(
                Money.from_float(execution_price),
                order.quantity
            )
