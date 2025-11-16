"""
Task Execution Wrapper

Provides a decorator and context manager for logging task executions to the database.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

from src.infrastructure.logging import get_user_logger
from src.infrastructure.persistence.service_status_repository import ServiceStatusRepository
from src.infrastructure.persistence.service_task_repository import ServiceTaskRepository


@contextmanager
def execute_task(
    user_id: int,
    db_session,
    task_name: str,
    logger=None,
):
    """
    Context manager for executing a task with automatic logging to database.

    Usage:
        with execute_task(user_id, db, "premarket_retry", logger):
            # Task code here
            result = do_something()
            return result

    Args:
        user_id: User ID for this task execution
        db_session: Database session
        task_name: Name of the task (e.g., "premarket_retry", "analysis")
        logger: Optional logger instance (will create one if not provided)

    Yields:
        dict: Task context that can be updated with details
    """
    task_start = time.time()
    task_repo = ServiceTaskRepository(db_session)
    status_repo = ServiceStatusRepository(db_session)
    task_context: dict[str, Any] = {}

    if logger is None:
        logger = get_user_logger(user_id=user_id, db=db_session, module="TaskExecution")

    try:
        logger.info(f"Starting task: {task_name}", action=task_name)
        yield task_context

        # Task completed successfully
        duration = time.time() - task_start
        task_repo.create(
            user_id=user_id,
            task_name=task_name,
            status="success",
            duration_seconds=duration,
            details=task_context,
        )
        status_repo.update_task_execution(user_id)
        logger.info(
            f"Task completed: {task_name} (duration: {duration:.2f}s)",
            action=task_name,
            duration=duration,
        )

    except Exception as e:
        # Task failed
        duration = time.time() - task_start
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            **task_context,
        }

        task_repo.create(
            user_id=user_id,
            task_name=task_name,
            status="failed",
            duration_seconds=duration,
            details=error_details,
        )
        status_repo.update_task_execution(user_id)
        status_repo.increment_error(user_id, error_message=str(e))

        logger.error(
            f"Task failed: {task_name} (duration: {duration:.2f}s)",
            exc_info=e,
            action=task_name,
            duration=duration,
        )
        raise


def task_execution_decorator(task_name: str):
    """
    Decorator for task methods that automatically logs execution to database.

    Usage:
        @task_execution_decorator("premarket_retry")
        def run_premarket_retry(self):
            # Task code here
            pass

    Args:
        task_name: Name of the task

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(self, *args, **kwargs):
            # Assume self has user_id, db, and logger attributes
            user_id = getattr(self, "user_id", None)
            db = getattr(self, "db", None)
            logger = getattr(self, "logger", None)

            if not user_id or not db:
                # Fallback: try to execute without logging
                return func(self, *args, **kwargs)

            with execute_task(user_id, db, task_name, logger):
                return func(self, *args, **kwargs)

        return wrapper

    return decorator


def skip_task(
    user_id: int,
    db_session,
    task_name: str,
    reason: str,
    logger=None,
):
    """
    Log a skipped task execution.

    Args:
        user_id: User ID
        db_session: Database session
        task_name: Name of the task
        reason: Reason for skipping
        logger: Optional logger instance
    """
    task_repo = ServiceTaskRepository(db_session)

    if logger is None:
        logger = get_user_logger(user_id=user_id, db=db_session, module="TaskExecution")

    task_repo.create(
        user_id=user_id,
        task_name=task_name,
        status="skipped",
        duration_seconds=0.0,
        details={"reason": reason},
    )

    logger.info(f"Task skipped: {task_name} - {reason}", action=task_name, reason=reason)
