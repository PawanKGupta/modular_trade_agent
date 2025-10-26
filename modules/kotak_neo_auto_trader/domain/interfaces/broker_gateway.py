"""
Broker Gateway Interface
Defines contract for broker API interactions
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from ..entities import Order, Holding


class IBrokerGateway(ABC):
    """
    Interface for broker API interactions
    
    This interface decouples domain logic from specific broker implementations,
    allowing us to swap brokers or use mocks for testing.
    """
    
    # Connection Management
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to broker
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """
        Disconnect from broker
        
        Returns:
            True if disconnection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if currently connected to broker
        
        Returns:
            True if connected, False otherwise
        """
        pass
    
    # Order Management
    
    @abstractmethod
    def place_order(self, order: Order) -> str:
        """
        Place an order with the broker
        
        Args:
            order: Order entity to place
            
        Returns:
            Broker-assigned order ID
            
        Raises:
            ConnectionError: If not connected to broker
            ValueError: If order validation fails
            RuntimeError: If order placement fails
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order
        
        Args:
            order_id: Broker order ID to cancel
            
        Returns:
            True if cancellation successful, False otherwise
            
        Raises:
            ConnectionError: If not connected to broker
            ValueError: If order_id is invalid
        """
        pass
    
    @abstractmethod
    def get_order(self, order_id: str) -> Optional[Order]:
        """
        Get order details by ID
        
        Args:
            order_id: Broker order ID
            
        Returns:
            Order entity if found, None otherwise
            
        Raises:
            ConnectionError: If not connected to broker
        """
        pass
    
    @abstractmethod
    def get_all_orders(self) -> List[Order]:
        """
        Get all orders
        
        Returns:
            List of all orders
            
        Raises:
            ConnectionError: If not connected to broker
        """
        pass
    
    @abstractmethod
    def get_pending_orders(self) -> List[Order]:
        """
        Get all pending/open orders
        
        Returns:
            List of pending orders
            
        Raises:
            ConnectionError: If not connected to broker
        """
        pass
    
    # Portfolio Management
    
    @abstractmethod
    def get_holdings(self) -> List[Holding]:
        """
        Get portfolio holdings
        
        Returns:
            List of holdings
            
        Raises:
            ConnectionError: If not connected to broker
        """
        pass
    
    @abstractmethod
    def get_holding(self, symbol: str) -> Optional[Holding]:
        """
        Get holding for specific symbol
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Holding entity if found, None otherwise
            
        Raises:
            ConnectionError: If not connected to broker
        """
        pass
    
    # Account Management
    
    @abstractmethod
    def get_account_limits(self) -> Dict[str, Any]:
        """
        Get account limits and margins
        
        Returns:
            Dictionary containing account limits:
            {
                'available_cash': Money,
                'margin_used': Money,
                'margin_available': Money,
                'collateral': Money
            }
            
        Raises:
            ConnectionError: If not connected to broker
        """
        pass
    
    @abstractmethod
    def get_available_balance(self) -> 'Money':
        """
        Get available cash balance
        
        Returns:
            Available cash balance
            
        Raises:
            ConnectionError: If not connected to broker
        """
        pass
    
    # Utility Methods
    
    @abstractmethod
    def search_orders_by_symbol(self, symbol: str) -> List[Order]:
        """
        Search orders by symbol
        
        Args:
            symbol: Stock symbol to search
            
        Returns:
            List of orders for the symbol
            
        Raises:
            ConnectionError: If not connected to broker
        """
        pass
    
    @abstractmethod
    def cancel_pending_buys_for_symbol(self, symbol: str) -> int:
        """
        Cancel all pending BUY orders for a symbol
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Number of orders cancelled
            
        Raises:
            ConnectionError: If not connected to broker
        """
        pass
