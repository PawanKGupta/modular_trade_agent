#!/usr/bin/env python3
"""
Order Field Extractor Utility
Centralized order field extraction with fallback logic for broker API inconsistencies
"""

from typing import Dict, Any, Optional


class OrderFieldExtractor:
    """
    Centralized order field extraction with fallback logic.
    
    Handles inconsistent broker API field names by trying multiple
    field name variations and returning the first match.
    """
    
    @staticmethod
    def get_order_id(order: Dict[str, Any]) -> str:
        """
        Extract order ID with fallbacks.
        
        Args:
            order: Order dict from broker API
            
        Returns:
            Order ID as string, empty string if not found
        """
        return str(
            order.get('neoOrdNo') or 
            order.get('nOrdNo') or 
            order.get('orderId') or 
            order.get('order_id') or 
            ''
        )
    
    @staticmethod
    def get_symbol(order: Dict[str, Any]) -> str:
        """
        Extract trading symbol with fallbacks.
        
        Args:
            order: Order dict from broker API
            
        Returns:
            Trading symbol (e.g., 'DALBHARAT-EQ'), empty string if not found
        """
        return (
            order.get('trdSym') or 
            order.get('tradingSymbol') or 
            order.get('symbol') or 
            ''
        )
    
    @staticmethod
    def get_transaction_type(order: Dict[str, Any]) -> str:
        """
        Extract transaction type (BUY/SELL) with fallbacks.
        
        Args:
            order: Order dict from broker API
            
        Returns:
            Transaction type uppercase ('BUY' or 'SELL'), empty string if not found
        """
        return (
            order.get('transactionType') or 
            order.get('trnsTp') or 
            order.get('txnType') or 
            ''
        ).upper()
    
    @staticmethod
    def get_status(order: Dict[str, Any]) -> str:
        """
        Extract order status with fallbacks.
        
        Args:
            order: Order dict from broker API
            
        Returns:
            Order status lowercase, empty string if not found
        """
        return (
            order.get('orderStatus') or 
            order.get('ordSt') or 
            order.get('status') or 
            ''
        ).lower()
    
    @staticmethod
    def get_quantity(order: Dict[str, Any]) -> int:
        """
        Extract quantity with fallbacks.
        
        Args:
            order: Order dict from broker API
            
        Returns:
            Quantity as integer, 0 if not found
        """
        return int(
            order.get('qty') or 
            order.get('quantity') or 
            order.get('fldQty') or 
            order.get('filledQty') or 
            0
        )
    
    @staticmethod
    def get_price(order: Dict[str, Any]) -> float:
        """
        Extract price with fallbacks.
        
        Args:
            order: Order dict from broker API
            
        Returns:
            Price as float, 0.0 if not found
        """
        return float(
            order.get('avgPrc') or 
            order.get('prc') or 
            order.get('price') or 
            order.get('executedPrice') or 
            order.get('executed_price') or 
            0.0
        )
    
    @staticmethod
    def get_rejection_reason(order: Dict[str, Any]) -> str:
        """
        Extract rejection reason with fallbacks.
        
        Args:
            order: Order dict from broker API
            
        Returns:
            Rejection reason, empty string if not found
        """
        return (
            order.get('rejRsn') or 
            order.get('rejectionReason') or 
            order.get('rmk') or 
            ''
        )
    
    @staticmethod
    def get_order_time(order: Dict[str, Any]) -> Optional[str]:
        """
        Extract order time/date with fallbacks.
        
        Args:
            order: Order dict from broker API
            
        Returns:
            Order time string, None if not found
        """
        return (
            order.get('ordDtTm') or 
            order.get('orderTime') or 
            order.get('order_time') or 
            order.get('timestamp') or 
            None
        )
    
    @staticmethod
    def is_buy_order(order: Dict[str, Any]) -> bool:
        """
        Check if order is a BUY order.
        
        Args:
            order: Order dict from broker API
            
        Returns:
            True if BUY order, False otherwise
        """
        txn_type = OrderFieldExtractor.get_transaction_type(order)
        return txn_type in ['B', 'BUY']
    
    @staticmethod
    def is_sell_order(order: Dict[str, Any]) -> bool:
        """
        Check if order is a SELL order.
        
        Args:
            order: Order dict from broker API
            
        Returns:
            True if SELL order, False otherwise
        """
        txn_type = OrderFieldExtractor.get_transaction_type(order)
        return txn_type in ['S', 'SELL']


