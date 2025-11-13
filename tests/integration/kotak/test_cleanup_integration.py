#!/usr/bin/env python3
"""
Integration tests for Phase 1 refactored cleanup functionality
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json
import tempfile
import os

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.utils.order_field_extractor import OrderFieldExtractor
from modules.kotak_neo_auto_trader.utils.order_status_parser import OrderStatusParser


class TestCleanupIntegration:
    """Integration tests for cleanup functionality"""
    
    @pytest.fixture
    def mock_auth(self):
        """Create mock auth object"""
        auth = Mock(spec=KotakNeoAuth)
        auth.client = Mock()
        return auth
    
    @pytest.fixture
    def temp_history_file(self):
        """Create temporary history file"""
        fd, path = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        
        # Initialize with test data
        data = {
            "trades": [
                {
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "status": "open",
                    "qty": 10,
                    "entry_price": 2000.0
                },
                {
                    "symbol": "TCS",
                    "ticker": "TCS.NS",
                    "status": "open",
                    "qty": 5,
                    "entry_price": 3000.0
                }
            ],
            "failed_orders": []
        }
        
        with open(path, 'w') as f:
            json.dump(data, f)
        
        yield path
        
        # Cleanup
        if os.path.exists(path):
            os.remove(path)
    
    @pytest.fixture
    def sell_manager(self, mock_auth, temp_history_file):
        """Create SellOrderManager instance with temp history"""
        with patch('modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster'):
            manager = SellOrderManager(auth=mock_auth, history_path=temp_history_file)
            # Replace orders with a mock
            manager.orders = Mock()
            manager.active_sell_orders = {
                'RELIANCE': {'order_id': '99999', 'qty': 10, 'target_price': 2500.0},
                'TCS': {'order_id': '88888', 'qty': 5, 'target_price': 3500.0}
            }
            manager.lowest_ema9 = {
                'RELIANCE': 2500.0,
                'TCS': 3500.0
            }
            return manager
    
    def test_full_cleanup_flow_manual_sell(self, sell_manager):
        """Test complete cleanup flow with manual sell detection"""
        # Setup: User manually sold RELIANCE (different order ID)
        executed_orders = [{
            'nOrdNo': '12345',  # Manual order (not tracked)
            'trdSym': 'RELIANCE-EQ',
            'trnsTp': 'S',
            'qty': 10,
            'avgPrc': 2500.0
        }]
        
        # Broker orders show bot order still open
        broker_orders = {
            'data': [
                {
                    'nOrdNo': '99999',  # Bot order
                    'trdSym': 'RELIANCE-EQ',
                    'ordSt': 'open'
                },
                {
                    'nOrdNo': '88888',  # TCS bot order
                    'trdSym': 'TCS-EQ',
                    'ordSt': 'open'
                }
            ]
        }
        
        sell_manager.orders.get_executed_orders.return_value = executed_orders
        sell_manager.orders.get_orders.return_value = broker_orders
        sell_manager.orders.cancel_order = Mock()
        
        # Run cleanup
        sell_manager._cleanup_rejected_orders()
        
        # Verify bot order was cancelled
        sell_manager.orders.cancel_order.assert_called_once_with('99999')
        
        # Verify RELIANCE removed from tracking
        assert 'RELIANCE' not in sell_manager.active_sell_orders
        assert 'RELIANCE' not in sell_manager.lowest_ema9
        
        # Verify TCS still tracked (no manual sell)
        assert 'TCS' in sell_manager.active_sell_orders
    
    def test_cleanup_with_rejected_order(self, sell_manager):
        """Test cleanup removes rejected orders"""
        # No manual sells
        sell_manager.orders.get_executed_orders.return_value = []
        
        # Broker orders show RELIANCE order rejected
        broker_orders = {
            'data': [
                {
                    'nOrdNo': '99999',
                    'trdSym': 'RELIANCE-EQ',
                    'ordSt': 'rejected',
                    'rejRsn': 'Insufficient balance'
                },
                {
                    'nOrdNo': '88888',
                    'trdSym': 'TCS-EQ',
                    'ordSt': 'open'
                }
            ]
        }
        
        sell_manager.orders.get_orders.return_value = broker_orders
        
        # Run cleanup
        sell_manager._cleanup_rejected_orders()
        
        # Verify RELIANCE removed (rejected)
        assert 'RELIANCE' not in sell_manager.active_sell_orders
        
        # Verify TCS still tracked (open)
        assert 'TCS' in sell_manager.active_sell_orders
    
    def test_cleanup_with_cancelled_order(self, sell_manager):
        """Test cleanup removes cancelled orders"""
        sell_manager.orders.get_executed_orders.return_value = []
        
        broker_orders = {
            'data': [
                {
                    'nOrdNo': '99999',
                    'trdSym': 'RELIANCE-EQ',
                    'ordSt': 'cancelled'
                }
            ]
        }
        
        sell_manager.orders.get_orders.return_value = broker_orders
        
        sell_manager._cleanup_rejected_orders()
        
        # Verify RELIANCE removed (cancelled)
        assert 'RELIANCE' not in sell_manager.active_sell_orders
    
    def test_cleanup_with_partial_manual_sell(self, sell_manager):
        """Test cleanup handles partial manual sell"""
        # User manually sold 5 of 10 RELIANCE shares
        executed_orders = [{
            'nOrdNo': '12345',
            'trdSym': 'RELIANCE-EQ',
            'trnsTp': 'S',
            'qty': 5,
            'avgPrc': 2500.0
        }]
        
        sell_manager.orders.get_executed_orders.return_value = executed_orders
        sell_manager.orders.get_orders.return_value = {'data': []}
        sell_manager.orders.cancel_order = Mock()
        
        sell_manager._cleanup_rejected_orders()
        
        # Should cancel bot order (wrong quantity)
        sell_manager.orders.cancel_order.assert_called_once()
        
        # Should be removed from tracking (will re-add with correct qty)
        assert 'RELIANCE' not in sell_manager.active_sell_orders
    
    def test_cleanup_ignores_bot_orders(self, sell_manager):
        """Test cleanup ignores bot orders (not manual)"""
        # Executed order matches bot order ID
        executed_orders = [{
            'nOrdNo': '99999',  # Bot order ID
            'trdSym': 'RELIANCE-EQ',
            'trnsTp': 'S',
            'qty': 10,
            'avgPrc': 2500.0
        }]
        
        sell_manager.orders.get_executed_orders.return_value = executed_orders
        sell_manager.orders.get_orders.return_value = {'data': []}
        sell_manager.orders.cancel_order = Mock()
        
        sell_manager._cleanup_rejected_orders()
        
        # Should not cancel (it's bot's own order)
        sell_manager.orders.cancel_order.assert_not_called()
        
        # Should still be tracked
        assert 'RELIANCE' in sell_manager.active_sell_orders
    
    def test_cleanup_ignores_buy_orders(self, sell_manager):
        """Test cleanup ignores BUY orders"""
        executed_orders = [{
            'nOrdNo': '12345',
            'trdSym': 'RELIANCE-EQ',
            'trnsTp': 'B',  # BUY order
            'qty': 10,
            'avgPrc': 2000.0
        }]
        
        sell_manager.orders.get_executed_orders.return_value = executed_orders
        sell_manager.orders.get_orders.return_value = {'data': []}
        
        sell_manager._cleanup_rejected_orders()
        
        # Should not affect tracking (BUY orders ignored)
        assert 'RELIANCE' in sell_manager.active_sell_orders
    
    def test_cleanup_trade_history_update_full_exit(self, sell_manager, temp_history_file):
        """Test cleanup updates trade history for full manual exit"""
        # Setup: Manual sell all shares
        manual_sells = {
            'RELIANCE': {
                'qty': 10,
                'orders': [{'order_id': '12345', 'qty': 10, 'price': 2500.0}]
            }
        }
        
        sell_manager._handle_manual_sells(manual_sells)
        
        # Load and verify trade history
        with open(temp_history_file, 'r') as f:
            history = json.load(f)
        
        reliance_trade = next(t for t in history['trades'] if t['symbol'] == 'RELIANCE')
        assert reliance_trade['status'] == 'closed'
        assert reliance_trade['exit_reason'] == 'MANUAL_EXIT'
        assert reliance_trade['exit_price'] == 2500.0
        assert 'pnl' in reliance_trade
        assert 'pnl_pct' in reliance_trade
    
    def test_cleanup_trade_history_update_partial_exit(self, sell_manager, temp_history_file):
        """Test cleanup updates trade history for partial manual exit"""
        # Setup: Manual sell partial shares
        manual_sells = {
            'RELIANCE': {
                'qty': 5,
                'orders': [{'order_id': '12345', 'qty': 5, 'price': 2500.0}]
            }
        }
        
        sell_manager._handle_manual_sells(manual_sells)
        
        # Load and verify trade history
        with open(temp_history_file, 'r') as f:
            history = json.load(f)
        
        reliance_trade = next(t for t in history['trades'] if t['symbol'] == 'RELIANCE')
        assert reliance_trade['status'] == 'open'  # Still open
        assert reliance_trade['qty'] == 5  # Reduced quantity
        assert 'partial_exits' in reliance_trade
        assert len(reliance_trade['partial_exits']) == 1
        assert reliance_trade['partial_exits'][0]['qty'] == 5
        assert reliance_trade['partial_exits'][0]['exit_reason'] == 'MANUAL_PARTIAL_EXIT'


class TestOrderFieldExtractorIntegration:
    """Integration tests for OrderFieldExtractor in real scenarios"""
    
    def test_real_broker_order_format(self):
        """Test OrderFieldExtractor with realistic broker order format"""
        # Realistic broker order response
        order = {
            'neoOrdNo': '251103000008704',
            'trdSym': 'DALBHARAT-EQ',
            'trnsTp': 'S',
            'ordSt': 'complete',
            'qty': 10,
            'avgPrc': 2100.50,
            'ordDtTm': '03-Nov-2025 09:15:00',
            'rejRsn': ''
        }
        
        assert OrderFieldExtractor.get_order_id(order) == '251103000008704'
        assert OrderFieldExtractor.get_symbol(order) == 'DALBHARAT-EQ'
        assert OrderFieldExtractor.get_transaction_type(order) == 'S'
        assert OrderFieldExtractor.get_status(order) == 'complete'
        assert OrderFieldExtractor.get_quantity(order) == 10
        assert OrderFieldExtractor.get_price(order) == 2100.50
        assert OrderFieldExtractor.is_sell_order(order) is True
        assert OrderFieldExtractor.is_buy_order(order) is False
    
    def test_fallback_field_extraction(self):
        """Test OrderFieldExtractor fallback logic"""
        # Order with alternative field names
        order = {
            'orderId': '555555',
            'tradingSymbol': 'RELIANCE-EQ',
            'transactionType': 'B',
            'orderStatus': 'open',
            'quantity': 20,
            'price': 2500.0,
            'orderTime': '03-Nov-2025 10:00:00'
        }
        
        assert OrderFieldExtractor.get_order_id(order) == '555555'
        assert OrderFieldExtractor.get_symbol(order) == 'RELIANCE-EQ'
        assert OrderFieldExtractor.get_transaction_type(order) == 'B'
        assert OrderFieldExtractor.get_status(order) == 'open'
        assert OrderFieldExtractor.get_quantity(order) == 20
        assert OrderFieldExtractor.get_price(order) == 2500.0
        assert OrderFieldExtractor.is_buy_order(order) is True


class TestOrderStatusParserIntegration:
    """Integration tests for OrderStatusParser in real scenarios"""
    
    def test_real_broker_statuses(self):
        """Test OrderStatusParser with realistic broker statuses"""
        # Complete order
        order = {
            'neoOrdNo': '251103000008704',
            'ordSt': 'complete'
        }
        assert OrderStatusParser.is_completed(order) is True
        assert OrderStatusParser.is_terminal(order) is True
        
        # Rejected order
        order = {
            'nOrdNo': '12345',
            'orderStatus': 'rejected',
            'rejRsn': 'Insufficient balance'
        }
        assert OrderStatusParser.is_rejected(order) is True
        assert OrderStatusParser.is_terminal(order) is True
        
        # Open order
        order = {
            'ordSt': 'open'
        }
        assert OrderStatusParser.is_active(order) is True
        assert OrderStatusParser.is_terminal(order) is False
    
    def test_status_keyword_matching(self):
        """Test OrderStatusParser keyword matching"""
        # Status with extra text
        order = {'orderStatus': 'order complete successfully'}
        assert OrderStatusParser.is_completed(order) is True
        
        order = {'ordSt': 'order executed by broker'}
        assert OrderStatusParser.is_completed(order) is True
        
        order = {'status': 'order rejected due to insufficient balance'}
        assert OrderStatusParser.is_rejected(order) is True


class TestEndToEndCleanupFlow:
    """End-to-end tests for complete cleanup flow"""
    
    @pytest.fixture
    def mock_auth(self):
        auth = Mock(spec=KotakNeoAuth)
        auth.client = Mock()
        return auth
    
    @pytest.fixture
    def temp_history_file(self):
        fd, path = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        
        data = {
            "trades": [
                {
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "status": "open",
                    "qty": 10,
                    "entry_price": 2000.0
                }
            ],
            "failed_orders": []
        }
        
        with open(path, 'w') as f:
            json.dump(data, f)
        
        yield path
        
        if os.path.exists(path):
            os.remove(path)
    
    def test_complete_cleanup_scenario(self, mock_auth, temp_history_file):
        """Test complete cleanup scenario with multiple conditions"""
        with patch('modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster'):
            manager = SellOrderManager(auth=mock_auth, history_path=temp_history_file)
            # Replace orders with a mock
            manager.orders = Mock()
            manager.active_sell_orders = {
                'RELIANCE': {'order_id': '99999', 'qty': 10},
                'TCS': {'order_id': '88888', 'qty': 5},
                'INFY': {'order_id': '77777', 'qty': 8}
            }
            
            # Scenario:
            # - RELIANCE: Manual sell detected
            # - TCS: Order rejected
            # - INFY: Order still open (no action)
            
            executed_orders = [{
                'nOrdNo': '12345',  # Manual order
                'trdSym': 'RELIANCE-EQ',
                'trnsTp': 'S',
                'qty': 10,
                'avgPrc': 2500.0
            }]
            
            broker_orders = {
                'data': [
                    {
                        'nOrdNo': '88888',  # TCS rejected
                        'trdSym': 'TCS-EQ',
                        'ordSt': 'rejected'
                    },
                    {
                        'nOrdNo': '77777',  # INFY open
                        'trdSym': 'INFY-EQ',
                        'ordSt': 'open'
                    }
                ]
            }
            
            manager.orders.get_executed_orders.return_value = executed_orders
            manager.orders.get_orders.return_value = broker_orders
            manager.orders.cancel_order = Mock()
            
            manager._cleanup_rejected_orders()
            
            # RELIANCE removed (manual sell)
            assert 'RELIANCE' not in manager.active_sell_orders
            
            # TCS removed (rejected)
            assert 'TCS' not in manager.active_sell_orders
            
            # INFY still tracked (open)
            assert 'INFY' in manager.active_sell_orders

