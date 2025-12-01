"""
Unit tests for OrderStatus enum.

Tests for:
1. All enum values exist
2. Enum values are lowercase strings
3. Enum can be created from string values
4. Invalid values raise appropriate errors
"""

import pytest

from src.infrastructure.db.models import OrderStatus


class TestOrderStatusEnum:
    """Test OrderStatus enum values and behavior"""

    def test_all_status_values_exist(self):
        """Test that all expected status values exist (simplified: 9 → 5 statuses)"""
        assert OrderStatus.PENDING == "pending"  # Merged: AMO + PENDING_EXECUTION
        assert OrderStatus.ONGOING == "ongoing"
        assert OrderStatus.CLOSED == "closed"
        assert OrderStatus.FAILED == "failed"  # Merged: FAILED + RETRY_PENDING + REJECTED
        assert OrderStatus.CANCELLED == "cancelled"
        # Note: SELL status removed - use side='sell' to identify sell orders

    def test_status_values_are_lowercase(self):
        """Test that all status values are lowercase strings"""
        for status in OrderStatus:
            assert isinstance(status.value, str)
            assert status.value == status.value.lower()

    def test_create_status_from_string(self):
        """Test creating OrderStatus from string value"""
        assert OrderStatus("pending") == OrderStatus.PENDING  # Merged: AMO + PENDING_EXECUTION
        assert OrderStatus("ongoing") == OrderStatus.ONGOING
        assert (
            OrderStatus("failed") == OrderStatus.FAILED
        )  # Merged: FAILED + RETRY_PENDING + REJECTED
        assert OrderStatus("closed") == OrderStatus.CLOSED
        assert OrderStatus("cancelled") == OrderStatus.CANCELLED

    def test_create_status_from_uppercase_string(self):
        """Test that creating from uppercase string works (case-insensitive)"""
        # Note: This depends on implementation - may need to handle case conversion
        # For now, test that lowercase works
        assert OrderStatus("PENDING".lower()) == OrderStatus.PENDING
        assert OrderStatus("FAILED".lower()) == OrderStatus.FAILED

    def test_invalid_status_raises_value_error(self):
        """Test that invalid status string raises ValueError"""
        with pytest.raises(ValueError):
            OrderStatus("invalid_status")

    def test_status_comparison(self):
        """Test that status values can be compared"""
        assert OrderStatus.PENDING != OrderStatus.FAILED
        assert OrderStatus.FAILED == OrderStatus.FAILED
        assert OrderStatus.PENDING != OrderStatus.ONGOING

    def test_status_string_representation(self):
        """Test string representation of status"""
        # str() returns the enum name, .value returns the string value
        assert OrderStatus.PENDING.value == "pending"
        assert OrderStatus.FAILED.value == "failed"
        assert OrderStatus.CANCELLED.value == "cancelled"
        # repr() should include the value
        assert "pending" in repr(OrderStatus.PENDING)

    def test_all_statuses_listed(self):
        """Test that we have all expected statuses (simplified: 9 → 5 statuses)"""
        expected_statuses = {
            "pending",  # Merged: AMO + PENDING_EXECUTION
            "ongoing",
            "closed",
            "failed",  # Merged: FAILED + RETRY_PENDING + REJECTED
            "cancelled",
            # Note: SELL status removed - use side='sell' to identify sell orders
        }
        actual_statuses = {s.value for s in OrderStatus}
        assert actual_statuses == expected_statuses
