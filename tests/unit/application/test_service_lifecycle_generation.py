"""Tests for unified service lifecycle generation tokens."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.application.services.service_lifecycle_generation import (
    bump_service_generation,
    current_service_generation,
    is_generation_current,
    reset_service_generation,
    should_apply_thread_exit_status,
)
from src.application.services.multi_user_trading_service import MultiUserTradingService
from src.infrastructure.db.models import ServiceStatus, Users
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.service_status_repository import ServiceStatusRepository


@pytest.fixture
def sample_user(db_session):
    user = Users(
        email="lifecycle@example.com",
        password_hash="hash",
        created_at=ist_now(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(autouse=True)
def _reset_generations():
    reset_service_generation()
    yield
    reset_service_generation()


class TestServiceLifecycleGeneration:
    def test_bump_increments_generation(self):
        assert bump_service_generation(2) == 1
        assert bump_service_generation(2) == 2
        assert current_service_generation(2) == 2

    def test_should_apply_only_for_current_generation(self):
        gen = bump_service_generation(7)
        assert should_apply_thread_exit_status(7, gen) is True
        bump_service_generation(7)
        assert should_apply_thread_exit_status(7, gen) is False

    def test_is_generation_current(self):
        gen = bump_service_generation(3)
        assert is_generation_current(3, gen) is True
        bump_service_generation(3)
        assert is_generation_current(3, gen) is False


class TestStartStopGenerationRace:
    """Simulate rapid stop/start where an old thread exits after a new start."""

    def test_old_thread_exit_does_not_clear_db_after_new_start(self, db_session, sample_user):
        status_repo = ServiceStatusRepository(db_session)
        status_repo.update_running(sample_user.id, running=True)
        db_session.commit()

        old_generation = bump_service_generation(sample_user.id)
        bump_service_generation(sample_user.id)  # simulate new start

        assert should_apply_thread_exit_status(sample_user.id, old_generation) is False

        if should_apply_thread_exit_status(sample_user.id, old_generation):
            status_repo.update_running(sample_user.id, running=False)
            db_session.commit()

        row = db_session.query(ServiceStatus).filter(ServiceStatus.user_id == sample_user.id).one()
        assert row.service_running is True

    def test_get_service_status_heals_false_stopped_with_live_thread(
        self, db_session, sample_user, monkeypatch
    ):
        monkeypatch.setattr(
            "src.application.services.multi_user_trading_service.get_user_logger",
            lambda **_kwargs: MagicMock(),
        )

        service_generation = bump_service_generation(sample_user.id)
        status_repo = ServiceStatusRepository(db_session)
        status_repo.update_running(sample_user.id, running=False)
        db_session.commit()

        svc = MultiUserTradingService(db=db_session)
        mock_adapter = MagicMock()
        mock_adapter._lifecycle_generation = service_generation
        mock_adapter.running = True

        alive_thread = MagicMock()
        alive_thread.is_alive.return_value = True

        svc._services[sample_user.id] = mock_adapter
        svc._service_threads[sample_user.id] = alive_thread

        status = svc.get_service_status(sample_user.id)
        assert status.service_running is True

    def test_concurrent_start_stop_generation_sequence(self):
        """Document expected generation sequence for stop then quick start."""
        user_id = 42
        start_gen = bump_service_generation(user_id)
        assert is_generation_current(user_id, start_gen)

        bump_service_generation(user_id)  # stop invalidates
        stop_gen = current_service_generation(user_id)
        assert not is_generation_current(user_id, start_gen)

        new_start_gen = bump_service_generation(user_id)
        assert new_start_gen == stop_gen + 1
        assert is_generation_current(user_id, new_start_gen)
        assert not should_apply_thread_exit_status(user_id, start_gen)
