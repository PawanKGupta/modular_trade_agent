#!/usr/bin/env python3
"""
Tests for OrderTracker duplicate prevention
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.order_tracker import OrderTracker


class TestOrderTrackerDuplicatePrevention:
    """Test OrderTracker duplicate prevention"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def order_tracker(self, temp_dir):
        """Create OrderTracker instance"""
        return OrderTracker(data_dir=temp_dir)

    def test_add_pending_order_duplicate_prevention(self, order_tracker):
        """Test that duplicate orders are not added"""
        # Add order first time
        order_tracker.add_pending_order(
            order_id="251106000008974",
            symbol="DALBHARAT",
            ticker="DALBHARAT.NS",
            qty=233,
            order_type="LIMIT",
            variety="REGULAR",
            price=2095.53,
        )

        # Verify order was added
        pending = order_tracker.get_pending_orders()
        assert len(pending) == 1
        assert pending[0]["order_id"] == "251106000008974"
        assert pending[0]["price"] == 2095.53

        # Try to add same order again
        with patch("modules.kotak_neo_auto_trader.order_tracker.logger") as mock_logger:
            order_tracker.add_pending_order(
                order_id="251106000008974",
                symbol="DALBHARAT",
                ticker="DALBHARAT.NS",
                qty=233,
                order_type="LIMIT",
                variety="REGULAR",
                price=0.0,  # Different price, but same order_id
            )

            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            warning_call = str(mock_logger.warning.call_args)
            assert "already exists" in warning_call.lower()
            assert "251106000008974" in warning_call

        # Verify no duplicate was added
        pending = order_tracker.get_pending_orders()
        assert len(pending) == 1, "Duplicate order should not be added"
        assert pending[0]["order_id"] == "251106000008974"
        # Original price should be preserved
        assert pending[0]["price"] == 2095.53

    def test_add_pending_order_multiple_duplicates(self, order_tracker):
        """Test that multiple duplicate attempts are prevented"""
        # Add order first time
        order_tracker.add_pending_order(
            order_id="12345", symbol="RELIANCE", ticker="RELIANCE.NS", qty=10, price=2500.0
        )

        # Try to add same order multiple times
        for i in range(3):
            order_tracker.add_pending_order(
                order_id="12345",
                symbol="RELIANCE",
                ticker="RELIANCE.NS",
                qty=10,
                price=2500.0 + i,  # Different prices each time
            )

        # Verify only one order exists
        pending = order_tracker.get_pending_orders()
        assert len(pending) == 1
        assert pending[0]["order_id"] == "12345"
        assert pending[0]["price"] == 2500.0  # Original price preserved

    def test_add_pending_order_different_order_ids(self, order_tracker):
        """Test that different order IDs can coexist"""
        # Add first order
        order_tracker.add_pending_order(
            order_id="11111", symbol="RELIANCE", ticker="RELIANCE.NS", qty=10, price=2500.0
        )

        # Add second order with different order_id
        order_tracker.add_pending_order(
            order_id="22222", symbol="RELIANCE", ticker="RELIANCE.NS", qty=10, price=2500.0
        )

        # Both should be added (different order_ids)
        pending = order_tracker.get_pending_orders()
        assert len(pending) == 2
        order_ids = [o["order_id"] for o in pending]
        assert "11111" in order_ids
        assert "22222" in order_ids

    def test_add_pending_order_same_symbol_different_order_id(self, order_tracker):
        """Test that same symbol with different order_id creates separate entries"""
        # Add order for DALBHARAT
        order_tracker.add_pending_order(
            order_id="251106000008974",
            symbol="DALBHARAT",
            ticker="DALBHARAT.NS",
            qty=233,
            price=2095.53,
        )

        # Add another order for same symbol but different order_id
        order_tracker.add_pending_order(
            order_id="251106000008975",  # Different order_id
            symbol="DALBHARAT",
            ticker="DALBHARAT.NS",
            qty=233,
            price=2095.53,
        )

        # Both should be added (different order_ids)
        pending = order_tracker.get_pending_orders()
        assert len(pending) == 2
        order_ids = [o["order_id"] for o in pending]
        assert "251106000008974" in order_ids
        assert "251106000008975" in order_ids

    def test_add_pending_order_duplicate_with_zero_price(self, order_tracker):
        """Test the specific bug scenario: duplicate with zero price"""
        # Add order with correct price (simulating initial placement)
        order_tracker.add_pending_order(
            order_id="251106000008974",
            symbol="DALBHARAT",
            ticker="DALBHARAT.NS",
            qty=233,
            order_type="LIMIT",
            variety="REGULAR",
            price=2095.53,
        )

        # Try to add duplicate with zero price (simulating re-registration bug)
        with patch("modules.kotak_neo_auto_trader.order_tracker.logger") as mock_logger:
            order_tracker.add_pending_order(
                order_id="251106000008974",
                symbol="DALBHARAT",
                ticker="DALBHARAT.NS",
                qty=233,
                order_type="LIMIT",
                variety="REGULAR",
                price=0.0,  # Zero price from bug scenario
            )

            # Should log warning
            assert mock_logger.warning.called

        # Verify original price preserved
        pending = order_tracker.get_pending_orders()
        assert len(pending) == 1
        assert pending[0]["price"] == 2095.53, "Original price should be preserved"

    def test_add_pending_order_after_removal(self, order_tracker):
        """Test that order can be added again after removal"""
        # Add order
        order_tracker.add_pending_order(
            order_id="12345", symbol="RELIANCE", ticker="RELIANCE.NS", qty=10, price=2500.0
        )

        # Remove order
        order_tracker.remove_pending_order("12345")

        # Verify removed
        pending = order_tracker.get_pending_orders()
        assert len(pending) == 0

        # Add same order_id again (should work after removal)
        order_tracker.add_pending_order(
            order_id="12345", symbol="RELIANCE", ticker="RELIANCE.NS", qty=10, price=2500.0
        )

        # Should be added successfully
        pending = order_tracker.get_pending_orders()
        assert len(pending) == 1
        assert pending[0]["order_id"] == "12345"
