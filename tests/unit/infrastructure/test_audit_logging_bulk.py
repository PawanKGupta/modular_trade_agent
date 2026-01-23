"""
Unit tests for Phase 1: Bulk audit logging

Tests the create_bulk() method and EOD expiry bulk insert optimization.
"""

from datetime import datetime, timedelta

import pytest

from src.infrastructure.db.models import AuditLog, Signals, SignalStatus
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.audit_log_repository import AuditLogRepository
from src.infrastructure.persistence.signals_repository import SignalsRepository

EXPIRED_SIGNAL_OFFSET = timedelta(days=14)


@pytest.fixture
def signals_repo(db_session):
    return SignalsRepository(db_session)


@pytest.fixture
def audit_log_repo(db_session):
    return AuditLogRepository(db_session)


class TestBulkAuditLogCreation:
    """Test create_bulk() method for audit logs"""

    def test_create_bulk_basic(self, audit_log_repo, db_session):
        """Test basic bulk insert of audit logs"""
        SYSTEM_USER_ID = 1

        audit_logs = [
            {
                "user_id": SYSTEM_USER_ID,
                "action": "update",
                "resource_type": "signal",
                "resource_id": 1,
                "changes": {
                    "previous_status": "active",
                    "new_status": "expired",
                    "reason": "eod_expiry",
                },
            },
            {
                "user_id": SYSTEM_USER_ID,
                "action": "update",
                "resource_type": "signal",
                "resource_id": 2,
                "changes": {
                    "previous_status": "active",
                    "new_status": "expired",
                    "reason": "eod_expiry",
                },
            },
            {
                "user_id": SYSTEM_USER_ID,
                "action": "update",
                "resource_type": "signal",
                "resource_id": 3,
                "changes": {
                    "previous_status": "active",
                    "new_status": "expired",
                    "reason": "eod_expiry",
                },
            },
        ]

        result = audit_log_repo.create_bulk(audit_logs)

        assert len(result) == 3
        assert all(isinstance(log, AuditLog) for log in result)
        assert all(log.id is not None for log in result)

        # Verify all logs were created
        created_logs = db_session.query(AuditLog).filter(AuditLog.resource_id.in_([1, 2, 3])).all()
        assert len(created_logs) == 3

    def test_create_bulk_with_timestamp(self, audit_log_repo, db_session):
        """Test bulk insert with explicit timestamps"""
        SYSTEM_USER_ID = 1
        custom_time = ist_now() - timedelta(hours=1)
        # Remove timezone for comparison (database stores naive datetime)
        custom_time_naive = custom_time.replace(tzinfo=None) if custom_time.tzinfo else custom_time

        audit_logs = [
            {
                "user_id": SYSTEM_USER_ID,
                "action": "update",
                "resource_type": "signal",
                "resource_id": 10,
                "changes": {"previous_status": "active", "new_status": "expired"},
                "timestamp": custom_time,
            },
            {
                "user_id": SYSTEM_USER_ID,
                "action": "update",
                "resource_type": "signal",
                "resource_id": 11,
                "changes": {"previous_status": "active", "new_status": "expired"},
                # No timestamp - should be auto-added
            },
        ]

        result = audit_log_repo.create_bulk(audit_logs)

        assert len(result) == 2
        # First log should have custom timestamp (compare without timezone)
        result_timestamp = (
            result[0].timestamp.replace(tzinfo=None)
            if result[0].timestamp.tzinfo
            else result[0].timestamp
        )
        assert abs((result_timestamp - custom_time_naive).total_seconds()) < 1  # Within 1 second
        # Second log should have auto-generated timestamp
        assert result[1].timestamp is not None
        assert result[1].timestamp >= ist_now().replace(tzinfo=None) - timedelta(seconds=5)

    def test_create_bulk_empty_list(self, audit_log_repo):
        """Test bulk insert with empty list"""
        result = audit_log_repo.create_bulk([])
        assert result == []

    def test_create_bulk_large_batch(self, audit_log_repo, db_session):
        """Test bulk insert with large batch (100+ entries)"""
        SYSTEM_USER_ID = 1

        # Create 150 audit log entries
        audit_logs = [
            {
                "user_id": SYSTEM_USER_ID,
                "action": "update",
                "resource_type": "signal",
                "resource_id": i,
                "changes": {
                    "previous_status": "active",
                    "new_status": "expired",
                    "reason": "eod_expiry",
                    "symbol": f"STOCK{i}",
                },
            }
            for i in range(1, 151)
        ]

        # This should complete quickly with bulk insert
        start_time = datetime.now()
        result = audit_log_repo.create_bulk(audit_logs)
        end_time = datetime.now()

        assert len(result) == 150
        # Should complete in reasonable time (less than 5 seconds for 150 entries)
        assert (end_time - start_time).total_seconds() < 5.0

        # Verify all were created
        created_count = (
            db_session.query(AuditLog).filter(AuditLog.resource_id.in_(range(1, 151))).count()
        )
        assert created_count == 150


class TestEODExpiryBulkAuditLogging:
    """Test that EOD expiry uses bulk insert for audit logs"""

    def test_eod_expiry_uses_bulk_insert(self, signals_repo, db_session):
        """Test that EOD expiry creates audit logs using bulk insert"""
        SYSTEM_USER_ID = 1

        # Create multiple expired signals
        expired_time = ist_now() - EXPIRED_SIGNAL_OFFSET
        signals = []
        for i in range(10):
            signal = Signals(symbol=f"STOCK{i}", status=SignalStatus.ACTIVE, ts=expired_time)
            signals.append(signal)

        db_session.add_all(signals)
        db_session.commit()

        for signal in signals:
            db_session.refresh(signal)

        # Count audit logs before expiry
        initial_count = db_session.query(AuditLog).count()

        # Expire signals (should use bulk insert)
        expired_count = signals_repo.mark_time_expired_signals()

        assert expired_count == 10

        # Verify audit logs were created
        final_count = db_session.query(AuditLog).count()
        assert final_count == initial_count + 10

        # Verify all audit logs have correct format
        audit_logs = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.resource_type == "signal",
                AuditLog.user_id == SYSTEM_USER_ID,
                AuditLog.action == "update",
            )
            .order_by(AuditLog.resource_id)
            .all()
        )

        assert len(audit_logs) >= 10

        # Check format of audit logs
        for log in audit_logs[:10]:
            assert log.changes is not None
            assert log.changes.get("previous_status") == "active"
            assert log.changes.get("new_status") == "expired"
            assert log.changes.get("reason") == "eod_expiry"
            assert "symbol" in log.changes

    def test_eod_expiry_audit_log_system_user(self, signals_repo, db_session):
        """Test that EOD expiry uses system user (id=1) for audit logs"""
        SYSTEM_USER_ID = 1

        # Create expired signal
        expired_time = ist_now() - EXPIRED_SIGNAL_OFFSET
        signal = Signals(symbol="TEST", status=SignalStatus.ACTIVE, ts=expired_time)
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # Expire signal
        signals_repo.mark_time_expired_signals()

        # Verify audit log uses system user
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.resource_type == "signal", AuditLog.resource_id == signal.id)
            .first()
        )

        assert audit_log is not None
        assert audit_log.user_id == SYSTEM_USER_ID
        assert audit_log.action == "update"
        assert audit_log.changes.get("reason") == "eod_expiry"

    def test_eod_expiry_no_signals_no_audit_logs(self, signals_repo, db_session):
        """Test that EOD expiry with no expired signals creates no audit logs"""
        initial_count = db_session.query(AuditLog).count()

        # Create active signal that is NOT expired
        active_time = ist_now() - timedelta(hours=1)  # Recent, not expired
        signal = Signals(symbol="ACTIVE", status=SignalStatus.ACTIVE, ts=active_time)
        db_session.add(signal)
        db_session.commit()

        # Try to expire (should expire nothing)
        expired_count = signals_repo.mark_time_expired_signals()

        assert expired_count == 0

        # Verify no new audit logs
        final_count = db_session.query(AuditLog).count()
        assert final_count == initial_count
