#!/usr/bin/env python3
"""
Tests for OrderStatusParser utility class
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.utils.order_status_parser import OrderStatusParser
from modules.kotak_neo_auto_trader.domain.value_objects.order_enums import OrderStatus


class TestOrderStatusParser:
    """Test OrderStatusParser utility class"""
    
    def test_parse_status_complete(self):
        """Test parsing complete status"""
        order = {'orderStatus': 'complete'}
        assert OrderStatusParser.parse_status(order) == OrderStatus.COMPLETE
        
        order = {'ordSt': 'complete'}
        assert OrderStatusParser.parse_status(order) == OrderStatus.COMPLETE
    
    def test_parse_status_executed(self):
        """Test parsing executed status"""
        order = {'orderStatus': 'executed'}
        assert OrderStatusParser.parse_status(order) == OrderStatus.EXECUTED
        
        order = {'status': 'executed'}
        assert OrderStatusParser.parse_status(order) == OrderStatus.EXECUTED
    
    def test_parse_status_filled(self):
        """Test parsing filled status (maps to COMPLETE per enum definition)"""
        order = {'orderStatus': 'filled'}
        assert OrderStatusParser.parse_status(order) == OrderStatus.COMPLETE
    
    def test_parse_status_rejected(self):
        """Test parsing rejected status"""
        order = {'orderStatus': 'rejected'}
        assert OrderStatusParser.parse_status(order) == OrderStatus.REJECTED
        
        order = {'ordSt': 'rejected'}
        assert OrderStatusParser.parse_status(order) == OrderStatus.REJECTED
    
    def test_parse_status_cancelled(self):
        """Test parsing cancelled status"""
        order = {'orderStatus': 'cancelled'}
        assert OrderStatusParser.parse_status(order) == OrderStatus.CANCELLED
        
        order = {'status': 'canceled'}  # American spelling
        assert OrderStatusParser.parse_status(order) == OrderStatus.CANCELLED
    
    def test_parse_status_open(self):
        """Test parsing open status"""
        order = {'orderStatus': 'open'}
        assert OrderStatusParser.parse_status(order) == OrderStatus.OPEN
    
    def test_parse_status_pending(self):
        """Test parsing pending status"""
        order = {'orderStatus': 'pending'}
        assert OrderStatusParser.parse_status(order) == OrderStatus.PENDING
    
    def test_parse_status_partial(self):
        """Test parsing partial fill status"""
        order = {'orderStatus': 'partial'}
        assert OrderStatusParser.parse_status(order) == OrderStatus.PARTIALLY_FILLED
        
        order = {'ordSt': 'partially executed'}
        # Should match "partially" (longer keyword) first, not "executed"
        assert OrderStatusParser.parse_status(order) == OrderStatus.PARTIALLY_FILLED
    
    def test_parse_status_keyword_matching(self):
        """Test keyword matching for status"""
        order = {'orderStatus': 'order complete'}
        assert OrderStatusParser.parse_status(order) == OrderStatus.COMPLETE
        
        order = {'ordSt': 'order executed successfully'}
        assert OrderStatusParser.parse_status(order) == OrderStatus.EXECUTED
        
        order = {'status': 'order rejected by broker'}
        assert OrderStatusParser.parse_status(order) == OrderStatus.REJECTED
    
    def test_parse_status_case_insensitive(self):
        """Test status parsing is case insensitive"""
        order = {'orderStatus': 'COMPLETE'}
        assert OrderStatusParser.parse_status(order) == OrderStatus.COMPLETE
        
        order = {'ordSt': 'EXECUTED'}
        assert OrderStatusParser.parse_status(order) == OrderStatus.EXECUTED
    
    def test_parse_status_unknown_defaults_to_pending(self):
        """Test unknown status defaults to PENDING"""
        order = {'orderStatus': 'unknown_status'}
        assert OrderStatusParser.parse_status(order) == OrderStatus.PENDING
        
        order = {}
        assert OrderStatusParser.parse_status(order) == OrderStatus.PENDING
    
    def test_is_completed(self):
        """Test is_completed helper"""
        order = {'orderStatus': 'complete'}
        assert OrderStatusParser.is_completed(order) is True
        
        order = {'ordSt': 'executed'}
        assert OrderStatusParser.is_completed(order) is True
        
        order = {'status': 'open'}
        assert OrderStatusParser.is_completed(order) is False
    
    def test_is_active(self):
        """Test is_active helper"""
        order = {'orderStatus': 'open'}
        assert OrderStatusParser.is_active(order) is True
        
        order = {'ordSt': 'pending'}
        assert OrderStatusParser.is_active(order) is True
        
        order = {'status': 'complete'}
        assert OrderStatusParser.is_active(order) is False
    
    def test_is_terminal(self):
        """Test is_terminal helper"""
        order = {'orderStatus': 'complete'}
        assert OrderStatusParser.is_terminal(order) is True
        
        order = {'ordSt': 'executed'}
        assert OrderStatusParser.is_terminal(order) is True
        
        order = {'status': 'rejected'}
        assert OrderStatusParser.is_terminal(order) is True
        
        order = {'orderStatus': 'open'}
        assert OrderStatusParser.is_terminal(order) is False
    
    def test_is_rejected(self):
        """Test is_rejected helper"""
        order = {'orderStatus': 'rejected'}
        assert OrderStatusParser.is_rejected(order) is True
        
        order = {'ordSt': 'complete'}
        assert OrderStatusParser.is_rejected(order) is False
    
    def test_is_cancelled(self):
        """Test is_cancelled helper"""
        order = {'orderStatus': 'cancelled'}
        assert OrderStatusParser.is_cancelled(order) is True
        
        order = {'ordSt': 'canceled'}
        assert OrderStatusParser.is_cancelled(order) is True
        
        order = {'status': 'complete'}
        assert OrderStatusParser.is_cancelled(order) is False
    
    def test_is_pending(self):
        """Test is_pending helper"""
        order = {'orderStatus': 'pending'}
        assert OrderStatusParser.is_pending(order) is True
        
        order = {'ordSt': 'complete'}
        assert OrderStatusParser.is_pending(order) is False
    
    def test_parse_status_from_string(self):
        """Test parse_status_from_string method"""
        assert OrderStatusParser.parse_status_from_string('complete') == OrderStatus.COMPLETE
        assert OrderStatusParser.parse_status_from_string('EXECUTED') == OrderStatus.EXECUTED
        assert OrderStatusParser.parse_status_from_string('rejected') == OrderStatus.REJECTED
        assert OrderStatusParser.parse_status_from_string('unknown') == OrderStatus.PENDING
        assert OrderStatusParser.parse_status_from_string('') == OrderStatus.PENDING
        assert OrderStatusParser.parse_status_from_string(None) == OrderStatus.PENDING
    
    def test_real_world_scenarios(self):
        """Test with realistic broker order statuses"""
        # Completed order
        order = {
            'neoOrdNo': '251103000008704',
            'ordSt': 'complete',
            'trdSym': 'DALBHARAT-EQ'
        }
        assert OrderStatusParser.is_completed(order) is True
        assert OrderStatusParser.is_terminal(order) is True
        assert OrderStatusParser.is_active(order) is False
        
        # Open order
        order = {
            'ordSt': 'open',
            'trdSym': 'RELIANCE-EQ'
        }
        assert OrderStatusParser.is_active(order) is True
        assert OrderStatusParser.is_terminal(order) is False
        
        # Rejected order
        order = {
            'orderStatus': 'rejected',
            'rejRsn': 'Insufficient balance'
        }
        assert OrderStatusParser.is_rejected(order) is True
        assert OrderStatusParser.is_terminal(order) is True
        
        # Cancelled order
        order = {
            'ordSt': 'cancelled'
        }
        assert OrderStatusParser.is_cancelled(order) is True
        assert OrderStatusParser.is_terminal(order) is True

