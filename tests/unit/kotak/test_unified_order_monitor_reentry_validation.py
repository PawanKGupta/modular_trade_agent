"""
Tests for reentry data validation in UnifiedOrderMonitor.

Tests that _validate_reentry_data() correctly validates reentry data structure
before writing to database.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.unified_order_monitor import UnifiedOrderMonitor  # noqa: E402


class TestReentryDataValidation:
    """Test reentry data validation"""

    @pytest.fixture
    def sell_manager(self):
        """Create a mock SellOrderManager"""
        manager = Mock()
        manager.get_existing_sell_orders = Mock(return_value={})
        return manager

    @pytest.fixture
    def unified_monitor(self, sell_manager):
        """Create UnifiedOrderMonitor instance"""
        monitor = UnifiedOrderMonitor(sell_order_manager=sell_manager, user_id=1)
        return monitor

    def test_validate_reentry_data_valid(self, unified_monitor):
        """Test that valid reentry data passes validation"""
        valid_data = {
            "qty": 10,
            "level": 20,
            "rsi": 19.5,
            "price": 2500.0,
            "time": datetime.now().isoformat(),
            "order_id": "ORDER123",
        }

        assert unified_monitor._validate_reentry_data(valid_data) is True

    def test_validate_reentry_data_missing_qty(self, unified_monitor):
        """Test that missing qty field fails validation"""
        invalid_data = {
            "price": 2500.0,
            "time": datetime.now().isoformat(),
        }

        assert unified_monitor._validate_reentry_data(invalid_data) is False

    def test_validate_reentry_data_missing_price(self, unified_monitor):
        """Test that missing price field fails validation"""
        invalid_data = {
            "qty": 10,
            "time": datetime.now().isoformat(),
        }

        assert unified_monitor._validate_reentry_data(invalid_data) is False

    def test_validate_reentry_data_missing_time(self, unified_monitor):
        """Test that missing time field fails validation"""
        invalid_data = {
            "qty": 10,
            "price": 2500.0,
        }

        assert unified_monitor._validate_reentry_data(invalid_data) is False

    def test_validate_reentry_data_invalid_qty_type(self, unified_monitor):
        """Test that invalid qty type fails validation"""
        invalid_data = {
            "qty": "10",  # String instead of int
            "price": 2500.0,
            "time": datetime.now().isoformat(),
        }

        assert unified_monitor._validate_reentry_data(invalid_data) is False

    def test_validate_reentry_data_invalid_qty_value(self, unified_monitor):
        """Test that negative or zero qty fails validation"""
        invalid_data = {
            "qty": 0,  # Zero qty
            "price": 2500.0,
            "time": datetime.now().isoformat(),
        }

        assert unified_monitor._validate_reentry_data(invalid_data) is False

        invalid_data["qty"] = -5  # Negative qty
        assert unified_monitor._validate_reentry_data(invalid_data) is False

    def test_validate_reentry_data_invalid_price_type(self, unified_monitor):
        """Test that invalid price type fails validation"""
        invalid_data = {
            "qty": 10,
            "price": "2500.0",  # String instead of number
            "time": datetime.now().isoformat(),
        }

        assert unified_monitor._validate_reentry_data(invalid_data) is False

    def test_validate_reentry_data_invalid_price_value(self, unified_monitor):
        """Test that negative or zero price fails validation"""
        invalid_data = {
            "qty": 10,
            "price": 0.0,  # Zero price
            "time": datetime.now().isoformat(),
        }

        assert unified_monitor._validate_reentry_data(invalid_data) is False

        invalid_data["price"] = -100.0  # Negative price
        assert unified_monitor._validate_reentry_data(invalid_data) is False

    def test_validate_reentry_data_invalid_time_format(self, unified_monitor):
        """Test that invalid time format fails validation"""
        invalid_data = {
            "qty": 10,
            "price": 2500.0,
            "time": "invalid-date",  # Invalid format
        }

        assert unified_monitor._validate_reentry_data(invalid_data) is False

    def test_validate_reentry_data_invalid_time_type(self, unified_monitor):
        """Test that invalid time type fails validation"""
        invalid_data = {
            "qty": 10,
            "price": 2500.0,
            "time": datetime.now(),  # datetime object instead of string
        }

        assert unified_monitor._validate_reentry_data(invalid_data) is False

    def test_validate_reentry_data_optional_fields_allowed(self, unified_monitor):
        """Test that optional fields (level, rsi, order_id) don't affect validation"""
        valid_data = {
            "qty": 10,
            "price": 2500.0,
            "time": datetime.now().isoformat(),
            # Optional fields can be None or missing
            "level": None,
            "rsi": None,
        }

        assert unified_monitor._validate_reentry_data(valid_data) is True

        # Also valid with optional fields present
        valid_data["level"] = 20
        valid_data["rsi"] = 19.5
        valid_data["order_id"] = "ORDER123"
        assert unified_monitor._validate_reentry_data(valid_data) is True

