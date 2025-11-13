#!/usr/bin/env python3
"""
Order Status Parser Utility
Centralized order status parsing with consistent logic
"""

from typing import Dict, Any, Optional

try:
    from ..domain.value_objects.order_enums import OrderStatus
except ImportError:
    # Fallback if relative import fails
    import sys
    from pathlib import Path
    project_root = Path(__file__).parent.parent.parent.parent
    sys.path.insert(0, str(project_root))
    from modules.kotak_neo_auto_trader.domain.value_objects.order_enums import OrderStatus


class OrderStatusParser:
    """
    Centralized order status parsing.
    
    Handles inconsistent broker API status values by:
    1. Trying OrderStatus enum conversion first
    2. Falling back to keyword matching
    3. Providing helper methods for common checks
    """
    
    # Status keywords mapping to OrderStatus enum
    STATUS_KEYWORDS = {
        'complete': OrderStatus.COMPLETE,
        'executed': OrderStatus.EXECUTED,
        'filled': OrderStatus.COMPLETE,  # Fixed: from_string maps FILLED to COMPLETE
        'done': OrderStatus.COMPLETE,
        'rejected': OrderStatus.REJECTED,
        'cancelled': OrderStatus.CANCELLED,
        'canceled': OrderStatus.CANCELLED,
        'open': OrderStatus.OPEN,
        'pending': OrderStatus.PENDING,
        'partial': OrderStatus.PARTIALLY_FILLED,
        'partially': OrderStatus.PARTIALLY_FILLED,
        'trigger pending': OrderStatus.TRIGGER_PENDING,
        'after market order req received': OrderStatus.PENDING,
    }
    
    @classmethod
    def parse_status(cls, order: Dict[str, Any]) -> OrderStatus:
        """
        Parse order status from order dict.
        
        Args:
            order: Order dict from broker API
            
        Returns:
            OrderStatus enum value
        """
        # Extract status string with fallbacks
        status_str = (
            order.get('orderStatus') or 
            order.get('ordSt') or 
            order.get('status') or 
            ''
        ).lower().strip()
        
        if not status_str:
            return OrderStatus.PENDING
        
        # Check if it's a single-word exact match (use enum conversion)
        # Multi-word phrases like "order complete" should use keyword matching
        words = status_str.split()
        is_single_word = len(words) == 1
        
        if is_single_word:
            # Try direct enum conversion for single words
            try:
                result = OrderStatus.from_string(status_str)
                # Only return if it's not the default PENDING (unless input was exactly "pending")
                if result != OrderStatus.PENDING or status_str == 'pending':
                    return result
            except (ValueError, AttributeError):
                pass
        
        # Fallback to keyword matching for phrases or unmatched single words
        # Sort keywords by length (longest first) to match more specific phrases first
        for keyword, status in sorted(cls.STATUS_KEYWORDS.items(), key=lambda x: len(x[0]), reverse=True):
            if keyword in status_str:
                return status
        
        # Default to PENDING if no match
        return OrderStatus.PENDING
    
    @classmethod
    def is_completed(cls, order: Dict[str, Any]) -> bool:
        """
        Check if order is completed/executed.
        
        Args:
            order: Order dict from broker API
            
        Returns:
            True if order is completed/executed, False otherwise
        """
        status = cls.parse_status(order)
        return status in {OrderStatus.COMPLETE, OrderStatus.EXECUTED}
    
    @classmethod
    def is_active(cls, order: Dict[str, Any]) -> bool:
        """
        Check if order is still active (not terminal).
        
        Args:
            order: Order dict from broker API
            
        Returns:
            True if order is active, False if terminal
        """
        status = cls.parse_status(order)
        return status.is_active()
    
    @classmethod
    def is_terminal(cls, order: Dict[str, Any]) -> bool:
        """
        Check if order is in terminal state (executed, rejected, cancelled).
        
        Args:
            order: Order dict from broker API
            
        Returns:
            True if order is terminal, False otherwise
        """
        status = cls.parse_status(order)
        return status.is_terminal()
    
    @classmethod
    def is_rejected(cls, order: Dict[str, Any]) -> bool:
        """
        Check if order is rejected.
        
        Args:
            order: Order dict from broker API
            
        Returns:
            True if order is rejected, False otherwise
        """
        status = cls.parse_status(order)
        return status == OrderStatus.REJECTED
    
    @classmethod
    def is_cancelled(cls, order: Dict[str, Any]) -> bool:
        """
        Check if order is cancelled.
        
        Args:
            order: Order dict from broker API
            
        Returns:
            True if order is cancelled, False otherwise
        """
        status = cls.parse_status(order)
        return status == OrderStatus.CANCELLED
    
    @classmethod
    def is_pending(cls, order: Dict[str, Any]) -> bool:
        """
        Check if order is pending.
        
        Args:
            order: Order dict from broker API
            
        Returns:
            True if order is pending, False otherwise
        """
        status = cls.parse_status(order)
        return status == OrderStatus.PENDING
    
    @classmethod
    def parse_status_from_string(cls, status_str: str) -> OrderStatus:
        """
        Parse status from string directly (without order dict).
        
        Args:
            status_str: Status string
            
        Returns:
            OrderStatus enum value
        """
        if not status_str:
            return OrderStatus.PENDING
        
        status_str = status_str.lower().strip()
        
        # Try direct enum conversion
        try:
            return OrderStatus.from_string(status_str)
        except (ValueError, AttributeError):
            pass
        
        # Fallback to keyword matching
        for keyword, status in cls.STATUS_KEYWORDS.items():
            if keyword in status_str:
                return status
        
        return OrderStatus.PENDING

