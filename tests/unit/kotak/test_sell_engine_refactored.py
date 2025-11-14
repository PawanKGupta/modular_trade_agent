#!/usr/bin/env python3
"""
Tests for refactored sell_engine methods (Phase 1 refactoring)
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.utils.order_field_extractor import OrderFieldExtractor
from modules.kotak_neo_auto_trader.utils.order_status_parser import OrderStatusParser
from modules.kotak_neo_auto_trader.domain.value_objects.order_enums import OrderStatus


class TestRefactoredSellEngineMethods:
    """Test refactored methods in SellOrderManager"""
    
    @pytest.fixture
    def mock_auth(self):
        """Create mock auth object"""
        auth = Mock(spec=KotakNeoAuth)
        auth.client = Mock()
        return auth
    
    @pytest.fixture
    def sell_manager(self, mock_auth):
        """Create SellOrderManager instance"""
        with patch('modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster'):
            manager = SellOrderManager(auth=mock_auth, history_path='test_history.json')
            # Mock the orders object properly
            manager.orders = Mock()
            return manager
    
    def test_detect_manual_sells_no_orders(self, sell_manager):
        """Test _detect_manual_sells with no executed orders"""
        sell_manager.orders.get_executed_orders.return_value = []
        result = sell_manager._detect_manual_sells()
        assert result == {}
    
    def test_detect_manual_sells_with_bot_order(self, sell_manager):
        """Test _detect_manual_sells ignores bot orders"""
        # Setup: bot order tracked
        sell_manager.active_sell_orders = {
            'RELIANCE': {'order_id': '12345', 'qty': 10}
        }
        
        # Executed order matches bot order ID
        executed_orders = [{
            'nOrdNo': '12345',
            'trdSym': 'RELIANCE-EQ',
            'trnsTp': 'S',
            'qty': 10,
            'avgPrc': 2500.0
        }]
        sell_manager.orders.get_executed_orders.return_value = executed_orders
        
        result = sell_manager._detect_manual_sells()
        assert result == {}  # Should be empty (bot order, not manual)
    
    def test_detect_manual_sells_with_manual_order(self, sell_manager):
        """Test _detect_manual_sells detects manual sell"""
        # Setup: bot has different order ID
        sell_manager.active_sell_orders = {
            'RELIANCE': {'order_id': '99999', 'qty': 10}
        }
        
        # Executed order has different order ID (manual sell)
        executed_orders = [{
            'nOrdNo': '12345',  # Different from bot order
            'trdSym': 'RELIANCE-EQ',
            'trnsTp': 'S',
            'qty': 5,
            'avgPrc': 2500.0
        }]
        sell_manager.orders.get_executed_orders.return_value = executed_orders
        
        result = sell_manager._detect_manual_sells()
        assert 'RELIANCE' in result
        assert result['RELIANCE']['qty'] == 5
        assert len(result['RELIANCE']['orders']) == 1
        assert result['RELIANCE']['orders'][0]['order_id'] == '12345'
    
    def test_detect_manual_sells_ignores_buy_orders(self, sell_manager):
        """Test _detect_manual_sells ignores BUY orders"""
        executed_orders = [{
            'nOrdNo': '12345',
            'trdSym': 'RELIANCE-EQ',
            'trnsTp': 'B',  # BUY order
            'qty': 10,
            'avgPrc': 2500.0
        }]
        sell_manager.orders.get_executed_orders.return_value = executed_orders
        
        result = sell_manager._detect_manual_sells()
        assert result == {}
    
    def test_is_tracked_order(self, sell_manager):
        """Test _is_tracked_order helper"""
        sell_manager.active_sell_orders = {
            'RELIANCE': {'order_id': '12345'},
            'TCS': {'order_id': '67890'}
        }
        
        assert sell_manager._is_tracked_order('12345') is True
        assert sell_manager._is_tracked_order('67890') is True
        assert sell_manager._is_tracked_order('99999') is False
    
    def test_handle_manual_sells_full_exit(self, sell_manager):
        """Test _handle_manual_sells with full exit"""
        # Setup tracked order
        sell_manager.active_sell_orders = {
            'RELIANCE': {'order_id': '99999', 'qty': 10}
        }
        
        # Manual sell info (sold all shares)
        manual_sells = {
            'RELIANCE': {
                'qty': 10,
                'orders': [{'order_id': '12345', 'qty': 10, 'price': 2500.0}]
            }
        }
        
        # Mock dependencies
        sell_manager.orders.cancel_order = Mock()
        sell_manager._update_trade_history_for_manual_sell = Mock()
        
        sell_manager._handle_manual_sells(manual_sells)
        
        # Should cancel bot order
        sell_manager.orders.cancel_order.assert_called_once_with('99999')
        # Should update trade history
        sell_manager._update_trade_history_for_manual_sell.assert_called_once()
        # Should remove from tracking
        assert 'RELIANCE' not in sell_manager.active_sell_orders
    
    def test_handle_manual_sells_partial_exit(self, sell_manager):
        """Test _handle_manual_sells with partial exit"""
        sell_manager.active_sell_orders = {
            'RELIANCE': {'order_id': '99999', 'qty': 10}
        }
        
        # Manual sell info (sold partial shares)
        manual_sells = {
            'RELIANCE': {
                'qty': 5,
                'orders': [{'order_id': '12345', 'qty': 5, 'price': 2500.0}]
            }
        }
        
        sell_manager.orders.cancel_order = Mock()
        sell_manager._update_trade_history_for_manual_sell = Mock()
        
        sell_manager._handle_manual_sells(manual_sells)
        
        # Should cancel bot order
        sell_manager.orders.cancel_order.assert_called_once()
        # Should update trade history
        sell_manager._update_trade_history_for_manual_sell.assert_called_once()
        # Should remove from tracking
        assert 'RELIANCE' not in sell_manager.active_sell_orders
    
    def test_cancel_bot_order_for_manual_sell(self, sell_manager):
        """Test _cancel_bot_order_for_manual_sell"""
        order_info = {'order_id': '12345'}
        sell_manager.orders.cancel_order = Mock()
        
        sell_manager._cancel_bot_order_for_manual_sell('RELIANCE', order_info)
        
        sell_manager.orders.cancel_order.assert_called_once_with('12345')
    
    def test_cancel_bot_order_no_order_id(self, sell_manager):
        """Test _cancel_bot_order_for_manual_sell with no order_id"""
        order_info = {}  # No order_id
        sell_manager.orders.cancel_order = Mock()
        
        sell_manager._cancel_bot_order_for_manual_sell('RELIANCE', order_info)
        
        # Should not call cancel_order
        sell_manager.orders.cancel_order.assert_not_called()
    
    def test_mark_trade_as_closed(self, sell_manager):
        """Test _mark_trade_as_closed"""
        trade = {'entry_price': 2000.0, 'status': 'open'}
        sell_info = {
            'orders': [
                {'qty': 5, 'price': 2500.0},
                {'qty': 5, 'price': 2550.0}
            ]
        }
        sold_qty = 10
        
        sell_manager._mark_trade_as_closed(trade, sell_info, sold_qty, 'MANUAL_EXIT')
        
        assert trade['status'] == 'closed'
        assert trade['exit_reason'] == 'MANUAL_EXIT'
        assert trade['exit_price'] == 2525.0  # Average of (2500*5 + 2550*5) / 10
        assert trade['pnl'] == 5250.0  # (2525 - 2000) * 10
        assert abs(trade['pnl_pct'] - 26.25) < 0.01  # ((2525/2000) - 1) * 100
    
    def test_calculate_avg_price_from_orders(self, sell_manager):
        """Test _calculate_avg_price_from_orders"""
        orders = [
            {'qty': 5, 'price': 2500.0},
            {'qty': 5, 'price': 2550.0}
        ]
        
        avg_price = sell_manager._calculate_avg_price_from_orders(orders)
        
        assert avg_price == 2525.0  # (2500*5 + 2550*5) / 10
    
    def test_calculate_avg_price_empty_list(self, sell_manager):
        """Test _calculate_avg_price_from_orders with empty list"""
        avg_price = sell_manager._calculate_avg_price_from_orders([])
        assert avg_price == 0.0
    
    def test_find_order_in_broker_orders(self, sell_manager):
        """Test _find_order_in_broker_orders"""
        broker_orders = [
            {'nOrdNo': '12345', 'trdSym': 'RELIANCE-EQ'},
            {'nOrdNo': '67890', 'trdSym': 'TCS-EQ'},
            {'orderId': '99999', 'trdSym': 'INFY-EQ'}
        ]
        
        result = sell_manager._find_order_in_broker_orders('12345', broker_orders)
        assert result is not None
        assert result['nOrdNo'] == '12345'
        
        result = sell_manager._find_order_in_broker_orders('99999', broker_orders)
        assert result is not None
        assert result['orderId'] == '99999'
        
        result = sell_manager._find_order_in_broker_orders('00000', broker_orders)
        assert result is None
    
    def test_remove_from_tracking(self, sell_manager):
        """Test _remove_from_tracking"""
        sell_manager.active_sell_orders = {
            'RELIANCE': {'order_id': '12345'},
            'TCS': {'order_id': '67890'}
        }
        sell_manager.lowest_ema9 = {
            'RELIANCE': 2500.0,
            'TCS': 3000.0
        }
        
        sell_manager._remove_from_tracking('RELIANCE')
        
        assert 'RELIANCE' not in sell_manager.active_sell_orders
        assert 'RELIANCE' not in sell_manager.lowest_ema9
        assert 'TCS' in sell_manager.active_sell_orders
        assert 'TCS' in sell_manager.lowest_ema9
    
    def test_remove_rejected_orders(self, sell_manager):
        """Test _remove_rejected_orders"""
        sell_manager.active_sell_orders = {
            'RELIANCE': {'order_id': '12345'},
            'TCS': {'order_id': '67890'}
        }
        
        # Mock broker orders
        broker_orders = {
            'data': [
                {'nOrdNo': '12345', 'ordSt': 'rejected'},
                {'nOrdNo': '67890', 'ordSt': 'open'}
            ]
        }
        sell_manager.orders.get_orders.return_value = broker_orders
        
        sell_manager._remove_rejected_orders()
        
        # RELIANCE should be removed (rejected)
        assert 'RELIANCE' not in sell_manager.active_sell_orders
        # TCS should remain (not rejected)
        assert 'TCS' in sell_manager.active_sell_orders
    
    def test_remove_rejected_orders_cancelled(self, sell_manager):
        """Test _remove_rejected_orders with cancelled orders"""
        sell_manager.active_sell_orders = {
            'RELIANCE': {'order_id': '12345'}
        }
        
        broker_orders = {
            'data': [
                {'nOrdNo': '12345', 'ordSt': 'cancelled'}
            ]
        }
        sell_manager.orders.get_orders.return_value = broker_orders
        
        sell_manager._remove_rejected_orders()
        
        assert 'RELIANCE' not in sell_manager.active_sell_orders
    
    def test_detect_and_handle_manual_buys(self, sell_manager):
        """Test _detect_and_handle_manual_buys"""
        with patch('modules.kotak_neo_auto_trader.storage.check_manual_buys_of_failed_orders') as mock_check:
            mock_check.return_value = ['RELIANCE', 'TCS']
            
            result = sell_manager._detect_and_handle_manual_buys()
            
            assert result == ['RELIANCE', 'TCS']
            mock_check.assert_called_once_with(
                sell_manager.history_path,
                sell_manager.orders
            )
    
    def test_detect_and_handle_manual_buys_empty(self, sell_manager):
        """Test _detect_and_handle_manual_buys with no manual buys"""
        with patch('modules.kotak_neo_auto_trader.storage.check_manual_buys_of_failed_orders') as mock_check:
            mock_check.return_value = []
            
            result = sell_manager._detect_and_handle_manual_buys()
            
            assert result == []
    
    def test_cleanup_rejected_orders_integration(self, sell_manager):
        """Test _cleanup_rejected_orders integration"""
        # Setup
        sell_manager.active_sell_orders = {
            'RELIANCE': {'order_id': '12345', 'qty': 10}
        }
        
        # Mock all dependencies
        with patch.object(sell_manager, '_detect_and_handle_manual_buys') as mock_detect_buys, \
             patch.object(sell_manager, '_detect_manual_sells') as mock_detect_sells, \
             patch.object(sell_manager, '_handle_manual_sells') as mock_handle_sells, \
             patch.object(sell_manager, '_remove_rejected_orders') as mock_remove_rejected:
            
            mock_detect_buys.return_value = []
            mock_detect_sells.return_value = {}
            
            sell_manager._cleanup_rejected_orders()
            
            # Verify all methods called
            mock_detect_buys.assert_called_once()
            mock_detect_sells.assert_called_once()
            mock_remove_rejected.assert_called_once()
            # Should not call handle_manual_sells (empty dict)
            mock_handle_sells.assert_not_called()
    
    def test_cleanup_rejected_orders_with_manual_sells(self, sell_manager):
        """Test _cleanup_rejected_orders with manual sells detected"""
        with patch.object(sell_manager, '_detect_and_handle_manual_buys') as mock_detect_buys, \
             patch.object(sell_manager, '_detect_manual_sells') as mock_detect_sells, \
             patch.object(sell_manager, '_handle_manual_sells') as mock_handle_sells, \
             patch.object(sell_manager, '_remove_rejected_orders') as mock_remove_rejected:
            
            mock_detect_buys.return_value = []
            mock_detect_sells.return_value = {'RELIANCE': {'qty': 5, 'orders': []}}
            
            sell_manager._cleanup_rejected_orders()
            
            # Should call handle_manual_sells
            mock_handle_sells.assert_called_once_with({'RELIANCE': {'qty': 5, 'orders': []}})
    
    def test_get_active_orders_initializes_lowest_ema9_from_target_price(self, sell_manager):
        """Test that _get_active_orders initializes lowest_ema9 from target_price when syncing from OrderStateManager"""
        # Setup OrderStateManager mock
        mock_state_manager = Mock()
        mock_state_manager.get_active_sell_orders.return_value = {
            'DALBHARAT': {
                'order_id': '251106000008974',
                'target_price': 2095.53,
                'qty': 233,
                'ticker': 'DALBHARAT.NS'
            },
            'RELIANCE': {
                'order_id': '12345',
                'target_price': 2500.0,
                'qty': 10,
                'ticker': 'RELIANCE.NS'
            }
        }
        sell_manager.state_manager = mock_state_manager
        sell_manager.lowest_ema9 = {}  # Empty initially
        
        # Call _get_active_orders
        result = sell_manager._get_active_orders()
        
        # Verify orders synced
        assert 'DALBHARAT' in result
        assert 'RELIANCE' in result
        
        # Verify lowest_ema9 initialized from target_price
        assert sell_manager.lowest_ema9['DALBHARAT'] == 2095.53
        assert sell_manager.lowest_ema9['RELIANCE'] == 2500.0
    
    def test_get_active_orders_skips_zero_target_price(self, sell_manager):
        """Test that _get_active_orders skips initializing lowest_ema9 when target_price is 0"""
        mock_state_manager = Mock()
        mock_state_manager.get_active_sell_orders.return_value = {
            'DALBHARAT': {
                'order_id': '251106000008974',
                'target_price': 0.0,  # Zero price from duplicate bug
                'qty': 233,
                'ticker': 'DALBHARAT.NS'
            }
        }
        sell_manager.state_manager = mock_state_manager
        sell_manager.lowest_ema9 = {}
        
        result = sell_manager._get_active_orders()
        
        # Order should be synced
        assert 'DALBHARAT' in result
        
        # But lowest_ema9 should NOT be initialized (target_price is 0)
        assert 'DALBHARAT' not in sell_manager.lowest_ema9
    
    def test_check_and_update_single_stock_initializes_lowest_ema9_from_target_price(self, sell_manager):
        """Test that _check_and_update_single_stock initializes lowest_ema9 from target_price if not set"""
        order_info = {
            'order_id': '12345',
            'target_price': 2095.53,
            'qty': 233,
            'ticker': 'DALBHARAT.NS',
            'placed_symbol': 'DALBHARAT-EQ'
        }
        sell_manager.lowest_ema9 = {}  # Empty initially
        
        # Mock get_current_ema9
        with patch.object(sell_manager, 'get_current_ema9', return_value=2095.27), \
             patch.object(sell_manager, 'round_to_tick_size', return_value=2095.30), \
             patch.object(sell_manager, 'update_sell_order', return_value=False):
            
            result = sell_manager._check_and_update_single_stock('DALBHARAT', order_info, [])
            
            # Verify lowest_ema9 initialized from target_price
            assert sell_manager.lowest_ema9['DALBHARAT'] == 2095.53
    
    def test_check_and_update_single_stock_initializes_lowest_ema9_from_current_ema9_when_target_zero(self, sell_manager):
        """Test that _check_and_update_single_stock initializes lowest_ema9 from current EMA9 when target_price is 0"""
        order_info = {
            'order_id': '251106000008974',
            'target_price': 0.0,  # Zero price from duplicate bug
            'qty': 233,
            'ticker': 'DALBHARAT.NS',
            'placed_symbol': 'DALBHARAT-EQ'
        }
        sell_manager.lowest_ema9 = {}  # Empty initially
        
        current_ema9 = 2095.27
        rounded_ema9 = 2095.30
        
        # Mock get_current_ema9
        with patch.object(sell_manager, 'get_current_ema9', return_value=current_ema9), \
             patch.object(sell_manager, 'round_to_tick_size', return_value=rounded_ema9), \
             patch.object(sell_manager, 'update_sell_order', return_value=False):
            
            result = sell_manager._check_and_update_single_stock('DALBHARAT', order_info, [])
            
            # Verify lowest_ema9 initialized from current EMA9 (not target_price)
            assert sell_manager.lowest_ema9['DALBHARAT'] == rounded_ema9
    
    def test_check_and_update_single_stock_handles_zero_target_price_display(self, sell_manager):
        """Test that _check_and_update_single_stock handles zero target_price for display"""
        order_info = {
            'order_id': '251106000008974',
            'target_price': 0.0,  # Zero price
            'qty': 233,
            'ticker': 'DALBHARAT.NS',
            'placed_symbol': 'DALBHARAT-EQ'
        }
        sell_manager.lowest_ema9 = {'DALBHARAT': 2095.30}  # Already initialized
        
        current_ema9 = 2095.27
        rounded_ema9 = 2095.30
        
        with patch.object(sell_manager, 'get_current_ema9', return_value=current_ema9), \
             patch.object(sell_manager, 'round_to_tick_size', return_value=rounded_ema9), \
             patch.object(sell_manager, 'update_sell_order', return_value=False), \
             patch('modules.kotak_neo_auto_trader.sell_engine.logger') as mock_logger:
            
            result = sell_manager._check_and_update_single_stock('DALBHARAT', order_info, [])
            
            # Verify log was called with correct values
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            # Should show Target=2095.30 (from lowest_ema9), not 0.0
            assert any('Target=₹2095.30' in str(call) for call in log_calls)
            assert any('Lowest=₹2095.30' in str(call) for call in log_calls)
    
    def test_check_and_update_single_stock_handles_missing_target_price(self, sell_manager):
        """Test that _check_and_update_single_stock handles missing target_price"""
        order_info = {
            'order_id': '12345',
            # No target_price key
            'qty': 10,
            'ticker': 'RELIANCE.NS',
            'placed_symbol': 'RELIANCE-EQ'
        }
        sell_manager.lowest_ema9 = {}  # Empty initially
        
        current_ema9 = 2500.0
        rounded_ema9 = 2500.0
        
        with patch.object(sell_manager, 'get_current_ema9', return_value=current_ema9), \
             patch.object(sell_manager, 'round_to_tick_size', return_value=rounded_ema9), \
             patch.object(sell_manager, 'update_sell_order', return_value=False):
            
            result = sell_manager._check_and_update_single_stock('RELIANCE', order_info, [])
            
            # Verify lowest_ema9 initialized from current EMA9
            assert sell_manager.lowest_ema9['RELIANCE'] == rounded_ema9
    
    def test_check_and_update_single_stock_preserves_existing_lowest_ema9(self, sell_manager):
        """Test that _check_and_update_single_stock doesn't overwrite existing lowest_ema9"""
        order_info = {
            'order_id': '12345',
            'target_price': 2500.0,
            'qty': 10,
            'ticker': 'RELIANCE.NS',
            'placed_symbol': 'RELIANCE-EQ'
        }
        # Already has lower value
        sell_manager.lowest_ema9 = {'RELIANCE': 2480.0}
        
        current_ema9 = 2500.0
        rounded_ema9 = 2500.0
        
        with patch.object(sell_manager, 'get_current_ema9', return_value=current_ema9), \
             patch.object(sell_manager, 'round_to_tick_size', return_value=rounded_ema9), \
             patch.object(sell_manager, 'update_sell_order', return_value=False):
            
            result = sell_manager._check_and_update_single_stock('RELIANCE', order_info, [])
            
            # Verify existing lowest_ema9 preserved (not overwritten)
            assert sell_manager.lowest_ema9['RELIANCE'] == 2480.0
