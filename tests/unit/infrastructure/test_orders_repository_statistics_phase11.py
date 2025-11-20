"""
Tests for Phase 11: Order Statistics in OrdersRepository

Tests order status distribution and statistics methods.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import text

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.db.models import OrderStatus
from src.infrastructure.persistence.orders_repository import OrdersRepository


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    return Mock()


@pytest.fixture
def sample_user():
    """Sample user for testing"""
    user = Mock()
    user.id = 1
    return user


class TestOrdersRepositoryStatisticsPhase11:
    """Test Phase 11 order statistics methods"""

    def test_get_order_status_distribution(self, mock_db_session):
        """Test getting order status distribution"""
        # Mock query results
        mock_results = [
            ("amo", 5),
            ("ongoing", 10),
            ("closed", 20),
            ("failed", 3),
            ("retry_pending", 2),
        ]

        # Mock the execute return value properly
        mock_result_obj = Mock()
        mock_result_obj.fetchall.return_value = mock_results
        mock_db_session.execute.return_value = mock_result_obj

        repo = OrdersRepository(mock_db_session)

        distribution = repo.get_order_status_distribution(user_id=1)

        # Verify query was executed
        mock_db_session.execute.assert_called_once()

        # Verify distribution
        assert distribution["amo"] == 5
        assert distribution["ongoing"] == 10
        assert distribution["closed"] == 20
        assert distribution["failed"] == 3
        assert distribution["retry_pending"] == 2

    def test_get_order_status_distribution_empty(self, mock_db_session):
        """Test getting order status distribution when no orders"""
        # Mock the execute return value properly
        mock_result_obj = Mock()
        mock_result_obj.fetchall.return_value = []
        mock_db_session.execute.return_value = mock_result_obj

        repo = OrdersRepository(mock_db_session)

        distribution = repo.get_order_status_distribution(user_id=1)

        # Verify distribution is empty
        assert distribution == {}

    def test_get_order_statistics(self, mock_db_session):
        """Test getting comprehensive order statistics"""
        # Mock status distribution results
        status_distribution_results = [
            ("amo", 5),
            ("ongoing", 10),
            ("closed", 20),
            ("failed", 3),
            ("retry_pending", 2),
            ("rejected", 1),
            ("cancelled", 4),
            ("pending_execution", 8),
        ]

        # Mock total count result
        total_count_result = [(53,)]  # Total of all counts

        # Create separate mock result objects
        mock_count_result = Mock()
        mock_count_result.fetchone.return_value = total_count_result[0]

        mock_distribution_result = Mock()
        mock_distribution_result.fetchall.return_value = status_distribution_results

        # Mock execute to return different results for different queries
        # get_order_statistics calls execute twice:
        # 1. First for total count (COUNT(*))
        # 2. Then get_order_status_distribution calls execute for status distribution (GROUP BY status)
        call_order = []

        def execute_side_effect(query, params):
            query_str = str(query)
            call_order.append(query_str)
            # Check for total count query (COUNT(*) without GROUP BY)
            if "COUNT(*)" in query_str and "GROUP BY" not in query_str:
                return mock_count_result
            # Check for status distribution query
            elif "GROUP BY status" in query_str:
                return mock_distribution_result
            return Mock()

        mock_db_session.execute.side_effect = execute_side_effect

        repo = OrdersRepository(mock_db_session)

        stats = repo.get_order_statistics(user_id=1)

        # Verify statistics
        assert stats["total_orders"] == 53
        assert stats["status_distribution"]["amo"] == 5
        assert stats["status_distribution"]["ongoing"] == 10
        assert stats["status_distribution"]["closed"] == 20
        assert stats["status_distribution"]["failed"] == 3
        assert stats["status_distribution"]["retry_pending"] == 2
        assert stats["status_distribution"]["rejected"] == 1
        assert stats["status_distribution"]["cancelled"] == 4
        assert stats["status_distribution"]["pending_execution"] == 8

        # Verify specific counts
        assert stats["pending_execution"] == 8
        assert stats["failed_orders"] == 3
        assert stats["retry_pending"] == 2
        assert stats["rejected_orders"] == 1
        assert stats["cancelled_orders"] == 4
        assert stats["executed_orders"] == 10  # ongoing orders
        assert stats["closed_orders"] == 20
        assert stats["amo_orders"] == 5

    def test_get_order_statistics_with_missing_statuses(self, mock_db_session):
        """Test getting statistics when some statuses are missing"""
        # Mock status distribution with only some statuses
        status_distribution_results = [
            ("amo", 5),
            ("ongoing", 10),
        ]

        total_count_result = [(15,)]

        # Create separate mock result objects
        mock_count_result = Mock()
        mock_count_result.fetchone.return_value = total_count_result[0]

        mock_distribution_result = Mock()
        mock_distribution_result.fetchall.return_value = status_distribution_results

        # Mock execute to return different results for different queries
        # get_order_statistics calls execute twice:
        # 1. First for total count (COUNT(*))
        # 2. Then get_order_status_distribution calls execute for status distribution (GROUP BY status)
        def execute_side_effect(query, params):
            query_str = str(query)
            # Check for total count query (COUNT(*) without GROUP BY)
            if "COUNT(*)" in query_str and "GROUP BY" not in query_str:
                return mock_count_result
            # Check for status distribution query
            elif "GROUP BY status" in query_str:
                return mock_distribution_result
            return Mock()

        mock_db_session.execute.side_effect = execute_side_effect

        repo = OrdersRepository(mock_db_session)

        stats = repo.get_order_statistics(user_id=1)

        # Verify statistics
        assert stats["total_orders"] == 15
        assert stats["pending_execution"] == 0  # Missing status defaults to 0
        assert stats["failed_orders"] == 0
        assert stats["retry_pending"] == 0
        assert stats["rejected_orders"] == 0
        assert stats["cancelled_orders"] == 0
        assert stats["executed_orders"] == 10
        assert stats["closed_orders"] == 0
        assert stats["amo_orders"] == 5

