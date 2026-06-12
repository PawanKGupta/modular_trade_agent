"""Tests for service restore snapshot backup/restore."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.application.services.service_restore_snapshot import (
    build_snapshot,
    capture_live_unified_user_ids,
    cleanup_and_restore_services,
    clear_scheduler_locks_for_users,
    load_snapshot,
    merge_restore_targets,
    save_snapshot,
)
from src.infrastructure.db.models import SchedulerLock
from src.infrastructure.db.models import Users
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.service_status_repository import ServiceStatusRepository


@pytest.fixture
def restore_test_user(db_session):
    user = Users(
        email="restore-snap@example.com",
        password_hash="hash",
        created_at=ist_now(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestMergeRestoreTargets:
    def test_unions_unified_and_individual(self):
        a = {
            "unified_user_ids": [1, 2],
            "individual_services": [{"user_id": 1, "task_name": "analysis"}],
        }
        b = {
            "unified_user_ids": [2, 3],
            "individual_services": [{"user_id": 2, "task_name": "buy_orders"}],
        }
        unified, individual = merge_restore_targets(a, b)
        assert unified == [1, 2, 3]
        assert individual == [(1, "analysis"), (2, "buy_orders")]

    def test_ignores_invalid_entries(self):
        payload = {
            "unified_user_ids": ["bad", 4],
            "individual_services": [{"user_id": 4, "task_name": "sell_monitor"}, {"oops": 1}],
        }
        unified, individual = merge_restore_targets(payload)
        assert unified == [4]
        assert individual == [(4, "sell_monitor")]


class TestSnapshotFileRoundTrip:
    def test_save_and_load(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SERVICE_RESTORE_SNAPSHOT_PATH", str(tmp_path / "snap.json"))
        payload = {
            "version": 1,
            "captured_at": "2026-06-11T09:00:00+05:30",
            "source": "test",
            "unified_user_ids": [2, 5],
            "individual_services": [],
        }
        save_snapshot(payload)
        loaded = load_snapshot()
        assert loaded is not None
        assert loaded["unified_user_ids"] == [2, 5]
        history = list((tmp_path / "service_restore_snapshots").glob("snapshot_*.json"))
        assert len(history) == 1


class TestBuildSnapshot:
    def test_includes_db_and_live_unified(self, db_session, restore_test_user):
        user_id = restore_test_user.id
        ServiceStatusRepository(db_session).update_running(user_id, running=True)
        db_session.commit()

        with patch(
            "src.application.services.service_restore_snapshot.capture_live_unified_user_ids",
            return_value=[99],
        ):
            snap = build_snapshot(db_session, source="test")

        assert user_id in snap["unified_user_ids"]
        assert 99 in snap["unified_user_ids"]


class TestCleanupAndRestore:
    def test_clears_scheduler_locks_before_unified_restore(
        self, db_session, restore_test_user, tmp_path, monkeypatch
    ):
        user_id = restore_test_user.id
        snap_path = tmp_path / "service_restore_snapshot.json"
        monkeypatch.setenv("SERVICE_RESTORE_SNAPSHOT_PATH", str(snap_path))

        db_session.add(
            SchedulerLock(
                user_id=user_id,
                locked_at=ist_now(),
                lock_id="pre-restore",
                expires_at=ist_now(),
            )
        )
        db_session.commit()

        save_snapshot(
            {
                "version": 1,
                "captured_at": "2026-06-11T09:00:00+05:30",
                "source": "cli_backup",
                "unified_user_ids": [user_id],
                "individual_services": [],
            },
            path=snap_path,
        )

        with patch(
            "src.application.services.multi_user_trading_service.MultiUserTradingService"
        ) as mock_cls:
            mock_svc = MagicMock()
            mock_svc.start_service.return_value = True
            mock_cls.return_value = mock_svc

            cleanup_and_restore_services(db_session)

        assert (
            db_session.query(SchedulerLock).filter(SchedulerLock.user_id == user_id).count() == 0
        )

    def test_restores_from_snapshot_when_db_says_stopped(
        self, db_session, restore_test_user, tmp_path, monkeypatch
    ):
        """Snapshot file can restore users not marked running in DB (false stale case)."""
        user_id = restore_test_user.id
        snap_path = tmp_path / "service_restore_snapshot.json"
        monkeypatch.setenv("SERVICE_RESTORE_SNAPSHOT_PATH", str(snap_path))

        save_snapshot(
            {
                "version": 1,
                "captured_at": "2026-06-11T09:00:00+05:30",
                "source": "cli_backup",
                "unified_user_ids": [user_id],
                "individual_services": [],
            },
            path=snap_path,
        )

        status = ServiceStatusRepository(db_session).get_or_create(user_id)
        status.service_running = False
        db_session.commit()

        with patch(
            "src.application.services.multi_user_trading_service.MultiUserTradingService"
        ) as mock_cls:
            mock_svc = MagicMock()
            mock_svc.start_service.return_value = True
            mock_cls.return_value = mock_svc

            summary = cleanup_and_restore_services(db_session)

        mock_svc.start_service.assert_called_once_with(user_id)
        assert user_id in summary.unified_targets
        assert summary.unified_restored == 1
