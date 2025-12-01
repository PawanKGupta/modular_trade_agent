"""Individual Service Manager

Manages individual service lifecycle, execution, and process management.
"""

from __future__ import annotations

import ast
import json
import os
import signal
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

from sqlalchemy.orm import Session

# Import trading service module at top level to avoid linting issues
import modules.kotak_neo_auto_trader.run_trading_service as trading_service_module  # noqa: PLC0415
from src.application.services.analysis_deduplication_service import AnalysisDeduplicationService
from src.application.services.broker_credentials import decrypt_broker_credentials
from src.application.services.config_converter import user_config_to_strategy_config
from src.application.services.conflict_detection_service import ConflictDetectionService
from src.application.services.schedule_manager import ScheduleManager
from src.application.services.task_execution_wrapper import execute_task
from src.infrastructure.logging import get_user_logger

# Import for service notifications
try:
    from modules.kotak_neo_auto_trader.telegram_notifier import get_telegram_notifier

    TELEGRAM_NOTIFIER_AVAILABLE = True
except ImportError:
    TELEGRAM_NOTIFIER_AVAILABLE = False

try:
    from services.email_notifier import EmailNotifier

    EMAIL_NOTIFIER_AVAILABLE = True
except ImportError:
    EMAIL_NOTIFIER_AVAILABLE = False
from src.infrastructure.persistence.individual_service_status_repository import (
    IndividualServiceStatusRepository,
)
from src.infrastructure.persistence.individual_service_task_execution_repository import (
    IndividualServiceTaskExecutionRepository,
)
from src.infrastructure.persistence.notification_repository import NotificationRepository
from src.infrastructure.persistence.service_status_repository import ServiceStatusRepository
from src.infrastructure.persistence.settings_repository import SettingsRepository
from src.infrastructure.persistence.signals_repository import SignalsRepository
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
        self._notification_repo = NotificationRepository(db)
        self._processes: dict[tuple[int, str], subprocess.Popen] = (
            {}
        )  # (user_id, task_name) -> process
        self._run_once_threads: dict[tuple[int, str], threading.Thread] = (
            {}
        )  # (user_id, task_name) -> thread
        self._schedules_checked = False  # Cache flag to avoid repeated checks

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

            # Small delay to ensure process has started
            time.sleep(0.1)

            # Check if process is still alive (hasn't crashed immediately)
            if process.poll() is not None:
                # Process already terminated (likely an error)
                return_code = process.returncode
                error_msg = f"Process terminated immediately with code {return_code}"
                logger = get_user_logger(user_id=user_id, db=self.db, module="IndividualService")
                logger.error(
                    f"Failed to start {task_name}: {error_msg}",
                    action="start_individual_service",
                )
                return False, f"Failed to start service: {error_msg}"

            # Update status
            self._status_repo.mark_running(user_id, task_name, process_id=process_id)
            # Commit to ensure status is immediately visible to other sessions
            self.db.commit()
            next_execution = self._schedule_manager.calculate_next_execution(task_name)
            if next_execution:
                self._status_repo.update_next_execution(user_id, task_name, next_execution)
                self.db.commit()

            # Store process reference
            self._processes[(user_id, task_name)] = process

            logger = get_user_logger(user_id=user_id, db=self.db, module="IndividualService")
            logger.info(
                f"Started individual service: {task_name} (PID: {process_id})",
                action="start_individual_service",
            )

            # Send notification for service start
            self._notify_service_started(user_id, task_name, process_id)

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
            # Commit to ensure status is immediately visible to other sessions
            self.db.commit()

            logger = get_user_logger(user_id=user_id, db=self.db, module="IndividualService")
            logger.info(
                f"Stopped individual service: {task_name}", action="stop_individual_service"
            )

            # Send notification for service stop
            self._notify_service_stopped(user_id, task_name)

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
        # CRITICAL: Block run-once if unified service is running (prevents session conflicts)
        # Exception: Analysis task doesn't need broker session, so it's safe
        if task_name != "analysis" and self._conflict_service.is_unified_service_running(user_id):
            return (
                False,
                "Cannot run task while unified service is active. Running this task would "
                "create a new broker session, causing JWT authentication conflicts with the "
                "unified service. Please stop the unified service first, or wait for this "
                "task to run via its schedule.",
                {},
            )

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

    def _update_execution_status(
        self,
        user_id: int,
        execution_id: int,
        status: str,
        duration: float,
        details: dict | str | None,
        task_name: str,
    ) -> None:
        """
        Update execution status with rollback handling and raw SQL fallback.

        This method ensures execution status is always updated, even if the session
        is in a bad state due to previous errors (e.g., datetime conversion issues).
        """
        logger = get_user_logger(user_id=user_id, db=self.db, module="IndividualService")

        # Ensure details is JSON-serializable
        if details is None:
            details_dict = {}
        elif isinstance(details, dict):
            details_dict = details
        else:
            details_dict = {"result": str(details)}

        try:
            # Rollback session if it's in a bad state (e.g., from previous errors)
            try:
                self.db.rollback()
            except Exception:
                pass  # Ignore rollback errors

            execution = self._execution_repo.get(execution_id)
            if execution:
                execution.status = status
                execution.duration_seconds = duration
                execution.details = details_dict
                self._execution_repo.db.commit()
                self._execution_repo.db.flush()
                logger.info(
                    f"Updated execution {execution_id} status to '{status}' in database",
                    action="run_once",
                    task_name=task_name,
                )
            else:
                logger.warning(
                    f"Execution {execution_id} not found, cannot update status",
                    action="run_once",
                    task_name=task_name,
                )
        except Exception as update_error:
            # If status update fails, try raw SQL as fallback
            logger.error(
                f"Failed to update execution {execution_id} status to '{status}' via ORM: {update_error}, trying raw SQL",
                exc_info=update_error,
                action="run_once",
                task_name=task_name,
            )
            try:
                from sqlalchemy import text  # noqa: PLC0415

                # Rollback and use fresh connection for raw SQL
                try:
                    self.db.rollback()
                except Exception:
                    pass

                update_sql = text(
                    """
                    UPDATE individual_service_task_execution
                    SET status = :status,
                        duration_seconds = :duration,
                        details = :details
                    WHERE id = :execution_id
                """
                )
                details_json = json.dumps(details_dict)
                self.db.execute(
                    update_sql,
                    {
                        "execution_id": execution_id,
                        "status": status,
                        "duration": duration,
                        "details": details_json,
                    },
                )
                self.db.commit()
                logger.info(
                    f"Updated execution {execution_id} status to '{status}' via raw SQL",
                    action="run_once",
                    task_name=task_name,
                )
            except Exception as raw_error:
                logger.error(
                    f"Failed to update execution {execution_id} status to '{status}' via raw SQL: {raw_error}",
                    exc_info=raw_error,
                    action="run_once",
                    task_name=task_name,
                )

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
            requires_broker_creds = (
                task_name != "analysis" and settings.trade_mode.value == "broker"
            )
            if requires_broker_creds:
                if not settings.broker_creds_encrypted:
                    raise ValueError(
                        f"Task '{task_name}' requires broker credentials, but none are stored for user_id={user_id}. "
                        f"Please configure broker credentials in your settings, or switch to paper trading mode "
                        f"(current mode: {settings.trade_mode.value})."
                    )
                broker_creds = decrypt_broker_credentials(settings.broker_creds_encrypted)
                if not broker_creds:
                    raise ValueError(
                        f"Failed to decrypt broker credentials for user_id={user_id}. "
                        f"Please reconfigure your broker credentials, or switch to "
                        f"paper trading mode."
                    )

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
            self._update_execution_status(
                user_id=user_id,
                execution_id=execution_id,
                status="success",
                duration=duration,
                details=result,
                task_name=task_name,
            )

            # Update last execution time
            self._status_repo.update_last_execution(user_id, task_name)

            logger.info(
                f"Task execution completed: {task_name} (duration: {duration:.2f}s)",
                action="run_once",
            )

            # Send notification for successful execution
            self._notify_service_execution_completed(user_id, task_name, "success", duration)

        except Exception as e:
            duration = time.time() - start_time
            error_details = {"error": str(e), "error_type": type(e).__name__}
            # Include traceback for better debugging
            error_details["traceback"] = traceback.format_exc()

            logger.error(
                f"Task execution failed: {task_name}",
                exc_info=e,
                action="run_once",
                task_name=task_name,
            )

            # Update execution record
            self._update_execution_status(
                user_id=user_id,
                execution_id=execution_id,
                status="failed",
                duration=duration,
                details=error_details,
                task_name=task_name,
            )

            # Send notification for failed execution
            self._notify_service_execution_completed(user_id, task_name, "failed", duration, str(e))

        finally:
            # Small delay to ensure database commit is fully written and visible
            # This helps with SQLite transaction isolation between threads
            time.sleep(0.2)
            # Remove thread reference after ensuring commit is visible
            thread_key = (user_id, task_name)
            if thread_key in self._run_once_threads:
                del self._run_once_threads[thread_key]
                logger.debug(
                    f"Removed thread reference for {task_name}",
                    action="run_once",
                    task_name=task_name,
                )

    def _execute_task_logic(
        self, user_id: int, task_name: str, broker_creds: dict | None, strategy_config, settings
    ) -> dict:
        """Execute the actual task logic"""
        logger = get_user_logger(user_id=user_id, db=self.db, module="IndividualService")

        if task_name == "analysis":
            return self._run_analysis_task(user_id=user_id)

        # Check if paper trading mode
        is_paper_mode = settings.trade_mode.value == "paper"

        if is_paper_mode:
            # Paper trading mode: use PaperTradingServiceAdapter
            from src.application.services.paper_trading_service_adapter import (
                PaperTradingServiceAdapter,
            )

            # Load user trading config to get paper_trading_initial_capital
            user_config = self._config_repo.get_or_create_default(user_id)

            service = PaperTradingServiceAdapter(
                user_id=user_id,
                db_session=self.db,
                strategy_config=strategy_config,
                initial_capital=user_config.paper_trading_initial_capital,
                storage_path=None,  # Will use user-specific path
                skip_execution_tracking=True,
            )

            # Initialize paper trading service
            if not service.initialize():
                raise RuntimeError(
                    "Failed to initialize paper trading service. "
                    "Check storage permissions and configuration."
                )
        else:
            # Broker mode: requires credentials
            if not broker_creds:
                raise ValueError(
                    f"Task '{task_name}' requires broker credentials for broker mode. "
                    f"Please configure broker credentials in your settings."
                )

            # Create TradingService instance (same as unified service) for broker-dependent tasks
            # Skip execution tracking since individual services track separately
            service = trading_service_module.TradingService(
                user_id=user_id,
                db_session=self.db,
                broker_creds=broker_creds,
                strategy_config=strategy_config,
                env_file=None,
                skip_execution_tracking=True,
            )

            # Initialize service
            logger.info(
                f"Initializing trading service for task: {task_name}", action="execute_task"
            )
            init_start = time.time()
            if not service.initialize():
                raise RuntimeError(
                    "Failed to initialize trading service. "
                    "Check broker credentials, authentication, and network connectivity."
                )
            init_duration = time.time() - init_start
            logger.info(
                f"Trading service initialized in {init_duration:.2f}s",
                action="execute_task",
                task_name=task_name,
            )

        # Execute specific task
        logger.info(f"Executing task: {task_name}", action="execute_task")
        task_start = time.time()
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
            logger.info(
                "About to call service.run_buy_orders()", action="execute_task", task_name=task_name
            )
            summary = service.run_buy_orders()
            task_duration = time.time() - task_start
            logger.info(
                f"service.run_buy_orders() completed in {task_duration:.2f}s",
                action="execute_task",
                task_name=task_name,
            )
            result = {"task": "buy_orders", "status": "completed"}
            if summary:
                result["summary"] = summary
            return result
        elif task_name == "eod_cleanup":
            service.run_eod_cleanup()
            return {"task": "eod_cleanup", "status": "completed"}
        else:
            raise ValueError(f"Unknown task name: {task_name}")

    def _run_analysis_task(self, user_id: int) -> dict:
        """Execute the analysis task without requiring broker credentials"""
        logger = get_user_logger(user_id=user_id, db=self.db, module="IndividualService")

        try:
            max_retries = 3
            base_delay = 30.0  # seconds
            timeout_seconds = 1800  # 30 minutes

            trade_agent_path = project_root / "trade_agent.py"
            if not trade_agent_path.exists():
                error_msg = f"trade_agent.py not found at {trade_agent_path}. Cannot run analysis."
                logger.error(error_msg, action="run_analysis")
                raise FileNotFoundError(error_msg)

            results_dir = project_root / "analysis_results"
            results_dir.mkdir(parents=True, exist_ok=True)
            results_json_path = results_dir / "latest_results.json"
            if results_json_path.exists():
                try:
                    results_json_path.unlink()
                except OSError:
                    logger.warning(
                        f"Unable to remove previous analysis results file: {results_json_path}",
                        action="run_analysis",
                        task_name="analysis",
                    )

            cmd = [
                sys.executable,
                str(trade_agent_path),
                "--backtest",
                "--json-output",
                str(results_json_path),
            ]
            logger.info(f"Running analysis: {' '.join(cmd)}", action="run_analysis")

            with execute_task(user_id, self.db, "analysis", logger) as task_context:
                task_context["timeout_seconds"] = timeout_seconds
                task_context["max_retries"] = max_retries

                for attempt in range(max_retries):
                    try:
                        if attempt > 0:
                            delay = base_delay * attempt
                            logger.info(
                                f"Retrying analysis attempt {attempt + 1}/{max_retries} in {delay:.0f}s",
                                action="run_analysis",
                                task_name="analysis",
                            )
                            time.sleep(delay)

                        logger.info(
                            "Starting analysis subprocess (trade_agent.py --backtest)",
                            action="run_analysis",
                            task_name="analysis",
                        )
                        result = subprocess.run(
                            cmd,
                            check=False,
                            cwd=str(project_root),
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                            timeout=timeout_seconds,
                        )

                        task_context["return_code"] = result.returncode
                        stdout_tail = (
                            result.stdout[-500:]
                            if result.stdout and len(result.stdout) > 500
                            else result.stdout
                        )
                        stderr_tail = (
                            result.stderr[-500:]
                            if result.stderr and len(result.stderr) > 500
                            else result.stderr
                        )

                        if result.returncode == 0:
                            logger.info(
                                "Analysis subprocess completed successfully",
                                action="run_analysis",
                                task_name="analysis",
                            )
                            task_context["success"] = True
                            if stdout_tail:
                                task_context["stdout_tail"] = stdout_tail

                            # Load and persist results (this may take time, but subprocess already completed)
                            analysis_results = []
                            summary = {"processed": 0, "inserted": 0, "updated": 0, "skipped": 0}
                            try:
                                analysis_results = self._load_analysis_results(
                                    results_json_path, logger
                                )
                                summary = self._persist_analysis_results(analysis_results, logger)
                                logger.info(
                                    f"Analysis results persisted: {summary}",
                                    action="run_analysis",
                                    task_name="analysis",
                                )
                            except Exception as persist_error:
                                # Log error but don't fail - subprocess completed
                                logger.error(
                                    f"Failed to persist analysis results "
                                    f"(but subprocess completed): {persist_error}",
                                    exc_info=persist_error,
                                    action="run_analysis",
                                    task_name="analysis",
                                )
                                summary["error"] = str(persist_error)

                            task_context["analysis_summary"] = summary
                            task_context["results_count"] = len(analysis_results)

                            return {
                                "task": "analysis",
                                "status": "completed",
                                "stdout_tail": stdout_tail,
                                "analysis_summary": summary,
                                "results_count": len(analysis_results),
                            }

                        error_msg = f"Analysis failed with return code {result.returncode}"
                        if stderr_tail:
                            error_msg += f"\nSTDERR (tail):\n{stderr_tail}"
                        if stdout_tail:
                            error_msg += f"\nSTDOUT (tail):\n{stdout_tail}"
                        task_context["error_message"] = error_msg

                        if (
                            self._looks_like_network_error(result.stdout, result.stderr)
                            and attempt < max_retries - 1
                        ):
                            logger.warning(
                                f"{error_msg}\nDetected transient/network issue. Retrying...",
                                action="run_analysis",
                                task_name="analysis",
                            )
                            continue

                        raise RuntimeError(error_msg)

                    except subprocess.TimeoutExpired:
                        timeout_msg = (
                            f"Analysis timed out after {timeout_seconds} seconds "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        logger.error(
                            timeout_msg,
                            action="run_analysis",
                            task_name="analysis",
                        )
                        task_context["timeout"] = True
                        if attempt < max_retries - 1:
                            continue
                        raise RuntimeError(timeout_msg)

                    except Exception as e:
                        logger.error(
                            f"Analysis subprocess failed: {e}",
                            exc_info=e,
                            action="run_analysis",
                            task_name="analysis",
                        )
                        task_context["exception"] = str(e)
                        if (
                            isinstance(e, RuntimeError)
                            and "network" in str(e).lower()
                            and attempt < max_retries - 1
                        ):
                            continue
                        raise

                raise RuntimeError("Analysis failed after all retry attempts")

        except Exception as e:
            # Log the error with full context
            logger.error(
                f"Analysis task failed: {str(e)}",
                exc_info=e,
                action="run_analysis",
                task_name="analysis",
            )
            raise

    @staticmethod
    def _looks_like_network_error(stdout: str | None, stderr: str | None) -> bool:
        """Heuristic to detect network-related errors so we can retry safely"""
        combined = ((stdout or "") + (stderr or "")).lower()
        network_keywords = ["timeout", "connection", "socket", "network", "urllib3", "recv_into"]
        return any(keyword in combined for keyword in network_keywords)

    def _load_analysis_results(self, results_path: Path, logger) -> list[dict]:
        """Load analysis results from JSON file produced by trade_agent"""
        if not results_path.exists():
            logger.warning(
                f"Analysis results JSON not found at {results_path}",
                action="run_analysis",
                task_name="analysis",
            )
            return []

        try:
            with results_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "results" in data:
                data = data["results"]
            if not isinstance(data, list):
                logger.warning(
                    "Analysis results JSON format invalid (expected list)",
                    action="run_analysis",
                    task_name="analysis",
                )
                return []

            return data
        except Exception as e:
            logger.error(
                f"Failed to load analysis results JSON: {e}",
                exc_info=e,
                action="run_analysis",
                task_name="analysis",
            )
            return []

    def _persist_analysis_results(self, results: list[dict], logger) -> dict[str, int]:
        """Persist analysis results to Signals table using deduplication rules"""
        logger.info(
            f"Starting persistence: {len(results)} results to process",
            action="run_analysis",
            task_name="analysis",
        )

        processed_rows = []
        for row in results:
            if not isinstance(row, dict) or row.get("status") not in {"success", None}:
                continue

            verdict = row.get("final_verdict") or row.get("verdict") or row.get("ml_verdict")
            if verdict not in {"buy", "strong_buy"}:
                continue

            normalized = self._normalize_analysis_row(row)
            if normalized:
                processed_rows.append(normalized)

        summary = {
            "processed": len(processed_rows),
            "inserted": 0,
            "updated": 0,
            "skipped": len(results) - len(processed_rows),
        }

        logger.info(
            f"Normalized {len(processed_rows)} rows from {len(results)} results",
            action="run_analysis",
            task_name="analysis",
        )

        if not processed_rows:
            logger.warning(
                "No processed rows to persist to Signals table",
                action="run_analysis",
                task_name="analysis",
            )
            return summary

        try:
            dedup_service = AnalysisDeduplicationService(self.db)

            should_update = dedup_service.should_update_signals()
            logger.info(
                f"should_update_signals() returned: {should_update}",
                action="run_analysis",
                task_name="analysis",
            )

            if not should_update:
                from datetime import time as time_class  # noqa: PLC0415

                from src.infrastructure.db.timezone_utils import ist_now  # noqa: PLC0415

                now = ist_now()
                current_time = now.time()
                reason = "unknown"
                if dedup_service.is_weekend_or_holiday(now.date()):
                    if current_time >= time_class(9, 0):
                        reason = "weekend/holiday (after 9AM)"
                    else:
                        reason = "weekend/holiday (unexpected - should allow before 9AM)"
                elif time_class(9, 0) <= current_time < time_class(16, 0):
                    reason = (
                        f"during trading hours (9AM-4PM, current time: {now.strftime('%H:%M:%S')})"
                    )
                else:
                    reason = (
                        f"unexpected time restriction (current time: {now.strftime('%H:%M:%S')})"
                    )

                logger.warning(
                    f"Signals update skipped: {reason}. Analysis completed but results "
                    f"not persisted to Signals table.",
                    action="run_analysis",
                    task_name="analysis",
                )
                summary["skipped_reason"] = reason
                summary["skipped"] = len(processed_rows)
                return summary

            # Mark old signals as expired before adding new ones
            signals_repo = SignalsRepository(self.db)
            expired_count = signals_repo.mark_old_signals_as_expired()
            if expired_count > 0:
                logger.info(
                    f"Marked {expired_count} old signals as EXPIRED",
                    action="run_analysis",
                    task_name="analysis",
                )
                summary["expired"] = expired_count

            logger.info(
                f"Calling deduplicate_and_update_signals with {len(processed_rows)} signals",
                action="run_analysis",
                task_name="analysis",
            )
            # Skip time check since we already checked it above
            counts = dedup_service.deduplicate_and_update_signals(
                processed_rows, skip_time_check=True
            )
            logger.info(
                f"deduplicate_and_update_signals returned: {counts}",
                action="run_analysis",
                task_name="analysis",
            )
            summary.update(counts)
            logger.info(
                f"Signals updated successfully: {summary}",
                action="run_analysis",
                task_name="analysis",
            )
            return summary
        except Exception as e:
            logger.error(
                f"Failed to persist analysis results: {e}",
                exc_info=e,
                action="run_analysis",
                task_name="analysis",
            )
            summary["error"] = str(e)
            return summary

    def _normalize_analysis_row(self, row: dict) -> dict | None:
        """Normalize raw analysis result for persistence"""
        ticker = row.get("ticker") or row.get("symbol")
        if not ticker:
            return None

        normalized: dict[str, object] = {"ticker": ticker, "symbol": ticker.replace(".NS", "")}

        if "rsi10" in row:
            normalized["rsi10"] = row.get("rsi10")
        elif "rsi" in row:
            normalized["rsi10"] = row.get("rsi")

        if "ema9" in row:
            normalized["ema9"] = row.get("ema9")
        if "ema200" in row:
            normalized["ema200"] = row.get("ema200")
        if "distance_to_ema9" in row:
            normalized["distance_to_ema9"] = row.get("distance_to_ema9")

        if "volume_ratio" not in normalized:
            volume_analysis = row.get("volume_analysis")
            if isinstance(volume_analysis, dict):
                volume_ratio = volume_analysis.get("ratio")
                if volume_ratio is not None:
                    normalized["volume_ratio"] = volume_ratio

        if "clean_chart" not in normalized:
            chart_quality = row.get("chart_quality")
            if isinstance(chart_quality, dict):
                clean_status = (
                    chart_quality.get("status") == "clean" or chart_quality.get("passed") is True
                )
                if clean_status:
                    normalized["clean_chart"] = True
                elif "passed" in chart_quality:
                    normalized["clean_chart"] = chart_quality.get("passed")

        if "monthly_support_dist" not in normalized:
            timeframe_analysis = row.get("timeframe_analysis")
            if isinstance(timeframe_analysis, dict):
                daily_analysis = timeframe_analysis.get("daily_analysis", {})
                if isinstance(daily_analysis, dict):
                    support_analysis = daily_analysis.get("support_analysis", {})
                    if isinstance(support_analysis, dict):
                        support_dist = support_analysis.get("distance_pct")
                        if support_dist is not None:
                            normalized["monthly_support_dist"] = support_dist

        if "backtest_score" not in normalized:
            if "backtest_score" in row:
                normalized["backtest_score"] = row.get("backtest_score")
            else:
                backtest = row.get("backtest")
                if isinstance(backtest, dict):
                    normalized["backtest_score"] = backtest.get("score")
                elif isinstance(backtest, (int, float)):
                    normalized["backtest_score"] = backtest
        allowed_keys = {
            "rsi10",
            "rsi",
            "ema9",
            "ema200",
            "distance_to_ema9",
            "clean_chart",
            "monthly_support_dist",
            "confidence",
            "backtest_score",
            "combined_score",
            "strength_score",
            "priority_score",
            "ml_verdict",
            "ml_confidence",
            "ml_probabilities",
            "buy_range",
            "target",
            "stop",
            "last_close",
            "pe",
            "pb",
            "fundamental_assessment",
            "fundamental_ok",
            "avg_vol",
            "today_vol",
            "volume_analysis",
            "volume_pattern",
            "volume_description",
            "vol_ok",
            "volume_ratio",
            "verdict",
            "final_verdict",
            "rule_verdict",
            "verdict_source",
            "backtest_confidence",
            "vol_strong",
            "is_above_ema200",
            "dip_depth_from_20d_high_pct",
            "consecutive_red_days",
            "dip_speed_pct_per_day",
            "decline_rate_slowing",
            "volume_green_vs_red_ratio",
            "support_hold_count",
            "signals",
            "justification",
            "timeframe_analysis",
            "news_sentiment",
            "candle_analysis",
            "chart_quality",
            "execution_capital",
            "max_capital",
            "capital_adjusted",
            "liquidity_recommendation",
            "trading_params",
        }

        # Boolean fields that need conversion from string to bool
        boolean_fields = {
            "clean_chart",
            "fundamental_ok",
            "vol_ok",
            "vol_strong",
            "is_above_ema200",
            "decline_rate_slowing",
            "capital_adjusted",
        }

        for key in allowed_keys:
            # Skip if already set from special handling above
            if key in normalized:
                continue
            if key not in row:
                continue
            value = row.get(key)

            if key in boolean_fields and isinstance(value, str):
                value = value.lower() in ("true", "1", "yes", "on")
            elif key in {
                "buy_range",
                "volume_analysis",
                "timeframe_analysis",
                "signals",
                "news_sentiment",
                "candle_analysis",
                "liquidity_recommendation",
                "trading_params",
                "chart_quality",
                "ml_probabilities",
            }:
                value = self._parse_structured_field(value)

            normalized[key] = value

        if "priority_score" not in normalized:
            normalized["priority_score"] = row.get("priority_score") or row.get("combined_score")

        if "ts" not in normalized:
            normalized["ts"] = row.get("ts") or row.get("timestamp")
            if normalized["ts"] is None:
                from src.infrastructure.db.timezone_utils import ist_now  # noqa: PLC0415

                normalized["ts"] = ist_now()

        return normalized

    def _parse_structured_field(self, value: object) -> object:
        """Attempt to parse structured data stored as string"""
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                try:
                    return ast.literal_eval(text)
                except (ValueError, SyntaxError):
                    if "-" in text:
                        parsed = self._parse_buy_range(text)
                        if parsed:
                            return parsed
            return text
        return value

    @staticmethod
    def _parse_buy_range(value: str) -> dict | None:
        """Parse simple 'low-high' range strings into dict"""
        segments = value.split("-")
        if len(segments) != 2:
            return None
        try:
            low = float(segments[0].strip())
            high = float(segments[1].strip())
            return {"low": low, "high": high}
        except ValueError:
            return None

    def _spawn_service_process(self, user_id: int, task_name: str) -> subprocess.Popen:
        """Spawn a separate process for individual service"""
        # Create script path
        script_path = project_root / "scripts" / "run_individual_service.py"

        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")

        # Build command
        cmd = [
            sys.executable,
            str(script_path),
            "--user-id",
            str(user_id),
            "--task",
            task_name,
        ]

        logger = get_user_logger(user_id=user_id, db=self.db, module="IndividualService")
        logger.debug(
            f"Spawning process: {' '.join(cmd)}",
            action="spawn_process",
            task_name=task_name,
        )

        # Get DB_URL from environment to pass to child process
        env = os.environ.copy()
        db_url = os.getenv("DB_URL")
        if db_url:
            env["DB_URL"] = db_url
            logger.debug(
                f"Passing DB_URL={db_url} to child process",
                action="spawn_process",
                task_name=task_name,
            )

        # Spawn process
        process = subprocess.Popen(
            cmd,
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,  # Pass environment variables including DB_URL
        )

        logger.debug(
            f"Process spawned with PID: {process.pid}",
            action="spawn_process",
            task_name=task_name,
        )

        return process

    def _ensure_default_schedules(self) -> None:
        """Ensure default service schedules exist in the database"""
        # Skip check if already verified (optimization to avoid repeated DB queries)
        if self._schedules_checked:
            return

        from datetime import time  # noqa: PLC0415

        from src.infrastructure.persistence.service_schedule_repository import (  # noqa: PLC0415
            ServiceScheduleRepository,
        )

        schedule_repo = ServiceScheduleRepository(self.db)

        # Define default schedules
        default_schedules = [
            {
                "task_name": "premarket_retry",
                "schedule_time": time(9, 0),
                "enabled": True,
                "is_hourly": False,
                "is_continuous": False,
                "schedule_type": "daily",
                "description": "Retry failed orders from previous day",
            },
            {
                "task_name": "sell_monitor",
                "schedule_time": time(9, 15),
                "enabled": True,
                "is_hourly": False,
                "is_continuous": True,
                "end_time": time(15, 30),
                "schedule_type": "daily",
                "description": "Place sell orders and monitor continuously",
            },
            {
                "task_name": "position_monitor",
                "schedule_time": time(9, 30),
                "enabled": True,
                "is_hourly": True,
                "is_continuous": False,
                "schedule_type": "daily",
                "description": "Monitor positions for reentry/exit signals (hourly)",
            },
            {
                "task_name": "analysis",
                "schedule_time": time(16, 0),
                "enabled": True,
                "is_hourly": False,
                "is_continuous": False,
                "schedule_type": "daily",
                "description": "Analyze stocks and generate recommendations (admin-only)",
            },
            {
                "task_name": "buy_orders",
                "schedule_time": time(16, 5),
                "enabled": True,
                "is_hourly": False,
                "is_continuous": False,
                "schedule_type": "daily",
                "description": "Place AMO buy orders for next day",
            },
            {
                "task_name": "eod_cleanup",
                "schedule_time": time(18, 0),
                "enabled": True,
                "is_hourly": False,
                "is_continuous": False,
                "schedule_type": "daily",
                "description": "End-of-day cleanup and reset for next day",
            },
        ]

        # Create any missing default schedules (check each individually)
        created_any = False
        for schedule_data in default_schedules:
            existing = schedule_repo.get_by_task_name(schedule_data["task_name"])
            if not existing:
                schedule_repo.create_or_update(**schedule_data)
                created_any = True

        if created_any:
            self.db.commit()

        # Mark as checked to avoid repeated queries
        self._schedules_checked = True

    def get_status(self, user_id: int) -> dict:
        """Get status of all individual services for a user"""
        # Expire all cached objects to ensure we get fresh data from database
        # This is important because execution status is updated in separate threads
        self.db.expire_all()

        # Ensure default schedules exist (auto-create if missing)
        self._ensure_default_schedules()

        services = self._status_repo.list_by_user(user_id)
        schedules = self._schedule_manager.get_all_schedules()

        # Create a dict of existing service statuses
        service_statuses = {s.task_name: s for s in services}

        result = {}
        # Return status for all scheduled tasks
        for schedule in schedules:
            task_name = schedule.task_name
            service = service_statuses.get(task_name)
            # Query fresh from database to get latest execution status
            # Use raw SQL to bypass session cache and see commits from other threads
            latest_execution_raw = self._execution_repo.get_latest_status_raw(user_id, task_name)

            # Get the full ORM object if we need it, but use raw status for checking
            latest_execution = self._execution_repo.get_latest(user_id, task_name)

            # Override status from raw query if available (more reliable across threads)
            if latest_execution_raw and latest_execution:
                latest_execution.status = latest_execution_raw["status"]
                # Update other fields from raw query
                if latest_execution_raw.get("details"):
                    latest_execution.details = latest_execution_raw["details"]
                if latest_execution_raw.get("duration_seconds") is not None:
                    latest_execution.duration_seconds = latest_execution_raw["duration_seconds"]

            next_execution = (
                self._schedule_manager.calculate_next_execution(task_name)
                if schedule.enabled
                else None
            )

            # Use execution record's executed_at if service status doesn't have last_execution_at
            last_execution_at = None
            if service and service.last_execution_at:
                last_execution_at = service.last_execution_at.isoformat()
            elif latest_execution and latest_execution.executed_at:
                last_execution_at = latest_execution.executed_at.isoformat()

            # Check if thread is still running for "run once" tasks
            thread_key = (user_id, task_name)
            thread = self._run_once_threads.get(thread_key)
            thread_is_alive = thread.is_alive() if thread else False

            # If execution status is "running" but thread is not alive, query fresh from database
            if latest_execution and latest_execution.status == "running" and not thread_is_alive:
                # Thread finished but DB might not be updated yet, or we have stale data
                # Use raw SQL to get truly fresh status (bypasses all session caching)
                latest_execution_raw = self._execution_repo.get_latest_status_raw(
                    user_id, task_name
                )
                if latest_execution_raw:
                    # Update the execution object with fresh status from raw query
                    latest_execution.status = latest_execution_raw["status"]
                    if latest_execution_raw.get("details"):
                        latest_execution.details = latest_execution_raw["details"]
                    if latest_execution_raw.get("duration_seconds") is not None:
                        latest_execution.duration_seconds = latest_execution_raw["duration_seconds"]
                else:
                    # No execution found, get fresh ORM object
                    self.db.expire_all()
                    latest_execution = self._execution_repo.get_latest(user_id, task_name)

                # Log for debugging
                if latest_execution:
                    logger = get_user_logger(
                        user_id=user_id, db=self.db, module="IndividualService"
                    )
                    logger.debug(
                        f"Thread finished for {task_name}, refreshed execution "
                        f"status: {latest_execution.status}",
                        action="get_status",
                        task_name=task_name,
                    )

            # Check for stale "running" executions (timeout check)
            # Use raw SQL to check actual database status (bypasses session cache)
            if latest_execution_raw and latest_execution_raw["status"] == "running":
                from datetime import timedelta  # noqa: PLC0415

                from src.infrastructure.db.timezone_utils import IST, ist_now  # noqa: PLC0415

                # Normalize executed_at to timezone-aware if it's naive
                executed_at = latest_execution_raw["executed_at"]
                if executed_at.tzinfo is None:
                    executed_at = executed_at.replace(tzinfo=IST)

                execution_age = ist_now() - executed_at
                timeout_minutes = 5
                if execution_age > timedelta(minutes=timeout_minutes):
                    # Mark stale execution as failed (regardless of thread status)
                    logger = get_user_logger(
                        user_id=user_id, db=self.db, module="IndividualService"
                    )
                    logger.warning(
                        f"Detected stale 'running' execution for {task_name} "
                        f"(age: {execution_age.total_seconds():.0f}s, "
                        f"thread_alive: {thread_is_alive}). Marking as failed.",
                        action="get_status",
                        task_name=task_name,
                    )
                    # Use raw SQL to update status directly (bypasses session issues)
                    from sqlalchemy import text  # noqa: PLC0415

                    update_sql = text(
                        """
                        UPDATE individual_service_task_execution
                        SET status = 'failed',
                            details = json_object(
                                'error', 'Execution timed out or process crashed',
                                'stale_execution', 1,
                                'age_seconds', :age_seconds,
                                'thread_was_alive', :thread_alive
                            )
                        WHERE id = :execution_id AND status = 'running'
                    """
                    )
                    self.db.execute(
                        update_sql,
                        {
                            "execution_id": latest_execution_raw["id"],
                            "age_seconds": execution_age.total_seconds(),
                            "thread_alive": 1 if thread_is_alive else 0,
                        },
                    )
                    self.db.commit()
                    # Refresh the raw status after update
                    latest_execution_raw = self._execution_repo.get_latest_status_raw(
                        user_id, task_name
                    )
                    if latest_execution_raw and latest_execution:
                        latest_execution.status = latest_execution_raw["status"]
                        latest_execution.details = latest_execution_raw.get("details")
                    # Clean up thread reference if it exists
                    if thread_key in self._run_once_threads:
                        del self._run_once_threads[thread_key]

            process_id = None
            if service and service.process_id:
                process_key = (user_id, task_name)
                internal_process = self._processes.get(process_key)
                if internal_process:
                    if internal_process.poll() is None:
                        process_id = service.process_id
                        if not service.is_running:
                            logger = get_user_logger(
                                user_id=user_id, db=self.db, module="IndividualService"
                            )
                            logger.info(
                                f"Internal process for {task_name} is alive but DB says "
                                f"stopped. Syncing DB to running.",
                                action="get_status",
                                task_name=task_name,
                            )
                            self._status_repo.mark_running(
                                user_id, task_name, process_id=process_id
                            )
                            self.db.commit()
                            service = self._status_repo.get_by_user_and_task(user_id, task_name)
                    else:
                        logger = get_user_logger(
                            user_id=user_id, db=self.db, module="IndividualService"
                        )
                        logger.warning(
                            f"Internal process for {task_name} is dead. Marking service as stopped.",
                            action="get_status",
                            task_name=task_name,
                        )
                        self._status_repo.mark_stopped(user_id, task_name)
                        service = self._status_repo.get_by_user_and_task(user_id, task_name)
                else:
                    process_exists = False
                    try:
                        if os.name == "nt":  # Windows
                            proc_result = subprocess.run(
                                ["tasklist", "/FI", f"PID eq {service.process_id}"],
                                capture_output=True,
                                text=True,
                                timeout=2,
                                check=False,
                            )
                            process_exists = (
                                proc_result.returncode == 0
                                and proc_result.stdout
                                and str(service.process_id) in proc_result.stdout
                            )
                        else:  # Unix/Linux
                            proc_path = Path(f"/proc/{service.process_id}")
                            if proc_path.exists():
                                process_exists = True
                            else:
                                proc_result = subprocess.run(
                                    ["kill", "-0", str(service.process_id)],
                                    capture_output=True,
                                    timeout=2,
                                    check=False,
                                )
                                process_exists = proc_result.returncode == 0
                    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, PermissionError):
                        # Can't check, assume doesn't exist to be safe
                        process_exists = False

                    if process_exists:
                        process_id = service.process_id
                        if not service.is_running:
                            logger = get_user_logger(
                                user_id=user_id, db=self.db, module="IndividualService"
                            )
                            logger.info(
                                f"Process {service.process_id} for {task_name} exists in OS but DB says stopped. Syncing DB to running.",
                                action="get_status",
                                task_name=task_name,
                            )
                            self._status_repo.mark_running(
                                user_id, task_name, process_id=process_id
                            )
                            self.db.commit()
                            service = self._status_repo.get_by_user_and_task(user_id, task_name)
                    else:
                        process_id = service.process_id if service.is_running else None

            # Determine actual execution status - use raw status (most reliable)
            actual_execution_status = None
            if latest_execution_raw:
                actual_execution_status = latest_execution_raw["status"]
            elif latest_execution:
                actual_execution_status = latest_execution.status

            if actual_execution_status == "running" and latest_execution_raw:
                from datetime import timedelta  # noqa: PLC0415

                from src.infrastructure.db.timezone_utils import IST, ist_now  # noqa: PLC0415

                executed_at = latest_execution_raw["executed_at"]
                if executed_at.tzinfo is None:
                    executed_at = executed_at.replace(tzinfo=IST)
                execution_age = ist_now() - executed_at

                timeout_minutes = 5
                if execution_age > timedelta(minutes=timeout_minutes):
                    actual_execution_status = "failed"
                    logger = get_user_logger(
                        user_id=user_id, db=self.db, module="IndividualService"
                    )
                    logger.warning(
                        f"Forcing execution status to 'failed' in response for {task_name} (age: {execution_age.total_seconds():.0f}s) - database update may have failed",
                        action="get_status",
                        task_name=task_name,
                    )

            # Get is_running from service status (synced above if needed)
            is_running = service.is_running if service else False

            result_data = {
                "is_running": is_running,
                "started_at": (
                    service.started_at.isoformat() if service and service.started_at else None
                ),
                "last_execution_at": last_execution_at,
                "next_execution_at": (next_execution.isoformat() if next_execution else None),
                "process_id": process_id,
                "schedule_enabled": schedule.enabled,
            }
            if latest_execution:
                result_data["last_execution_status"] = actual_execution_status
                result_data["last_execution_duration"] = latest_execution.duration_seconds
                result_data["last_execution_details"] = latest_execution.details
            else:
                result_data["last_execution_status"] = None
                result_data["last_execution_duration"] = None
                result_data["last_execution_details"] = None

            result[task_name] = result_data

        return result

    def _get_telegram_notifier(self, user_id: int):
        """Get Telegram notifier instance with database session and user-specific chat ID"""
        if not TELEGRAM_NOTIFIER_AVAILABLE:
            return None
        try:
            # Get user's notification preferences to get Telegram chat ID
            from services.notification_preference_service import NotificationPreferenceService

            pref_service = NotificationPreferenceService(self.db)
            preferences = pref_service.get_preferences(user_id)

            # Check if Telegram is enabled for this user
            if not preferences or not preferences.telegram_enabled:
                return None

            # Get bot token from environment (global) and chat ID from user preferences
            import os

            bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
            chat_id = preferences.telegram_chat_id if preferences else None

            # Only create notifier if both bot token and chat ID are available
            if not bot_token:
                return None
            if not chat_id:
                return None

            # Create a new TelegramNotifier instance (not singleton) for this user
            # This is necessary because each user has a different chat_id
            from modules.kotak_neo_auto_trader.telegram_notifier import TelegramNotifier

            return TelegramNotifier(
                bot_token=bot_token,
                chat_id=chat_id,
                enabled=True,
                db_session=self.db,
            )
        except Exception as e:
            # Use module-level logger if available, otherwise skip logging
            try:
                from utils.logger import logger as utils_logger

                utils_logger.warning(f"Failed to get Telegram notifier: {e}")
            except ImportError:
                pass  # Logger not available
            return None

    def _notify_service_started(
        self, user_id: int, task_name: str, process_id: int | None = None
    ) -> None:
        """Send notification when a service is started"""
        task_display_name = task_name.replace("_", " ").title()
        message_text = f"Service: {task_display_name}"
        if process_id:
            message_text += f"\nProcess ID: {process_id}"
        message_text += "\nStatus: Running"

        # Check user preferences
        from services.notification_preference_service import (
            NotificationEventType,
            NotificationPreferenceService,
        )

        pref_service = NotificationPreferenceService(self.db)

        # Send Telegram notification if enabled and preference allows
        if pref_service.should_notify(
            user_id, NotificationEventType.SERVICE_STARTED, channel="telegram"
        ):
            notifier = self._get_telegram_notifier(user_id)
            if notifier and notifier.enabled:
                try:
                    notifier.notify_system_alert(
                        alert_type="SERVICE_STARTED",
                        message_text=f"Service Started\n\n{message_text}",
                        severity="INFO",
                        user_id=user_id,
                    )
                except Exception as e:
                    try:
                        from utils.logger import logger as utils_logger

                        utils_logger.warning(f"Failed to send Telegram notification: {e}")
                    except ImportError:
                        pass

        # Create in-app notification first (so we can track email delivery status)
        notification = None
        if pref_service.should_notify(
            user_id, NotificationEventType.SERVICE_STARTED, channel="in_app"
        ):
            try:
                notification = self._notification_repo.create(
                    user_id=user_id,
                    type="service",
                    level="info",
                    title="Service Started",
                    message=message_text,
                )
                logger = get_user_logger(user_id=user_id, db=self.db, module="IndividualService")
                logger.info(
                    f"Created in-app notification for service start: {task_name}",
                    action="notify_service_started",
                    notification_id=notification.id,
                )
            except Exception as e:
                logger = get_user_logger(user_id=user_id, db=self.db, module="IndividualService")
                logger.error(
                    f"Failed to create in-app notification for service start: {e}",
                    exc_info=e,
                    action="notify_service_started",
                )

        # Send Email notification if enabled and preference allows
        email_sent = False
        if pref_service.should_notify(
            user_id, NotificationEventType.SERVICE_STARTED, channel="email"
        ):
            preferences = pref_service.get_preferences(user_id)
            if preferences and preferences.email_address:
                if EMAIL_NOTIFIER_AVAILABLE:
                    try:
                        email_notifier = EmailNotifier()
                        if email_notifier.is_available():
                            email_sent = email_notifier.send_service_notification(
                                to_email=preferences.email_address,
                                title="Service Started",
                                message=message_text,
                                level="info",
                            )
                            # Update notification delivery status if notification was created
                            if notification and email_sent:
                                self._notification_repo.update_delivery_status(
                                    notification_id=notification.id, email_sent=True
                                )
                    except Exception as e:
                        try:
                            from utils.logger import logger as utils_logger

                            utils_logger.warning(f"Failed to send email notification: {e}")
                        except ImportError:
                            pass

    def _notify_service_stopped(self, user_id: int, task_name: str) -> None:
        """Send notification when a service is stopped"""
        task_display_name = task_name.replace("_", " ").title()
        message_text = f"Service: {task_display_name}\nStatus: Stopped"

        # Check user preferences
        from services.notification_preference_service import (
            NotificationEventType,
            NotificationPreferenceService,
        )

        pref_service = NotificationPreferenceService(self.db)

        # Send Telegram notification if enabled and preference allows
        if pref_service.should_notify(
            user_id, NotificationEventType.SERVICE_STOPPED, channel="telegram"
        ):
            notifier = self._get_telegram_notifier(user_id)
            if notifier and notifier.enabled:
                try:
                    notifier.notify_system_alert(
                        alert_type="SERVICE_STOPPED",
                        message_text=f"Service Stopped\n\n{message_text}",
                        severity="INFO",
                        user_id=user_id,
                    )
                except Exception as e:
                    try:
                        from utils.logger import logger as utils_logger

                        utils_logger.warning(f"Failed to send Telegram notification: {e}")
                    except ImportError:
                        pass

        # Create in-app notification first (so we can track email delivery status)
        notification = None
        if pref_service.should_notify(
            user_id, NotificationEventType.SERVICE_STOPPED, channel="in_app"
        ):
            try:
                notification = self._notification_repo.create(
                    user_id=user_id,
                    type="service",
                    level="info",
                    title="Service Stopped",
                    message=message_text,
                )
            except Exception as e:
                try:
                    from utils.logger import logger as utils_logger

                    utils_logger.warning(f"Failed to create in-app notification: {e}")
                except ImportError:
                    pass

        # Send Email notification if enabled and preference allows
        email_sent = False
        if pref_service.should_notify(
            user_id, NotificationEventType.SERVICE_STOPPED, channel="email"
        ):
            preferences = pref_service.get_preferences(user_id)
            if preferences and preferences.email_address:
                if EMAIL_NOTIFIER_AVAILABLE:
                    try:
                        email_notifier = EmailNotifier()
                        if email_notifier.is_available():
                            email_sent = email_notifier.send_service_notification(
                                to_email=preferences.email_address,
                                title="Service Stopped",
                                message=message_text,
                                level="info",
                            )
                            # Update notification delivery status if notification was created
                            if notification and email_sent:
                                self._notification_repo.update_delivery_status(
                                    notification_id=notification.id, email_sent=True
                                )
                    except Exception as e:
                        try:
                            from utils.logger import logger as utils_logger

                            utils_logger.warning(f"Failed to send email notification: {e}")
                        except ImportError:
                            pass

    def _notify_service_execution_completed(
        self, user_id: int, task_name: str, status: str, duration: float, error: str | None = None
    ) -> None:
        """Send notification when a service execution completes (success or failure)"""
        task_display_name = task_name.replace("_", " ").title()
        duration_str = f"{duration:.2f}s" if duration < 60 else f"{duration / 60:.1f}m"

        # Check user preferences
        from services.notification_preference_service import (
            NotificationEventType,
            NotificationPreferenceService,
        )

        pref_service = NotificationPreferenceService(self.db)
        preferences = pref_service.get_preferences(user_id)

        if status == "success":
            title = "Service Execution Completed"
            message_text = (
                f"Service: {task_display_name}\nStatus: Success\nDuration: {duration_str}"
            )
            level = "info"
            severity = "SUCCESS"
        else:
            title = "Service Execution Failed"
            message_text = f"Service: {task_display_name}\nStatus: Failed\nDuration: {duration_str}"
            if error:
                # Truncate error message if too long
                error_msg = error[:200] + "..." if len(error) > 200 else error
                message_text += f"\nError: {error_msg}"
            level = "error"
            severity = "ERROR"

        # Send Telegram notification if enabled and preference allows
        if pref_service.should_notify(
            user_id, NotificationEventType.SERVICE_EXECUTION_COMPLETED, channel="telegram"
        ):
            notifier = self._get_telegram_notifier(user_id)
            if notifier and notifier.enabled:
                try:
                    notifier.notify_system_alert(
                        alert_type="SERVICE_EXECUTION",
                        message_text=f"{title}\n\n{message_text}",
                        severity=severity,
                        user_id=user_id,
                    )
                except Exception as e:
                    try:
                        from utils.logger import logger as utils_logger

                        utils_logger.warning(f"Failed to send Telegram notification: {e}")
                    except ImportError:
                        pass

        # Create in-app notification first (so we can track email delivery status)
        notification = None
        if pref_service.should_notify(
            user_id, NotificationEventType.SERVICE_EXECUTION_COMPLETED, channel="in_app"
        ):
            try:
                notification = self._notification_repo.create(
                    user_id=user_id,
                    type="service",
                    level=level,
                    title=title,
                    message=message_text,
                )
            except Exception as e:
                try:
                    from utils.logger import logger as utils_logger

                    utils_logger.warning(f"Failed to create in-app notification: {e}")
                except ImportError:
                    pass

        # Send Email notification if enabled and preference allows
        email_sent = False
        if pref_service.should_notify(
            user_id, NotificationEventType.SERVICE_EXECUTION_COMPLETED, channel="email"
        ):
            preferences = pref_service.get_preferences(user_id)
            if preferences and preferences.email_address:
                if EMAIL_NOTIFIER_AVAILABLE:
                    try:
                        email_notifier = EmailNotifier()
                        if email_notifier.is_available():
                            email_sent = email_notifier.send_service_notification(
                                to_email=preferences.email_address,
                                title=title,
                                message=message_text,
                                level=level,
                            )
                            # Update notification delivery status if notification was created
                            if notification and email_sent:
                                self._notification_repo.update_delivery_status(
                                    notification_id=notification.id, email_sent=True
                                )
                    except Exception as e:
                        try:
                            from utils.logger import logger as utils_logger

                            utils_logger.warning(f"Failed to send email notification: {e}")
                        except ImportError:
                            pass

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
