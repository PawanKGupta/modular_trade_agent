#!/usr/bin/env python3
"""
Unified Order State Manager
Consolidates order state management across multiple storage systems.

Provides single source of truth for:
- Active sell orders (in-memory)
- Pending orders (OrderTracker)
- Trade history (storage.trades_history.json)
- Failed orders (storage.trades_history.json)
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import threading

from utils.logger import logger

try:
    from .order_tracker import OrderTracker
    from .storage import (
        load_history, save_history, mark_position_closed,
        add_failed_order, cleanup_expired_failed_orders
    )
    from .utils.order_field_extractor import OrderFieldExtractor
    from .utils.order_status_parser import OrderStatusParser
    from .utils.symbol_utils import extract_base_symbol
    from .domain.value_objects.order_enums import OrderStatus
except ImportError:
    from modules.kotak_neo_auto_trader.order_tracker import OrderTracker
    from modules.kotak_neo_auto_trader.storage import (
        load_history, save_history, mark_position_closed,
        add_failed_order, cleanup_expired_failed_orders
    )
    from modules.kotak_neo_auto_trader.utils.order_field_extractor import OrderFieldExtractor
    from modules.kotak_neo_auto_trader.utils.order_status_parser import OrderStatusParser
    from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_base_symbol
    from modules.kotak_neo_auto_trader.domain.value_objects.order_enums import OrderStatus


class OrderStateManager:
    """
    Unified order state management providing single source of truth.
    
    Consolidates:
    - active_sell_orders (in-memory cache)
    - pending_orders (OrderTracker JSON)
    - trades (trades_history.json)
    - failed_orders (trades_history.json)
    
    Provides atomic updates across all state sources.
    """
    
    def __init__(self, history_path: str, data_dir: str = "data"):
        """
        Initialize order state manager.
        
        Args:
            history_path: Path to trades_history.json
            data_dir: Directory for OrderTracker data
        """
        self.history_path = history_path
        self.data_dir = data_dir
        
        # In-memory cache for active sell orders
        # Format: {symbol: {'order_id': str, 'target_price': float, 'qty': int, ...}}
        self.active_sell_orders: Dict[str, Dict[str, Any]] = {}
        
        # Order tracker for pending orders
        self._order_tracker = OrderTracker(data_dir=data_dir)
        
        # Thread lock for atomic operations
        self._lock = threading.Lock()
        
        logger.info(f"OrderStateManager initialized (history: {history_path}, data_dir: {data_dir})")
    
    def register_sell_order(
        self,
        symbol: str,
        order_id: str,
        target_price: float,
        qty: int,
        ticker: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        Register new sell order with atomic updates to all state sources.
        
        Args:
            symbol: Trading symbol (e.g., 'RELIANCE')
            order_id: Order ID from broker
            target_price: Target sell price
            qty: Order quantity
            ticker: Full ticker symbol (e.g., 'RELIANCE.NS')
            **kwargs: Additional order metadata
            
        Returns:
            True if successfully registered, False otherwise
        """
        with self._lock:
            try:
                base_symbol = extract_base_symbol(symbol).upper()
                
                # Check if order already exists in active_sell_orders
                existing_order = self.active_sell_orders.get(base_symbol)
                if existing_order and existing_order.get('order_id') == order_id:
                    # Order already registered - check if price needs updating
                    existing_price = existing_order.get('target_price', 0)
                    if existing_price != target_price and target_price > 0:
                        # Price changed - update it
                        logger.debug(
                            f"Order {order_id} already registered for {base_symbol}. "
                            f"Updating price from ₹{existing_price:.2f} to ₹{target_price:.2f}"
                        )
                        self.active_sell_orders[base_symbol]['target_price'] = target_price
                        self.active_sell_orders[base_symbol]['last_updated'] = datetime.now().isoformat()
                        return True  # Return True after updating price
                    else:
                        # Order already registered with same or better price - skip duplicate registration
                        logger.debug(
                            f"Order {order_id} already registered for {base_symbol}. "
                            f"Existing price: ₹{existing_price:.2f}, New price: ₹{target_price:.2f}. "
                            f"Skipping duplicate registration."
                        )
                        return True  # Return True since order is already tracked
                
                # 1. Update in-memory cache
                self.active_sell_orders[base_symbol] = {
                    'order_id': order_id,
                    'target_price': target_price,
                    'qty': qty,
                    'symbol': symbol,
                    'ticker': ticker,
                    'registered_at': datetime.now().isoformat(),
                    **kwargs
                }
                
                # 2. Add to pending orders tracker (will skip if duplicate due to fix in add_pending_order)
                if ticker:
                    self._order_tracker.add_pending_order(
                        order_id=order_id,
                        symbol=symbol,
                        ticker=ticker,
                        qty=qty,
                        order_type="LIMIT",
                        variety="REGULAR",
                        price=target_price
                    )
                
                logger.info(
                    f"Registered sell order: {base_symbol} "
                    f"(order_id: {order_id}, price: ₹{target_price:.2f}, qty: {qty})"
                )
                
                return True
                
            except Exception as e:
                logger.error(f"Error registering sell order {order_id}: {e}")
                return False
    
    def mark_order_executed(
        self,
        symbol: str,
        order_id: str,
        execution_price: float,
        execution_qty: Optional[int] = None
    ) -> bool:
        """
        Mark order as executed with atomic updates to all state sources.
        
        Args:
            symbol: Trading symbol
            order_id: Order ID
            execution_price: Price at which order executed
            execution_qty: Quantity executed (defaults to full qty)
            
        Returns:
            True if successfully updated, False otherwise
        """
        with self._lock:
            try:
                base_symbol = extract_base_symbol(symbol).upper()
                
                # Get order info before removing
                order_info = self.active_sell_orders.get(base_symbol, {})
                execution_qty = execution_qty or order_info.get('qty', 0)
                
                # 1. Remove from active tracking
                if base_symbol in self.active_sell_orders:
                    del self.active_sell_orders[base_symbol]
                
                # 2. Update order tracker status
                self._order_tracker.update_order_status(
                    order_id=order_id,
                    status='EXECUTED',
                    executed_qty=execution_qty
                )
                
                # 3. Update trade history
                mark_position_closed(
                    history_path=self.history_path,
                    symbol=base_symbol,
                    exit_price=execution_price,
                    sell_order_id=order_id
                )
                
                logger.info(
                    f"Marked order as executed: {base_symbol} "
                    f"(order_id: {order_id}, price: ₹{execution_price:.2f}, qty: {execution_qty})"
                )
                
                return True
                
            except Exception as e:
                logger.error(f"Error marking order {order_id} as executed: {e}")
                return False
    
    def update_sell_order_price(
        self,
        symbol: str,
        new_price: float
    ) -> bool:
        """
        Update target price for an active sell order.
        
        Args:
            symbol: Trading symbol
            new_price: New target price
            
        Returns:
            True if updated, False if order not found
        """
        with self._lock:
            base_symbol = extract_base_symbol(symbol).upper()
            
            if base_symbol in self.active_sell_orders:
                self.active_sell_orders[base_symbol]['target_price'] = new_price
                self.active_sell_orders[base_symbol]['last_updated'] = datetime.now().isoformat()
                logger.debug(f"Updated sell order price: {base_symbol} → ₹{new_price:.2f}")
                return True
            
            return False
    
    def remove_from_tracking(
        self,
        symbol: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Remove order from active tracking (e.g., rejected, cancelled).
        
        Args:
            symbol: Trading symbol
            reason: Reason for removal (optional)
            
        Returns:
            True if removed, False if not found
        """
        with self._lock:
            base_symbol = extract_base_symbol(symbol).upper()
            
            if base_symbol in self.active_sell_orders:
                order_info = self.active_sell_orders[base_symbol]
                order_id = order_info.get('order_id')
                
                # Remove from active tracking
                del self.active_sell_orders[base_symbol]
                
                # Update order tracker if order_id exists
                if order_id:
                    self._order_tracker.update_order_status(
                        order_id=order_id,
                        status='CANCELLED'
                    )
                
                logger.info(
                    f"Removed order from tracking: {base_symbol} "
                    f"(reason: {reason or 'unknown'})"
                )
                
                return True
            
            return False
    
    def get_active_sell_orders(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all active sell orders.
        
        Returns:
            Dict of active sell orders {symbol: order_info}
        """
        with self._lock:
            return self.active_sell_orders.copy()
    
    def get_active_order(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get active sell order for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Order info dict or None if not found
        """
        base_symbol = extract_base_symbol(symbol).upper()
        return self.active_sell_orders.get(base_symbol)
    
    def sync_with_broker(
        self,
        orders_api,
        broker_orders: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, int]:
        """
        Sync state with broker to detect manual orders and status changes.
        
        Args:
            orders_api: Orders API client (with get_orders method)
            broker_orders: Optional pre-fetched broker orders list
            
        Returns:
            Stats dict with sync results
        """
        stats = {
            'checked': 0,
            'executed': 0,
            'rejected': 0,
            'cancelled': 0,
            'manual_sells': 0
        }
        
        try:
            # Fetch broker orders if not provided
            if broker_orders is None:
                orders_response = orders_api.get_orders() if orders_api else None
                broker_orders = orders_response.get('data', []) if orders_response else []
            
            # Check each active sell order
            active_symbols = list(self.active_sell_orders.keys())
            
            for symbol in active_symbols:
                order_info = self.active_sell_orders.get(symbol)
                if not order_info:
                    continue
                
                order_id = order_info.get('order_id')
                if not order_id:
                    continue
                
                stats['checked'] += 1
                
                # Find order in broker orders
                broker_order = None
                for bo in broker_orders:
                    broker_order_id = OrderFieldExtractor.get_order_id(bo)
                    if broker_order_id == order_id:
                        broker_order = bo
                        break
                
                if broker_order:
                    # Check status
                    status = OrderStatusParser.parse_status(broker_order)
                    
                    if status in {OrderStatus.COMPLETE, OrderStatus.EXECUTED}:
                        # Order executed
                        execution_price = OrderFieldExtractor.get_price(broker_order) or order_info.get('target_price', 0)
                        execution_qty = OrderFieldExtractor.get_quantity(broker_order) or order_info.get('qty', 0)
                        
                        self.mark_order_executed(symbol, order_id, execution_price, execution_qty)
                        stats['executed'] += 1
                        
                    elif status == OrderStatus.REJECTED:
                        # Order rejected
                        rejection_reason = broker_order.get('rejectionReason') or 'Unknown'
                        self.remove_from_tracking(symbol, reason=f"Rejected: {rejection_reason}")
                        stats['rejected'] += 1
                        
                    elif status == OrderStatus.CANCELLED:
                        # Order cancelled
                        self.remove_from_tracking(symbol, reason="Cancelled")
                        stats['cancelled'] += 1
                
                else:
                    # Order not found in broker orders - might be executed
                    # Check if symbol has any executed orders
                    executed_orders = [
                        bo for bo in broker_orders
                        if OrderFieldExtractor.get_symbol(bo).upper().startswith(symbol.upper())
                        and OrderStatusParser.is_completed(bo)
                        and OrderFieldExtractor.is_sell_order(bo)
                    ]
                    
                    if executed_orders:
                        # Manual sell detected
                        logger.warning(f"Manual sell detected for {symbol}")
                        stats['manual_sells'] += 1
                        # Handle manual sell (could mark as executed)
                        # This is a placeholder - actual handling depends on requirements
                        self.remove_from_tracking(symbol, reason="Manual sell detected")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error syncing with broker: {e}")
            return stats
    
    def get_pending_orders(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get pending orders from OrderTracker.
        
        Args:
            status_filter: Optional status filter (PENDING/OPEN/EXECUTED/etc.)
            
        Returns:
            List of pending order dicts
        """
        return self._order_tracker.get_pending_orders(status_filter=status_filter)
    
    def cleanup_expired_failed_orders(self) -> int:
        """
        Clean up expired failed orders from trade history.
        
        Returns:
            Number of orders removed
        """
        return cleanup_expired_failed_orders(self.history_path)
    
    def get_trade_history(self) -> Dict[str, Any]:
        """
        Get full trade history.
        
        Returns:
            Trade history dict
        """
        return load_history(self.history_path)
    
    def reload_state(self):
        """
        Reload state from storage (useful after external changes).
        
        Note: This does not reload active_sell_orders from broker.
        Use sync_with_broker() for that.
        """
        # OrderTracker automatically loads from file
        # Trade history is loaded on-demand
        logger.debug("State reloaded from storage")
