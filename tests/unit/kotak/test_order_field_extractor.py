#!/usr/bin/env python3
"""
Tests for OrderFieldExtractor utility class
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.utils.order_field_extractor import OrderFieldExtractor


class TestOrderFieldExtractor:
    """Test OrderFieldExtractor utility class"""
    
    def test_get_order_id_with_neoOrdNo(self):
        """Test extracting order ID with neoOrdNo field"""
        order = {'neoOrdNo': '123456789'}
        assert OrderFieldExtractor.get_order_id(order) == '123456789'
    
    def test_get_order_id_with_nOrdNo(self):
        """Test extracting order ID with nOrdNo field"""
        order = {'nOrdNo': '987654321'}
        assert OrderFieldExtractor.get_order_id(order) == '987654321'
    
    def test_get_order_id_with_orderId(self):
        """Test extracting order ID with orderId field"""
        order = {'orderId': '555555555'}
        assert OrderFieldExtractor.get_order_id(order) == '555555555'
    
    def test_get_order_id_with_order_id(self):
        """Test extracting order ID with order_id field"""
        order = {'order_id': '111111111'}
        assert OrderFieldExtractor.get_order_id(order) == '111111111'
    
    def test_get_order_id_fallback_order(self):
        """Test order ID fallback priority"""
        order = {
            'neoOrdNo': 'first',
            'nOrdNo': 'second',
            'orderId': 'third'
        }
        assert OrderFieldExtractor.get_order_id(order) == 'first'
    
    def test_get_order_id_empty(self):
        """Test extracting order ID when not present"""
        order = {}
        assert OrderFieldExtractor.get_order_id(order) == ''
    
    def test_get_symbol_with_trdSym(self):
        """Test extracting symbol with trdSym field"""
        order = {'trdSym': 'RELIANCE-EQ'}
        assert OrderFieldExtractor.get_symbol(order) == 'RELIANCE-EQ'
    
    def test_get_symbol_with_tradingSymbol(self):
        """Test extracting symbol with tradingSymbol field"""
        order = {'tradingSymbol': 'DALBHARAT-EQ'}
        assert OrderFieldExtractor.get_symbol(order) == 'DALBHARAT-EQ'
    
    def test_get_symbol_fallback(self):
        """Test symbol fallback priority"""
        order = {
            'trdSym': 'RELIANCE-EQ',
            'tradingSymbol': 'DALBHARAT-EQ'
        }
        assert OrderFieldExtractor.get_symbol(order) == 'RELIANCE-EQ'
    
    def test_get_transaction_type_buy(self):
        """Test extracting BUY transaction type"""
        order = {'transactionType': 'B'}
        assert OrderFieldExtractor.get_transaction_type(order) == 'B'
        
        order = {'trnsTp': 'BUY'}
        assert OrderFieldExtractor.get_transaction_type(order) == 'BUY'
    
    def test_get_transaction_type_sell(self):
        """Test extracting SELL transaction type"""
        order = {'transactionType': 'S'}
        assert OrderFieldExtractor.get_transaction_type(order) == 'S'
        
        order = {'trnsTp': 'SELL'}
        assert OrderFieldExtractor.get_transaction_type(order) == 'SELL'
    
    def test_get_transaction_type_case_insensitive(self):
        """Test transaction type is uppercase"""
        order = {'transactionType': 'buy'}
        assert OrderFieldExtractor.get_transaction_type(order) == 'BUY'
        
        order = {'trnsTp': 'sell'}
        assert OrderFieldExtractor.get_transaction_type(order) == 'SELL'
    
    def test_get_status_with_orderStatus(self):
        """Test extracting status with orderStatus field"""
        order = {'orderStatus': 'complete'}
        assert OrderFieldExtractor.get_status(order) == 'complete'
    
    def test_get_status_with_ordSt(self):
        """Test extracting status with ordSt field"""
        order = {'ordSt': 'executed'}
        assert OrderFieldExtractor.get_status(order) == 'executed'
    
    def test_get_status_lowercase(self):
        """Test status is lowercase"""
        order = {'orderStatus': 'COMPLETE'}
        assert OrderFieldExtractor.get_status(order) == 'complete'
    
    def test_get_quantity_with_qty(self):
        """Test extracting quantity with qty field"""
        order = {'qty': 10}
        assert OrderFieldExtractor.get_quantity(order) == 10
    
    def test_get_quantity_with_quantity(self):
        """Test extracting quantity with quantity field"""
        order = {'quantity': 20}
        assert OrderFieldExtractor.get_quantity(order) == 20
    
    def test_get_quantity_with_fldQty(self):
        """Test extracting quantity with fldQty field"""
        order = {'fldQty': 15}
        assert OrderFieldExtractor.get_quantity(order) == 15
    
    def test_get_quantity_fallback(self):
        """Test quantity fallback priority"""
        order = {'qty': 10, 'quantity': 20, 'fldQty': 15}
        assert OrderFieldExtractor.get_quantity(order) == 10
    
    def test_get_quantity_zero_default(self):
        """Test quantity defaults to 0"""
        order = {}
        assert OrderFieldExtractor.get_quantity(order) == 0
    
    def test_get_price_with_avgPrc(self):
        """Test extracting price with avgPrc field"""
        order = {'avgPrc': 2100.50}
        assert OrderFieldExtractor.get_price(order) == 2100.50
    
    def test_get_price_with_prc(self):
        """Test extracting price with prc field"""
        order = {'prc': 1500.75}
        assert OrderFieldExtractor.get_price(order) == 1500.75
    
    def test_get_price_with_price(self):
        """Test extracting price with price field"""
        order = {'price': 3000.25}
        assert OrderFieldExtractor.get_price(order) == 3000.25
    
    def test_get_price_fallback(self):
        """Test price fallback priority"""
        order = {'avgPrc': 2100.50, 'prc': 1500.75, 'price': 3000.25}
        assert OrderFieldExtractor.get_price(order) == 2100.50
    
    def test_get_price_zero_default(self):
        """Test price defaults to 0.0"""
        order = {}
        assert OrderFieldExtractor.get_price(order) == 0.0
    
    def test_get_rejection_reason(self):
        """Test extracting rejection reason"""
        order = {'rejRsn': 'Insufficient balance'}
        assert OrderFieldExtractor.get_rejection_reason(order) == 'Insufficient balance'
        
        order = {'rejectionReason': 'Invalid symbol'}
        assert OrderFieldExtractor.get_rejection_reason(order) == 'Invalid symbol'
    
    def test_get_order_time(self):
        """Test extracting order time"""
        order = {'ordDtTm': '03-Nov-2025 09:15:00'}
        assert OrderFieldExtractor.get_order_time(order) == '03-Nov-2025 09:15:00'
        
        order = {'orderTime': '03-Nov-2025 10:30:00'}
        assert OrderFieldExtractor.get_order_time(order) == '03-Nov-2025 10:30:00'
    
    def test_get_order_time_none(self):
        """Test order time returns None when not present"""
        order = {}
        assert OrderFieldExtractor.get_order_time(order) is None
    
    def test_is_buy_order(self):
        """Test is_buy_order helper"""
        order = {'transactionType': 'B'}
        assert OrderFieldExtractor.is_buy_order(order) is True
        
        order = {'trnsTp': 'BUY'}
        assert OrderFieldExtractor.is_buy_order(order) is True
        
        order = {'transactionType': 'S'}
        assert OrderFieldExtractor.is_buy_order(order) is False
    
    def test_is_sell_order(self):
        """Test is_sell_order helper"""
        order = {'transactionType': 'S'}
        assert OrderFieldExtractor.is_sell_order(order) is True
        
        order = {'trnsTp': 'SELL'}
        assert OrderFieldExtractor.is_sell_order(order) is True
        
        order = {'transactionType': 'B'}
        assert OrderFieldExtractor.is_sell_order(order) is False
    
    def test_real_world_order(self):
        """Test with realistic broker order format"""
        order = {
            'neoOrdNo': '251103000008704',
            'trdSym': 'DALBHARAT-EQ',
            'trnsTp': 'S',
            'ordSt': 'complete',
            'qty': 10,
            'avgPrc': 2100.50,
            'ordDtTm': '03-Nov-2025 09:15:00'
        }
        
        assert OrderFieldExtractor.get_order_id(order) == '251103000008704'
        assert OrderFieldExtractor.get_symbol(order) == 'DALBHARAT-EQ'
        assert OrderFieldExtractor.get_transaction_type(order) == 'S'
        assert OrderFieldExtractor.get_status(order) == 'complete'
        assert OrderFieldExtractor.get_quantity(order) == 10
        assert OrderFieldExtractor.get_price(order) == 2100.50
        assert OrderFieldExtractor.is_sell_order(order) is True
        assert OrderFieldExtractor.is_buy_order(order) is False





