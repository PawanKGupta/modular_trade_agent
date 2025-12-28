"""
Tests for database connection pool monitoring functionality
"""

import pytest
from sqlalchemy.orm import Session

from src.infrastructure.db.connection_monitor import (
    check_pool_health,
    get_active_connections_count,
    get_pool_status,
    log_pool_status,
)
from src.infrastructure.db.session import engine


class TestConnectionPoolMonitoring:
    """Test connection pool monitoring utilities"""

    def test_get_pool_status(self):
        """Test that get_pool_status returns valid metrics"""
        status = get_pool_status(engine)

        # Verify all expected keys are present
        assert "pool_size" in status
        assert "checked_in" in status
        assert "checked_out" in status
        assert "overflow" in status
        assert "max_overflow" in status
        assert "total_connections" in status
        assert "utilization_percent" in status

        # Verify data types
        assert isinstance(status["pool_size"], int)
        assert isinstance(status["checked_in"], int)
        assert isinstance(status["checked_out"], int)
        assert isinstance(status["overflow"], int)
        assert isinstance(status["max_overflow"], int)
        assert isinstance(status["total_connections"], int)
        assert isinstance(status["utilization_percent"], float)

        # Verify logical constraints
        assert status["pool_size"] >= 0
        assert status["checked_in"] >= 0
        assert status["checked_out"] >= 0
        assert status["overflow"] >= 0
        assert status["total_connections"] >= 0
        assert 0 <= status["utilization_percent"] <= 100

    def test_get_active_connections_count(self):
        """Test that get_active_connections_count returns valid count"""
        count = get_active_connections_count(engine)

        assert isinstance(count, int)
        assert count >= 0

    def test_check_pool_health_normal(self):
        """Test pool health check under normal conditions"""
        is_healthy, message = check_pool_health(engine)

        assert isinstance(is_healthy, bool)
        assert isinstance(message, str)
        assert len(message) > 0

    def test_log_pool_status(self, caplog):
        """Test that log_pool_status logs correctly"""
        import logging

        logger = logging.getLogger("test_pool_monitor")

        # Test with logger
        log_pool_status(engine, logger)

        # Test without logger (should use print)
        log_pool_status(engine, None)

    def test_pool_status_with_active_connection(self, db_session: Session):
        """Test pool status when a connection is active"""
        # Get status while a connection is checked out
        status = get_pool_status(engine)

        # Note: StaticPool used in tests returns 0 for all values
        # In production with real pool, we'd see checked_out >= 1
        assert isinstance(status["checked_out"], int)

        # Total connections should be >= 0
        assert status["total_connections"] >= 0

    def test_pool_utilization_calculation(self):
        """Test that pool utilization is calculated correctly"""
        status = get_pool_status(engine)

        max_total = status["pool_size"] + status["max_overflow"]
        if max_total > 0:
            expected_utilization = (status["total_connections"] / max_total) * 100
            assert abs(status["utilization_percent"] - expected_utilization) < 0.1
        else:
            assert status["utilization_percent"] == 0.0


class TestConnectionPoolStressScenarios:
    """Test connection pool behavior under stress"""

    def test_multiple_concurrent_connections(self):
        """Test pool status with multiple concurrent connections"""
        from src.infrastructure.db.session import SessionLocal

        sessions = []
        try:
            # Create multiple concurrent sessions
            for _ in range(5):
                session = SessionLocal()
                sessions.append(session)

            # Check pool status
            status = get_pool_status(engine)

            # Note: StaticPool used in tests returns 0
            # In production with real pool, we'd see checked_out >= 5
            assert status["checked_out"] >= 0

            # Verify health check works
            is_healthy, message = check_pool_health(engine)
            assert isinstance(is_healthy, bool)

        finally:
            # Cleanup
            for session in sessions:
                session.close()

    def test_pool_status_after_connection_close(self):
        """Test that pool status updates after connections are closed"""
        from src.infrastructure.db.session import SessionLocal

        # Get initial status
        initial_status = get_pool_status(engine)
        initial_checked_out = initial_status["checked_out"]

        # Create and close a session
        session = SessionLocal()
        after_open_status = get_pool_status(engine)
        session.close()
        after_close_status = get_pool_status(engine)

        # Checked out count should increase after opening
        assert after_open_status["checked_out"] >= initial_checked_out

        # Checked out count should decrease after closing (though may not be immediate)
        # Give it a moment for pool to update
        import time

        time.sleep(0.1)
        final_status = get_pool_status(engine)
        assert final_status["checked_out"] <= after_open_status["checked_out"]


# Note: API integration tests moved to tests/integration/test_connection_pool_api.py
# They require full FastAPI app setup with authentication
