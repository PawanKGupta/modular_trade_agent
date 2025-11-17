"""Individual Service Manager

Manages individual service lifecycle, execution, and process management.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from sqlalchemy.orm import Session

# Import trading service module at top level to avoid linting issues
import modules.kotak_neo_auto_trader.run_trading_service as trading_service_module  # noqa: PLC0415
from src.application.services.broker_credentials import (
    decrypt_broker_credentials,
)
from src.application.services.config_converter import user_config_to_strategy_config
from src.application.services.conflict_detection_service import ConflictDetectionService
from src.application.services.schedule_manager import ScheduleManager
from src.infrastructure.logging import get_user_logger
from src.infrastructure.persistence.individual_service_status_repository import (
    IndividualServiceStatusRepository,
)
from src.infrastructure.persistence.individual_service_task_execution_repository import (
    IndividualServiceTaskExecutionRepository,
)
from src.infrastructure.persistence.service_status_repository import ServiceStatusRepository
from src.infrastructure.persistence.settings_repository import SettingsRepository
from src.infrastructure.persistence.user_trading_config_repository import (
    UserTradingConfigRepository,
)

# Project root for script execution
project_root = Path(__file__).parent.parent.parent.parent


class IndividualServiceManager:
    """Manages individual service execution and lifecycle"""

    def __init__(self, db: Session):
        self.db = db
        self._status_repo = IndividualServiceStatusRepository(db)
        self._execution_repo = IndividualServiceTaskExecutionRepository(db)
        self._service_status_repo = ServiceStatusRepository(db)
        self._settings_repo = SettingsRepository(db)
        self._config_repo = UserTradingConfigRepository(db)
        self._conflict_service = ConflictDetectionService(db)
        self._schedule_manager = ScheduleManager(db)
        self._processes: dict[tuple[int, str], subprocess.Popen] = (
            {}
        )  # (user_id, task_name) -> process
        self._run_once_threads: dict[tuple[int, str], threading.Thread] = (
            {}
        )  # (user_id, task_name) -> thread

    def start_service(self, user_id: int, task_name: str) -> tuple[bool, str]:
        """
        Start an individual service for a user.

        Args:
            user_id: User ID
            task_name: Task name (premarket_retry, sell_monitor, etc.)

        Returns:
            (success: bool, message: str)
        """
        # Check if unified service is running
        can_start, message = self._conflict_service.can_start_individual_service(user_id)
        if not can_start:
            return False, message

        # Check if service is already running
        status = self._status_repo.get_by_user_and_task(user_id, task_name)
        if status and status.is_running:
            return False, f"Service '{task_name}' is already running"

        # Get schedule
        schedule = self._schedule_manager.get_schedule(task_name)
        if not schedule:
            return False, f"Schedule not found for task '{task_name}'"

        if not schedule.enabled:
            return False, f"Task '{task_name}' is disabled"

        try:
            # Spawn process for individual service
            process = self._spawn_service_process(user_id, task_name)
            process_id = process.pid

            # Update status
            self._status_repo.mark_running(user_id, task_name, process_id=process_id)
            next_execution = self._schedule_manager.calculate_next_execution(task_name)
            if next_execution:
                self._status_repo.update_next_execution(user_id, task_name, next_execution)

            # Store process reference
            self._processes[(user_id, task_name)] = process

            logger = get_user_logger(user_id=user_id, db=self.db, module="IndividualService")
            logger.info(
                f"Started individual service: {task_name}", action="start_individual_service"
            )

            return True, f"Service '{task_name}' started successfully"

        except Exception as e:
            logger = get_user_logger(user_id=user_id, db=self.db, module="IndividualService")
            logger.error(f"Failed to start individual service: {task_name}", exc_info=e)
            return False, f"Failed to start service: {str(e)}"

    def stop_service(self, user_id: int, task_name: str) -> tuple[bool, str]:
        """
        Stop an individual service for a user.

        Args:
            user_id: User ID
            task_name: Task name

        Returns:
            (success: bool, message: str)
        """
        status = self._status_repo.get_by_user_and_task(user_id, task_name)
        if not status or not status.is_running:
            return False, f"Service '{task_name}' is not running"

        try:
            # Get process
            process_key = (user_id, task_name)
            process = self._processes.get(process_key)

            if process and process.poll() is None:
                # Process is still running
                # Send termination signal
                try:
                    if sys.platform == "win32":
                        process.terminate()
                    else:
                        os.kill(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass  # Process already dead

                # Wait up to 30 seconds
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    # Force kill
                    try:
                        if sys.platform == "win32":
                            process.kill()
                        else:
                            os.kill(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass  # Process already dead

            # Remove from processes dict
            if process_key in self._processes:
                del self._processes[process_key]

            # Update status
            self._status_repo.mark_stopped(user_id, task_name)

            logger = get_user_logger(user_id=user_id, db=self.db, module="IndividualService")
            logger.info(
                f"Stopped individual service: {task_name}", action="stop_individual_service"
            )

            return True, f"Service '{task_name}' stopped successfully"

        except Exception as e:
            logger = get_user_logger(user_id=user_id, db=self.db, module="IndividualService")
            logger.error(f"Failed to stop individual service: {task_name}", exc_info=e)
            return False, f"Failed to stop service: {str(e)}"

    def run_once(
        self, user_id: int, task_name: str, execution_type: str = "run_once"
    ) -> tuple[bool, str, dict]:
        """
        Run a task once immediately (in separate thread/process).

        Args:
            user_id: User ID
            task_name: Task name
            execution_type: 'run_once' or 'manual'

        Returns:
            (success: bool, message: str, execution_details: dict)
        """
        # Check for conflicts (but allow if unified is running, just warn)
        has_conflict, conflict_message = self._conflict_service.check_conflict(user_id, task_name)
        if has_conflict:
            # Still allow but return warning
            logger = get_user_logger(user_id=user_id, db=self.db, module="IndividualService")
            logger.warning(f"Conflict detected for run_once: {conflict_message}")

        # Check if task is already running
        if self._conflict_service.is_task_running(user_id, task_name):
            return False, f"Task '{task_name}' is already running", {}

        try:
            # Create execution record
            execution = self._execution_repo.create(
                user_id=user_id,
                task_name=task_name,
                status="running",
                duration_seconds=0.0,
                execution_type=execution_type,
            )

            # Run in separate thread to avoid blocking
            thread = threading.Thread(
                target=self._execute_task_once,
                args=(user_id, task_name, execution.id),
                daemon=True,
                name=f"RunOnce-{user_id}-{task_name}",
            )
            thread.start()

            # Store thread reference
            self._run_once_threads[(user_id, task_name)] = thread

            return True, f"Task '{task_name}' execution started", {"execution_id": execution.id}

        except Exception as e:
            logger = get_user_logger(user_id=user_id, db=self.db, module="IndividualService")
            logger.error(f"Failed to start run_once: {task_name}", exc_info=e)
            return False, f"Failed to start execution: {str(e)}", {}

    def _execute_task_once(self, user_id: int, task_name: str, execution_id: int) -> None:
        """Execute a task once in a separate thread"""
        start_time = time.time()
        logger = get_user_logger(user_id=user_id, db=self.db, module="IndividualService")

        try:
            logger.info(f"Executing task once: {task_name}", action="run_once")

            # Get user context
            settings = self._settings_repo.get_by_user_id(user_id)
            if not settings:
                raise ValueError(f"User settings not found for user_id={user_id}")

            # Load configuration
            user_config = self._config_repo.get_or_create_default(user_id)
            strategy_config = user_config_to_strategy_config(user_config)

            # Get broker credentials if needed
            broker_creds = None
            if settings.trade_mode.value == "broker":
                if not settings.broker_creds_encrypted:
                    raise ValueError(f"No broker credentials stored for user_id={user_id}")
                broker_creds = decrypt_broker_credentials(settings.broker_creds_encrypted)
                if not broker_creds:
                    raise ValueError(f"Failed to decrypt broker credentials for user_id={user_id}")

            # Execute task based on task_name
            result = self._execute_task_logic(
                user_id=user_id,
                task_name=task_name,
                broker_creds=broker_creds,
                strategy_config=strategy_config,
                settings=settings,
            )

            # Update execution record
            duration = time.time() - start_time
            self._execution_repo.db.refresh(
                self._execution_repo.get(execution_id)
            )  # Refresh to get latest
            execution = self._execution_repo.get(execution_id)
            if execution:
                execution.status = "success"
                execution.duration_seconds = duration
                execution.details = result
                self._execution_repo.db.commit()

            # Update last execution time
            self._status_repo.update_last_execution(user_id, task_name)

            logger.info(
                f"Task execution completed: {task_name} (duration: {duration:.2f}s)",
                action="run_once",
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Task execution failed: {task_name}", exc_info=e, action="run_once")

            # Update execution record
            execution = self._execution_repo.get(execution_id)
            if execution:
                execution.status = "failed"
                execution.duration_seconds = duration
                execution.details = {"error": str(e)}
                self._execution_repo.db.commit()

        finally:
            # Remove thread reference
            thread_key = (user_id, task_name)
            if thread_key in self._run_once_threads:
                del self._run_once_threads[thread_key]

    def _execute_task_logic(
        self, user_id: int, task_name: str, broker_creds: dict | None, strategy_config, settings
    ) -> dict:
        """Execute the actual task logic"""

        # Create TradingService instance (same as unified service)
        service = trading_service_module.TradingService(
            user_id=user_id,
            db_session=self.db,
            broker_creds=broker_creds,
            strategy_config=strategy_config,
            env_file=None,  # Will use broker_creds dict
        )

        # Initialize service
        if not service.initialize():
            raise RuntimeError("Failed to initialize trading service")

        # Execute specific task
        if task_name == "premarket_retry":
            service.run_premarket_retry()
            return {"task": "premarket_retry", "status": "completed"}
        elif task_name == "sell_monitor":
            service.run_sell_monitor()
            return {"task": "sell_monitor", "status": "completed"}
        elif task_name == "position_monitor":
            service.run_position_monitor()
            return {"task": "position_monitor", "status": "completed"}
        elif task_name == "buy_orders":
            service.run_buy_orders()
            return {"task": "buy_orders", "status": "completed"}
        elif task_name == "eod_cleanup":
            service.run_eod_cleanup()
            return {"task": "eod_cleanup", "status": "completed"}
        else:
            raise ValueError(f"Unknown task name: {task_name}")

    def _spawn_service_process(self, user_id: int, task_name: str) -> subprocess.Popen:
        """Spawn a separate process for individual service"""
        # Create script path
        script_path = project_root / "scripts" / "run_individual_service.py"

        # Build command
        cmd = [
            sys.executable,
            str(script_path),
            "--user-id",
            str(user_id),
            "--task",
            task_name,
        ]

        # Spawn process
        process = subprocess.Popen(
            cmd,
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        return process

    def get_status(self, user_id: int) -> dict:
        """Get status of all individual services for a user"""
        services = self._status_repo.list_by_user(user_id)
        schedules = self._schedule_manager.get_all_schedules()

        # Create a dict of existing service statuses
        service_statuses = {s.task_name: s for s in services}

        result = {}
        # Return status for all scheduled tasks
        for schedule in schedules:
            task_name = schedule.task_name
            service = service_statuses.get(task_name)

            next_execution = (
                self._schedule_manager.calculate_next_execution(task_name)
                if schedule.enabled
                else None
            )

            result[task_name] = {
                "is_running": service.is_running if service else False,
                "started_at": (
                    service.started_at.isoformat() if service and service.started_at else None
                ),
                "last_execution_at": (
                    service.last_execution_at.isoformat()
                    if service and service.last_execution_at
                    else None
                ),
                "next_execution_at": (next_execution.isoformat() if next_execution else None),
                "process_id": service.process_id if service else None,
                "schedule_enabled": schedule.enabled,
            }

        return result

    def cleanup_stopped_processes(self) -> int:
        """Clean up processes that have stopped (for crash detection)"""
        count = 0
        for (user_id, task_name), process in list(self._processes.items()):
            if process.poll() is not None:
                # Process has terminated
                self._status_repo.mark_stopped(user_id, task_name)
                del self._processes[(user_id, task_name)]
                count += 1
        return count
