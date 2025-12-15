# ruff: noqa: E402, PLC0415

from __future__ import annotations

from pathlib import Path

import pytest

from src.application.services.log_retention_service import LogRetentionService
from src.infrastructure.db.models import ErrorLog, Users
from src.infrastructure.db.timezone_utils import ist_now


@pytest.fixture
def seeded_logs(db_session, tmp_path, monkeypatch):
    """Create test data for log retention"""
    monkeypatch.chdir(tmp_path)

    user = Users(email="logs@example.com", password_hash="hash", role="user")
    db_session.add(user)
    db_session.flush()

    now = ist_now()
    old_time = now.replace(year=now.year - 1)

    # Create old and new error logs
    error_old = ErrorLog(
        user_id=user.id,
        error_type="ValueError",
        error_message="old",
        traceback="trace",
        occurred_at=old_time,
    )
    error_new = ErrorLog(
        user_id=user.id,
        error_type="ValueError",
        error_message="new",
        traceback="trace",
        occurred_at=now,
    )
    db_session.add_all([error_old, error_new])
    db_session.commit()

    # Create old and new file logs
    log_dir = Path("logs") / "users" / f"user_{user.id}"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Old log file (year ago)
    old_date_str = old_time.strftime("%Y%m%d")
    old_log_file = log_dir / f"service_{old_date_str}.jsonl"
    old_log_file.write_text('{"message": "old log"}\n')

    # New log file (today)
    new_date_str = now.strftime("%Y%m%d")
    new_log_file = log_dir / f"service_{new_date_str}.jsonl"
    new_log_file.write_text('{"message": "new log"}\n')

    return {
        "error_new_id": error_new.id,
        "user_id": user.id,
        "old_log_file": old_log_file,
        "new_log_file": new_log_file,
    }


def test_log_retention_service_purges_old_logs(db_session, seeded_logs):
    """Test that log retention service purges old file logs and error logs"""
    service = LogRetentionService(db_session)
    removed = service.purge_older_than(90)

    # Should remove old file log but keep new one
    assert removed["service_logs_files"] == 1
    assert removed["error_logs"] == 1

    # Verify old file was deleted
    assert not seeded_logs["old_log_file"].exists()
    assert seeded_logs["new_log_file"].exists()

    # Verify old error log was deleted
    from sqlalchemy import select

    remaining_errors = db_session.scalars(
        select(ErrorLog).where(ErrorLog.user_id == seeded_logs["user_id"])
    ).all()

    assert len(remaining_errors) == 1
    assert remaining_errors[0].id == seeded_logs["error_new_id"]
