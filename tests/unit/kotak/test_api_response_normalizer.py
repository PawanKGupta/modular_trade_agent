#!/usr/bin/env python3
"""
Tests for BrokerResponseNormalizer utility class
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.utils.api_response_normalizer import BrokerResponseNormalizer


class TestBrokerResponseNormalizer:
    """Test BrokerResponseNormalizer utility class"""
    
    def test_normalize_order_basic(self):
        """Test basic order normalization"""
        order = {
            'neoOrdNo': '12345',
            'trdSym': 'RELIANCE-EQ',
            'orderStatus': 'complete',
            'transactionType': 'SELL',
            'qty': 10,
            'avgPrc': 2500.50
        }
        
        normalized = BrokerResponseNormalizer.normalize_order(order)
        
        assert normalized['order_id'] == '12345'
        assert normalized['symbol'] == 'RELIANCE-EQ'
        assert normalized['status'] == 'complete'
        assert normalized['transaction_type'] == 'SELL'
        assert normalized['quantity'] == 10
        assert normalized['price'] == 2500.50
        assert '_original' in normalized
    
    def test_normalize_order_fallback_fields(self):
        """Test fallback field extraction"""
        order = {
            'nOrdNo': '67890',  # Fallback for order_id
            'tradingSymbol': 'DALBHARAT-EQ',  # Fallback for symbol
            'ordSt': 'open',  # Fallback for status
            'trnsTp': 'BUY',  # Fallback for transaction_type
            'quantity': 5,  # Fallback for quantity
            'price': 2100.0  # Fallback for price
        }
        
        normalized = BrokerResponseNormalizer.normalize_order(order)
        
        assert normalized['order_id'] == '67890'
        assert normalized['symbol'] == 'DALBHARAT-EQ'
        assert normalized['status'] == 'open'
        assert normalized['transaction_type'] == 'BUY'
        assert normalized['quantity'] == 5
        assert normalized['price'] == 2100.0
    
    def test_normalize_order_list(self):
        """Test normalizing list of orders"""
        orders = [
            {'neoOrdNo': '1', 'trdSym': 'RELIANCE-EQ', 'orderStatus': 'complete'},
            {'nOrdNo': '2', 'tradingSymbol': 'DALBHARAT-EQ', 'ordSt': 'open'}
        ]
        
        normalized_list = BrokerResponseNormalizer.normalize_order_list(orders)
        
        assert len(normalized_list) == 2
        assert normalized_list[0]['order_id'] == '1'
        assert normalized_list[0]['symbol'] == 'RELIANCE-EQ'
        assert normalized_list[1]['order_id'] == '2'
        assert normalized_list[1]['symbol'] == 'DALBHARAT-EQ'
    
    def test_get_order_id(self):
        """Test get_order_id helper"""
        order = {'neoOrdNo': '12345'}
        assert BrokerResponseNormalizer.get_order_id(order) == '12345'
        
        order = {'nOrdNo': '67890'}
        assert BrokerResponseNormalizer.get_order_id(order) == '67890'
        
        order = {'order_id': '99999'}  # Already normalized
        assert BrokerResponseNormalizer.get_order_id(order) == '99999'
    
    def test_get_symbol(self):
        """Test get_symbol helper"""
        order = {'trdSym': 'RELIANCE-EQ'}
        assert BrokerResponseNormalizer.get_symbol(order) == 'RELIANCE-EQ'
        
        order = {'tradingSymbol': 'DALBHARAT-EQ'}
        assert BrokerResponseNormalizer.get_symbol(order) == 'DALBHARAT-EQ'
        
        order = {'symbol': 'GALLANTT-EQ'}  # Already normalized
        assert BrokerResponseNormalizer.get_symbol(order) == 'GALLANTT-EQ'
    
    def test_get_status(self):
        """Test get_status helper"""
        order = {'orderStatus': 'complete'}
        assert BrokerResponseNormalizer.get_status(order) == 'complete'
        
        order = {'ordSt': 'open'}
        assert BrokerResponseNormalizer.get_status(order) == 'open'
        
        order = {'status': 'executed'}  # Already normalized
        assert BrokerResponseNormalizer.get_status(order) == 'executed'
    
    def test_get_transaction_type(self):
        """Test get_transaction_type helper"""
        order = {'transactionType': 'SELL'}
        assert BrokerResponseNormalizer.get_transaction_type(order) == 'SELL'
        
        order = {'trnsTp': 'buy'}
        assert BrokerResponseNormalizer.get_transaction_type(order) == 'BUY'
        
        order = {'transaction_type': 'SELL'}  # Already normalized
        assert BrokerResponseNormalizer.get_transaction_type(order) == 'SELL'
    
    def test_get_quantity(self):
        """Test get_quantity helper"""
        order = {'qty': 10}
        assert BrokerResponseNormalizer.get_quantity(order) == 10
        
        order = {'quantity': 5}
        assert BrokerResponseNormalizer.get_quantity(order) == 5
        
        order = {'filledQty': 3}
        assert BrokerResponseNormalizer.get_quantity(order) == 3
        
        order = {'quantity': 7}  # Already normalized
        assert BrokerResponseNormalizer.get_quantity(order) == 7
    
    def test_get_price(self):
        """Test get_price helper"""
        order = {'avgPrc': 2500.50}
        assert BrokerResponseNormalizer.get_price(order) == 2500.50
        
        order = {'prc': 2100.0}
        assert BrokerResponseNormalizer.get_price(order) == 2100.0
        
        order = {'price': 1800.75}  # Already normalized
        assert BrokerResponseNormalizer.get_price(order) == 1800.75
    
    def test_normalize_order_missing_fields(self):
        """Test normalization with missing fields"""
        order = {'neoOrdNo': '12345'}  # Only order_id
        
        normalized = BrokerResponseNormalizer.normalize_order(order)
        
        assert normalized['order_id'] == '12345'
        # Other fields should not be present (not in mapping)
        assert 'symbol' not in normalized or normalized.get('symbol') is None
    
    def test_normalize_order_preserves_original(self):
        """Test that original order is preserved"""
        order = {'neoOrdNo': '12345', 'customField': 'customValue'}
        
        normalized = BrokerResponseNormalizer.normalize_order(order)
        
        assert '_original' in normalized
        assert normalized['_original']['neoOrdNo'] == '12345'
        assert normalized['_original']['customField'] == 'customValue'





