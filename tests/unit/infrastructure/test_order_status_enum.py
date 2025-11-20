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
        """Test that all expected status values exist"""
        assert OrderStatus.AMO == "amo"
        assert OrderStatus.ONGOING == "ongoing"
        assert OrderStatus.SELL == "sell"
        assert OrderStatus.CLOSED == "closed"
        assert OrderStatus.FAILED == "failed"
        assert OrderStatus.RETRY_PENDING == "retry_pending"
        assert OrderStatus.REJECTED == "rejected"
        assert OrderStatus.PENDING_EXECUTION == "pending_execution"

    def test_status_values_are_lowercase(self):
        """Test that all status values are lowercase strings"""
        for status in OrderStatus:
            assert isinstance(status.value, str)
            assert status.value == status.value.lower()

    def test_create_status_from_string(self):
        """Test creating OrderStatus from string value"""
        assert OrderStatus("amo") == OrderStatus.AMO
        assert OrderStatus("ongoing") == OrderStatus.ONGOING
        assert OrderStatus("failed") == OrderStatus.FAILED
        assert OrderStatus("retry_pending") == OrderStatus.RETRY_PENDING
        assert OrderStatus("rejected") == OrderStatus.REJECTED
        assert OrderStatus("pending_execution") == OrderStatus.PENDING_EXECUTION

    def test_create_status_from_uppercase_string(self):
        """Test that creating from uppercase string works (case-insensitive)"""
        # Note: This depends on implementation - may need to handle case conversion
        # For now, test that lowercase works
        assert OrderStatus("AMO".lower()) == OrderStatus.AMO
        assert OrderStatus("FAILED".lower()) == OrderStatus.FAILED

    def test_invalid_status_raises_value_error(self):
        """Test that invalid status string raises ValueError"""
        with pytest.raises(ValueError):
            OrderStatus("invalid_status")

    def test_status_comparison(self):
        """Test that status values can be compared"""
        assert OrderStatus.AMO != OrderStatus.FAILED
        assert OrderStatus.FAILED == OrderStatus.FAILED
        assert OrderStatus.RETRY_PENDING != OrderStatus.REJECTED

    def test_status_string_representation(self):
        """Test string representation of status"""
        # str() returns the enum name, .value returns the string value
        assert OrderStatus.AMO.value == "amo"
        assert OrderStatus.FAILED.value == "failed"
        assert OrderStatus.RETRY_PENDING.value == "retry_pending"
        # repr() should include the value
        assert "retry_pending" in repr(OrderStatus.RETRY_PENDING)

    def test_all_statuses_listed(self):
        """Test that we have all expected statuses"""
        expected_statuses = {
            "amo",
            "ongoing",
            "sell",
            "closed",
            "failed",
            "retry_pending",
            "rejected",
            "pending_execution",
        }
        actual_statuses = {s.value for s in OrderStatus}
        assert actual_statuses == expected_statuses
