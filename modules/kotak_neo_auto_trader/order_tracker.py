#!/usr/bin/env python3
"""
Order Tracker Module
Manages pending orders and tracks their status lifecycle.

SOLID Principles:
- Single Responsibility: Only manages order tracking and status
- Interface Segregation: Clean API for order operations
- Dependency Inversion: Abstract order status checking
"""

import os
import json
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

# Use existing project logger
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger


class OrderTracker:
    """
    Tracks pending orders from placement to execution/rejection.
    Maintains order status and provides status verification.
    """
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize order tracker.
        
        Args:
            data_dir: Directory for storing pending orders data
        """
        self.data_dir = data_dir
        self.pending_file = os.path.join(data_dir, "pending_orders.json")
        self._ensure_data_file()
    
    def _ensure_data_file(self) -> None:
        """Create pending orders file if it doesn't exist."""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
        
        if not os.path.exists(self.pending_file):
            self._save_pending_data({"orders": []})
    
    def _load_pending_data(self) -> Dict[str, Any]:
        """Load pending orders from file."""
        try:
            with open(self.pending_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load pending orders: {e}")
            return {"orders": []}
    
    def _save_pending_data(self, data: Dict[str, Any]) -> None:
        """Save pending orders to file."""
        try:
            with open(self.pending_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save pending orders: {e}")
    
    @staticmethod
    def extract_order_id(response: Dict[str, Any]) -> Optional[str]:
        """
        Extract order ID from broker response.
        
        Handles multiple response formats from Kotak Neo API:
        - {'data': {'neoOrdNo': 'ORDER-123'}}
        - {'neoOrdNo': 'ORDER-123'}
        - {'orderId': 'ORDER-123'}
        
        Args:
            response: Response dict from broker API
        
        Returns:
            Order ID string or None if not found
        """
        if not isinstance(response, dict):
            return None
        
        # Try data field first
        data = response.get('data', response)
        
        # Try common field names
        order_id = (
            data.get('neoOrdNo') or
            data.get('orderId') or
            data.get('order_id') or
            data.get('OrdId') or
            data.get('ordId')
        )
        
        if order_id:
            logger.debug(f"Extracted order ID: {order_id}")
            return str(order_id)
        
        logger.warning("Could not extract order ID from response")
        return None
    
    def add_pending_order(
        self,
        order_id: str,
        symbol: str,
        ticker: str,
        qty: int,
        order_type: str = "MARKET",
        variety: str = "AMO",
        price: float = 0.0
    ) -> None:
        """
        Add order to pending tracking.
        
        Args:
            order_id: Order ID from broker
            symbol: Trading symbol
            ticker: Full ticker symbol
            qty: Order quantity
            order_type: MARKET/LIMIT
            variety: AMO/REGULAR
            price: Limit price (0 for market orders)
        """
        data = self._load_pending_data()
        
        pending_order = {
            "order_id": order_id,
            "symbol": symbol,
            "ticker": ticker,
            "qty": qty,
            "order_type": order_type,
            "variety": variety,
            "price": price,
            "placed_at": datetime.now().isoformat(),
            "last_status_check": datetime.now().isoformat(),
            "status": "PENDING",
            "rejection_reason": None,
            "check_count": 0,
            "executed_qty": 0
        }
        
        data["orders"].append(pending_order)
        self._save_pending_data(data)
        
        logger.info(
            f"Added to pending orders: {symbol} "
            f"(order_id: {order_id}, qty: {qty})"
        )
    
    def get_pending_orders(
        self,
        status_filter: Optional[str] = None,
        symbol_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get list of pending orders with optional filters.
        
        Args:
            status_filter: Filter by status (PENDING/OPEN/PARTIALLY_FILLED)
            symbol_filter: Filter by symbol
        
        Returns:
            List of pending order dicts
        """
        data = self._load_pending_data()
        orders = data["orders"]
        
        # Apply filters
        if status_filter:
            orders = [o for o in orders if o["status"] == status_filter]
        
        if symbol_filter:
            orders = [o for o in orders if o["symbol"] == symbol_filter]
        
        return orders
    
    def update_order_status(
        self,
        order_id: str,
        status: str,
        executed_qty: Optional[int] = None,
        rejection_reason: Optional[str] = None
    ) -> bool:
        """
        Update status of a pending order.
        
        Args:
            order_id: Order ID to update
            status: New status (PENDING/OPEN/EXECUTED/REJECTED/CANCELLED/PARTIALLY_FILLED)
            executed_qty: Quantity executed (for partial fills)
            rejection_reason: Reason if rejected
        
        Returns:
            True if order found and updated, False otherwise
        """
        data = self._load_pending_data()
        
        for order in data["orders"]:
            if order["order_id"] == order_id:
                old_status = order["status"]
                order["status"] = status
                order["last_status_check"] = datetime.now().isoformat()
                order["check_count"] = order.get("check_count", 0) + 1
                
                if executed_qty is not None:
                    order["executed_qty"] = executed_qty
                
                if rejection_reason:
                    order["rejection_reason"] = rejection_reason
                
                self._save_pending_data(data)
                
                logger.info(
                    f"Updated order status: {order_id} "
                    f"{old_status} -> {status}"
                )
                
                return True
        
        logger.warning(f"Order {order_id} not found in pending orders")
        return False
    
    def remove_pending_order(self, order_id: str) -> bool:
        """
        Remove order from pending tracking.
        
        Args:
            order_id: Order ID to remove
        
        Returns:
            True if order found and removed, False otherwise
        """
        data = self._load_pending_data()
        
        original_count = len(data["orders"])
        data["orders"] = [o for o in data["orders"] if o["order_id"] != order_id]
        
        if len(data["orders"]) < original_count:
            self._save_pending_data(data)
            logger.info(f"Removed order from pending: {order_id}")
            return True
        
        logger.warning(f"Order {order_id} not found in pending orders")
        return False
    
    def get_order_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get pending order by order ID.
        
        Args:
            order_id: Order ID to find
        
        Returns:
            Order dict or None if not found
        """
        data = self._load_pending_data()
        
        for order in data["orders"]:
            if order["order_id"] == order_id:
                return order
        
        return None
    
    def search_order_in_broker_orderbook(
        self,
        orders_api_client,
        symbol: str,
        qty: int,
        after_timestamp: str,
        max_wait_seconds: int = 60
    ) -> Optional[str]:
        """
        Search for order in broker's order book when order_id not received.
        Implements 60-second fallback logic.
        
        Args:
            orders_api_client: Orders API client (with get_orders method)
            symbol: Trading symbol to search for
            qty: Expected quantity
            after_timestamp: Only consider orders after this time
            max_wait_seconds: Maximum seconds to wait (default 60)
        
        Returns:
            Order ID if found, None otherwise
        """
        logger.info(
            f"Searching order book for {symbol} (qty: {qty}) - "
            f"waiting up to {max_wait_seconds}s"
        )
        
        time.sleep(max_wait_seconds)  # Wait for broker to process
        
        try:
            # Get all orders from broker
            orders_response = orders_api_client.get_orders()
            
            if not orders_response or 'data' not in orders_response:
                logger.warning("Failed to fetch orders from broker")
                return None
            
            # Parse after_timestamp
            try:
                after_time = datetime.fromisoformat(after_timestamp)
            except Exception:
                after_time = datetime.now()
            
            # Search for matching order
            for order in orders_response['data']:
                order_symbol = str(order.get('tradingSymbol', '')).upper()
                order_qty = int(order.get('quantity', 0))
                
                # Parse order time
                order_time_str = order.get('orderEntryTime') or order.get('timestamp')
                if order_time_str:
                    try:
                        order_time = datetime.fromisoformat(order_time_str)
                        if order_time < after_time:
                            continue  # Too old
                    except Exception:
                        pass
                
                # Check if match
                if symbol.upper() in order_symbol and order_qty == qty:
                    found_order_id = (
                        order.get('neoOrdNo') or
                        order.get('orderId') or
                        order.get('order_id')
                    )
                    
                    if found_order_id:
                        logger.info(
                            f"Found order in broker order book: "
                            f"{found_order_id} for {symbol}"
                        )
                        return str(found_order_id)
            
            logger.warning(
                f"Order not found in broker order book: {symbol} x{qty}"
            )
            return None
            
        except Exception as e:
            logger.error(f"Error searching order book: {e}")
            return None


# Singleton instance
_order_tracker_instance: Optional[OrderTracker] = None


def get_order_tracker(data_dir: str = "data") -> OrderTracker:
    """
    Get or create order tracker singleton instance.
    
    Args:
        data_dir: Directory for pending orders data
    
    Returns:
        OrderTracker instance
    """
    global _order_tracker_instance
    
    if _order_tracker_instance is None:
        _order_tracker_instance = OrderTracker(data_dir)
    
    return _order_tracker_instance


# Convenience functions
def extract_order_id(response: Dict[str, Any]) -> Optional[str]:
    """Extract order ID from broker response."""
    return OrderTracker.extract_order_id(response)


def add_pending_order(*args, **kwargs) -> None:
    """Add order to pending tracking."""
    return get_order_tracker().add_pending_order(*args, **kwargs)


def get_pending_orders(**kwargs) -> List[Dict[str, Any]]:
    """Get list of pending orders."""
    return get_order_tracker().get_pending_orders(**kwargs)


def update_order_status(*args, **kwargs) -> bool:
    """Update order status."""
    return get_order_tracker().update_order_status(*args, **kwargs)


def remove_pending_order(order_id: str) -> bool:
    """Remove order from pending."""
    return get_order_tracker().remove_pending_order(order_id)


def get_order_by_id(order_id: str) -> Optional[Dict[str, Any]]:
    """Get order by ID."""
    return get_order_tracker().get_order_by_id(order_id)


def search_order_in_broker_orderbook(*args, **kwargs) -> Optional[str]:
    """Search for order in broker order book."""
    return get_order_tracker().search_order_in_broker_orderbook(*args, **kwargs)
