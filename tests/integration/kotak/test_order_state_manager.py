#!/usr/bin/env python3
"""
Tests for OrderStateManager unified state management
"""

import pytest
import sys
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.order_state_manager import OrderStateManager


class TestOrderStateManager:
    """Test OrderStateManager unified state management"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def history_path(self, temp_dir):
        """Create temporary history file"""
        path = os.path.join(temp_dir, "trades_history.json")
        with open(path, 'w') as f:
            json.dump({"trades": [], "failed_orders": []}, f)
        return path
    
    @pytest.fixture
    def state_manager(self, history_path, temp_dir):
        """Create OrderStateManager instance"""
        return OrderStateManager(history_path=history_path, data_dir=temp_dir)
    
    def test_register_sell_order(self, state_manager):
        """Test registering a sell order"""
        result = state_manager.register_sell_order(
            symbol="RELIANCE-EQ",
            order_id="12345",
            target_price=2500.0,
            qty=10,
            ticker="RELIANCE.NS"
        )
        
        assert result is True
        assert "RELIANCE" in state_manager.active_sell_orders
        assert state_manager.active_sell_orders["RELIANCE"]["order_id"] == "12345"
        assert state_manager.active_sell_orders["RELIANCE"]["target_price"] == 2500.0
        assert state_manager.active_sell_orders["RELIANCE"]["qty"] == 10
    
    def test_update_sell_order_price(self, state_manager):
        """Test updating sell order price"""
        state_manager.register_sell_order(
            symbol="RELIANCE",
            order_id="12345",
            target_price=2500.0,
            qty=10
        )
        
        result = state_manager.update_sell_order_price("RELIANCE", 2550.0)
        
        assert result is True
        assert state_manager.active_sell_orders["RELIANCE"]["target_price"] == 2550.0
    
    def test_get_active_sell_orders(self, state_manager):
        """Test getting all active sell orders"""
        state_manager.register_sell_order("RELIANCE", "12345", 2500.0, 10)
        state_manager.register_sell_order("DALBHARAT", "67890", 2100.0, 5)
        
        orders = state_manager.get_active_sell_orders()
        
        assert len(orders) == 2
        assert "RELIANCE" in orders
        assert "DALBHARAT" in orders
    
    def test_get_active_order(self, state_manager):
        """Test getting a specific active order"""
        state_manager.register_sell_order("RELIANCE", "12345", 2500.0, 10)
        
        order = state_manager.get_active_order("RELIANCE")
        
        assert order is not None
        assert order["order_id"] == "12345"
        
        # Test with non-existent symbol
        order = state_manager.get_active_order("NONEXISTENT")
        assert order is None
    
    def test_mark_order_executed(self, state_manager):
        """Test marking order as executed"""
        state_manager.register_sell_order(
            symbol="RELIANCE",
            order_id="12345",
            target_price=2500.0,
            qty=10,
            ticker="RELIANCE.NS"
        )
        
        result = state_manager.mark_order_executed(
            symbol="RELIANCE",
            order_id="12345",
            execution_price=2505.0,
            execution_qty=10
        )
        
        assert result is True
        assert "RELIANCE" not in state_manager.active_sell_orders
    
    def test_remove_from_tracking(self, state_manager):
        """Test removing order from tracking"""
        state_manager.register_sell_order("RELIANCE", "12345", 2500.0, 10)
        
        result = state_manager.remove_from_tracking("RELIANCE", reason="Rejected")
        
        assert result is True
        assert "RELIANCE" not in state_manager.active_sell_orders
    
    def test_remove_from_tracking_not_found(self, state_manager):
        """Test removing non-existent order"""
        result = state_manager.remove_from_tracking("NONEXISTENT")
        assert result is False
    
    def test_sync_with_broker_executed(self, state_manager):
        """Test syncing with broker when order is executed"""
        state_manager.register_sell_order("RELIANCE", "12345", 2500.0, 10)
        
        broker_orders = [
            {
                'neoOrdNo': '12345',
                'trdSym': 'RELIANCE-EQ',
                'orderStatus': 'complete',
                'transactionType': 'SELL',
                'avgPrc': 2505.0,
                'qty': 10
            }
        ]
        
        mock_orders_api = Mock()
        stats = state_manager.sync_with_broker(mock_orders_api, broker_orders=broker_orders)
        
        assert stats['checked'] == 1
        assert stats['executed'] == 1
        assert "RELIANCE" not in state_manager.active_sell_orders
    
    def test_sync_with_broker_rejected(self, state_manager):
        """Test syncing with broker when order is rejected"""
        state_manager.register_sell_order("RELIANCE", "12345", 2500.0, 10)
        
        broker_orders = [
            {
                'neoOrdNo': '12345',
                'trdSym': 'RELIANCE-EQ',
                'orderStatus': 'rejected',
                'transactionType': 'SELL',
                'rejectionReason': 'Insufficient balance'
            }
        ]
        
        mock_orders_api = Mock()
        stats = state_manager.sync_with_broker(mock_orders_api, broker_orders=broker_orders)
        
        assert stats['checked'] == 1
        assert stats['rejected'] == 1
        assert "RELIANCE" not in state_manager.active_sell_orders
    
    def test_sync_with_broker_cancelled(self, state_manager):
        """Test syncing with broker when order is cancelled"""
        state_manager.register_sell_order("RELIANCE", "12345", 2500.0, 10)
        
        broker_orders = [
            {
                'neoOrdNo': '12345',
                'trdSym': 'RELIANCE-EQ',
                'orderStatus': 'cancelled',
                'transactionType': 'SELL'
            }
        ]
        
        mock_orders_api = Mock()
        stats = state_manager.sync_with_broker(mock_orders_api, broker_orders=broker_orders)
        
        assert stats['checked'] == 1
        assert stats['cancelled'] == 1
        assert "RELIANCE" not in state_manager.active_sell_orders
    
    def test_get_pending_orders(self, state_manager):
        """Test getting pending orders"""
        state_manager.register_sell_order(
            symbol="RELIANCE",
            order_id="12345",
            target_price=2500.0,
            qty=10,
            ticker="RELIANCE.NS"
        )
        
        pending = state_manager.get_pending_orders()
        
        assert len(pending) >= 1
        assert any(o['order_id'] == '12345' for o in pending)
    
    def test_thread_safety(self, state_manager):
        """Test thread safety of operations"""
        import threading
        
        results = []
        
        def register_order(symbol, order_id):
            result = state_manager.register_sell_order(symbol, order_id, 2500.0, 10)
            results.append(result)
        
        threads = []
        for i in range(10):
            thread = threading.Thread(target=register_order, args=(f"SYMBOL{i}", f"ORDER{i}"))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All operations should succeed
        assert all(results)
        assert len(state_manager.active_sell_orders) == 10
    
    def test_get_trade_history(self, state_manager, history_path):
        """Test getting trade history"""
        history = state_manager.get_trade_history()
        
        assert isinstance(history, dict)
        assert 'trades' in history
        assert 'failed_orders' in history

