"""
Tests for task execution wrapper (Phase 2.5)

Tests that task executions are properly logged to the database with user context.
"""

import os
import time
from unittest.mock import MagicMock, patch

import pytest

from src.application.services.task_execution_wrapper import (
    execute_task,
    skip_task,
    task_execution_decorator,
)
from src.infrastructure.db.models import Users


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = Users(
        email="test@example.com",
        password_hash="test_hash",
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def mock_logger():
    """Mock logger"""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.error = MagicMock()
    logger.warning = MagicMock()
    return logger


class TestExecuteTask:
    """Test execute_task context manager"""

    def test_successful_task_execution(self, db_session, test_user, mock_logger):
        """Test successful task execution is logged"""
        from src.infrastructure.persistence.service_task_repository import ServiceTaskRepository

        task_context = {}
        with execute_task(test_user.id, db_session, "test_task", mock_logger) as ctx:
            task_context = ctx
            task_context["test_key"] = "test_value"
            # Simulate task work
            time.sleep(0.01)

        # Verify task was logged
        task_repo = ServiceTaskRepository(db_session)
        tasks = task_repo.list(test_user.id, task_name="test_task", limit=1)

        assert len(tasks) == 1
        task = tasks[0]
        assert task.user_id == test_user.id
        assert task.task_name == "test_task"
        assert task.status == "success"
        assert task.duration_seconds > 0
        assert task.details["test_key"] == "test_value"

    def test_failed_task_execution(self, db_session, test_user, mock_logger):
        """Test failed task execution is logged with error"""
        from src.infrastructure.persistence.service_status_repository import ServiceStatusRepository
        from src.infrastructure.persistence.service_task_repository import ServiceTaskRepository

        error_message = "Test error occurred"

        with pytest.raises(ValueError, match=error_message):
            with execute_task(test_user.id, db_session, "test_task", mock_logger) as ctx:
                ctx["attempt"] = 1
                raise ValueError(error_message)

        # Verify task was logged as failed
        task_repo = ServiceTaskRepository(db_session)
        tasks = task_repo.list(test_user.id, task_name="test_task", limit=1)

        assert len(tasks) == 1
        task = tasks[0]
        assert task.status == "failed"
        assert task.details["error_type"] == "ValueError"
        assert task.details["error_message"] == error_message
        assert task.details["attempt"] == 1

        # Verify error count was incremented
        status_repo = ServiceStatusRepository(db_session)
        status = status_repo.get(test_user.id)
        assert status is not None
        assert status.error_count > 0

    def test_task_context_preservation(self, db_session, test_user, mock_logger):
        """Test that task context is preserved in details"""
        from src.infrastructure.persistence.service_task_repository import ServiceTaskRepository

        with execute_task(test_user.id, db_session, "test_task", mock_logger) as ctx:
            ctx["symbol"] = "RELIANCE"
            ctx["quantity"] = 20
            ctx["price"] = 2500.0

        task_repo = ServiceTaskRepository(db_session)
        tasks = task_repo.list(test_user.id, task_name="test_task", limit=1)

        assert len(tasks) == 1
        details = tasks[0].details
        assert details["symbol"] == "RELIANCE"
        assert details["quantity"] == 20
        assert details["price"] == 2500.0

    def test_task_duration_tracking(self, db_session, test_user, mock_logger):
        """Test that task duration is accurately tracked"""
        from src.infrastructure.persistence.service_task_repository import ServiceTaskRepository

        sleep_duration = 0.1

        with execute_task(test_user.id, db_session, "test_task", mock_logger):
            time.sleep(sleep_duration)

        task_repo = ServiceTaskRepository(db_session)
        tasks = task_repo.list(test_user.id, task_name="test_task", limit=1)

        assert len(tasks) == 1
        # Duration should be at least sleep_duration (may be slightly more)
        assert tasks[0].duration_seconds >= sleep_duration
        # But shouldn't be too much more (allow 0.05s overhead)
        assert tasks[0].duration_seconds < sleep_duration + 0.05

    def test_task_updates_service_status(self, db_session, test_user, mock_logger):
        """Test that task execution updates service status"""
        from src.infrastructure.persistence.service_status_repository import ServiceStatusRepository

        initial_status = ServiceStatusRepository(db_session).get_or_create(test_user.id)
        initial_time = initial_status.last_task_execution

        # Wait a bit to ensure time difference
        time.sleep(0.01)

        with execute_task(test_user.id, db_session, "test_task", mock_logger):
            pass

        # Verify last_task_execution was updated
        status_repo = ServiceStatusRepository(db_session)
        updated_status = status_repo.get(test_user.id)

        assert updated_status.last_task_execution is not None
        if initial_time:
            assert updated_status.last_task_execution > initial_time


class TestSkipTask:
    """Test skip_task function"""

    def test_skip_task_logs_skipped_status(self, db_session, test_user, mock_logger):
        """Test that skipped tasks are logged with skipped status"""
        from src.infrastructure.persistence.service_task_repository import ServiceTaskRepository

        skip_task(
            test_user.id,
            db_session,
            "test_task",
            "Task already completed",
            mock_logger,
        )

        task_repo = ServiceTaskRepository(db_session)
        tasks = task_repo.list(test_user.id, task_name="test_task", limit=1)

        assert len(tasks) == 1
        task = tasks[0]
        assert task.status == "skipped"
        assert task.duration_seconds == 0.0
        assert task.details["reason"] == "Task already completed"

    def test_skip_task_without_logger(self, db_session, test_user):
        """Test skip_task works without explicit logger"""
        from src.infrastructure.persistence.service_task_repository import ServiceTaskRepository

        skip_task(
            test_user.id,
            db_session,
            "test_task",
            "No logger provided",
        )

        task_repo = ServiceTaskRepository(db_session)
        tasks = task_repo.list(test_user.id, task_name="test_task", limit=1)

        assert len(tasks) == 1
        assert tasks[0].status == "skipped"


class TestTaskExecutionDecorator:
    """Test task_execution_decorator"""

    def test_decorator_logs_successful_execution(self, db_session, test_user):
        """Test that decorated function logs execution"""
        from src.infrastructure.persistence.service_task_repository import ServiceTaskRepository

        class TestService:
            def __init__(self):
                self.user_id = test_user.id
                self.db = db_session
                self.logger = MagicMock()

            @task_execution_decorator("decorated_task")
            def run_task(self):
                return "success"

        service = TestService()
        result = service.run_task()

        assert result == "success"

        task_repo = ServiceTaskRepository(db_session)
        tasks = task_repo.list(test_user.id, task_name="decorated_task", limit=1)

        assert len(tasks) == 1
        assert tasks[0].status == "success"

    def test_decorator_logs_failed_execution(self, db_session, test_user):
        """Test that decorated function logs failures"""
        from src.infrastructure.persistence.service_task_repository import ServiceTaskRepository

        class TestService:
            def __init__(self):
                self.user_id = test_user.id
                self.db = db_session
                self.logger = MagicMock()

            @task_execution_decorator("decorated_task")
            def run_task(self):
                raise ValueError("Task failed")

        service = TestService()

        with pytest.raises(ValueError):
            service.run_task()

        task_repo = ServiceTaskRepository(db_session)
        tasks = task_repo.list(test_user.id, task_name="decorated_task", limit=1)

        assert len(tasks) == 1
        assert tasks[0].status == "failed"

    def test_decorator_fallback_without_user_id(self):
        """Test decorator falls back gracefully when user_id/db not available"""

        class TestService:
            @task_execution_decorator("decorated_task")
            def run_task(self):
                return "success"

        service = TestService()
        # Should not raise error even without user_id/db
        result = service.run_task()
        assert result == "success"


class TestTaskExecutionIntegration:
    """Integration tests for task execution with TradingService"""

    def test_premarket_retry_task_execution(self, db_session, test_user):
        """Test that premarket_retry task is logged"""
        from unittest.mock import MagicMock

        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.run_trading_service import TradingService

        # Mock all dependencies
        with (
            patch(
                "modules.kotak_neo_auto_trader.run_trading_service.KotakNeoAuth"
            ) as mock_auth_class,
            patch(
                "modules.kotak_neo_auto_trader.run_trading_service.AutoTradeEngine"
            ) as mock_engine_class,
        ):
            mock_auth = MagicMock()
            mock_auth.is_authenticated.return_value = True
            mock_auth.login.return_value = True
            mock_auth_class.return_value = mock_auth

            mock_engine = MagicMock()
            mock_engine.load_latest_recommendations.return_value = []
            mock_engine_class.return_value = mock_engine

            # Create temp env file
            import tempfile

            temp_env = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".env")
            temp_env.write("KOTAK_CONSUMER_KEY=test\nKOTAK_CONSUMER_SECRET=test\n")
            temp_env.close()

            try:
                service = TradingService(
                    user_id=test_user.id,
                    db_session=db_session,
                    broker_creds={"api_key": "test"},
                    strategy_config=StrategyConfig.default(),
                    env_file=temp_env.name,
                )
                service.auth = mock_auth
                service.engine = mock_engine
                service.logger = MagicMock()

                # Run task
                service.run_premarket_retry()

                # Verify task was logged
                from src.infrastructure.persistence.service_task_repository import (
                    ServiceTaskRepository,
                )

                task_repo = ServiceTaskRepository(db_session)
                tasks = task_repo.list(test_user.id, task_name="premarket_retry", limit=1)

                assert len(tasks) == 1
                assert tasks[0].status == "success"
                assert tasks[0].user_id == test_user.id

            finally:
                if os.path.exists(temp_env.name):
                    os.unlink(temp_env.name)

    def test_multiple_task_executions(self, db_session, test_user, mock_logger):
        """Test that multiple task executions are logged separately"""
        from src.infrastructure.persistence.service_task_repository import ServiceTaskRepository

        # Execute same task multiple times
        for i in range(3):
            with execute_task(test_user.id, db_session, "repeated_task", mock_logger) as ctx:
                ctx["iteration"] = i
                time.sleep(0.01)

        task_repo = ServiceTaskRepository(db_session)
        tasks = task_repo.list(test_user.id, task_name="repeated_task", limit=10)

        assert len(tasks) == 3
        # Verify all are successful
        for task in tasks:
            assert task.status == "success"
            assert "iteration" in task.details

        # Verify they have different execution times
        execution_times = [task.executed_at for task in tasks]
        assert len(set(execution_times)) == 3  # All unique

    def test_task_execution_with_exception_context(self, db_session, test_user, mock_logger):
        """Test that exception context is captured in task details"""
        from src.infrastructure.persistence.service_task_repository import ServiceTaskRepository

        try:
            with execute_task(test_user.id, db_session, "error_task", mock_logger) as ctx:
                ctx["step"] = "initialization"
                raise RuntimeError("Something went wrong")
        except RuntimeError:
            pass

        task_repo = ServiceTaskRepository(db_session)
        tasks = task_repo.list(test_user.id, task_name="error_task", limit=1)

        assert len(tasks) == 1
        task = tasks[0]
        assert task.status == "failed"
        assert task.details["error_type"] == "RuntimeError"
        assert task.details["error_message"] == "Something went wrong"
        assert task.details["step"] == "initialization"  # Context preserved
