# ruff: noqa: E402, PLC0415

from __future__ import annotations

import pytest

from src.application.services.log_retention_service import LogRetentionService
from src.infrastructure.db.models import ErrorLog, ServiceLog, Users
from src.infrastructure.db.timezone_utils import ist_now


@pytest.fixture
def seeded_logs(db_session):
    user = Users(email="logs@example.com", password_hash="hash", role="user")
    db_session.add(user)
    db_session.flush()

    now = ist_now()
    old_time = now.replace(year=now.year - 1)

    service_old = ServiceLog(
        user_id=user.id, level="INFO", module="test", message="old", timestamp=old_time
    )
    service_new = ServiceLog(
        user_id=user.id, level="INFO", module="test", message="new", timestamp=now
    )
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
    db_session.add_all([service_old, service_new, error_old, error_new])
    db_session.commit()
    return {
        "service_new_id": service_new.id,
        "error_new_id": error_new.id,
        "user_id": user.id,
    }


def test_log_retention_service_purges_old_logs(db_session, seeded_logs):
    service = LogRetentionService(db_session)
    removed = service.purge_older_than(90)

    assert removed["service_logs"] == 1
    assert removed["error_logs"] == 1

    remaining_services = db_session.query(ServiceLog).all()
    remaining_errors = db_session.query(ErrorLog).all()

    assert len(remaining_services) == 1
    assert remaining_services[0].id == seeded_logs["service_new_id"]
    assert len(remaining_errors) == 1
    assert remaining_errors[0].id == seeded_logs["error_new_id"]
