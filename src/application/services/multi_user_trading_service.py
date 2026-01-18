"""
Multi-User Trading Service Wrapper

Manages trading service instances for multiple users, ensuring isolation
and proper lifecycle management.
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime
from datetime import time as dt_time
from typing import Any

from sqlalchemy.orm import Session

import modules.kotak_neo_auto_trader.run_trading_service as trading_service_module
from services.notification_preference_service import (
    NotificationEventType,
    NotificationPreferenceService,
)
from src.application.services.broker_credentials import (
    create_temp_env_file,
    decrypt_broker_credentials,
)
from src.application.services.config_converter import user_config_to_strategy_config
from src.application.services.paper_trading_service_adapter import PaperTradingServiceAdapter
from src.application.services.schedule_manager import ScheduleManager
from src.infrastructure.logging import get_user_logger
from src.infrastructure.persistence.notification_repository import NotificationRepository
from src.infrastructure.persistence.service_status_repository import ServiceStatusRepository
from src.infrastructure.persistence.settings_repository import SettingsRepository
from src.infrastructure.persistence.user_trading_config_repository import (
    UserTradingConfigRepository,
)


def _is_sell_monitor_running(db_session, user_id: int) -> bool:
    """
    Check if sell_monitor task is currently running by querying the database.

    This prevents overlapping executions when the scheduler runs every minute.

    Args:
        db_session: Database session
        user_id: User ID

    Returns:
        True if task is running, False otherwise
    """
    try:
        from src.infrastructure.persistence.individual_service_task_execution_repository import (
            IndividualServiceTaskExecutionRepository,
        )

        execution_repo = IndividualServiceTaskExecutionRepository(db_session)
        running_executions = execution_repo.get_running_tasks_raw(user_id, "sell_monitor")

        return len(running_executions) > 0
    except Exception:
        # If check fails, assume not running to avoid blocking
        return False


def _try_acquire_paper_scheduler_lock(db_session, user_id: int) -> tuple[bool, str | None]:
    """
    Ensure only ONE paper-trading scheduler loop runs per user across processes.

    Uses table-based locking instead of PostgreSQL advisory locks (which are problematic
    with connection pooling). This works with any database and any connection.

    Returns (acquired, lock_id).
    """
    try:
        from src.infrastructure.db.models import SchedulerLock
        from src.infrastructure.db.timezone_utils import ist_now
        from datetime import timedelta
        import uuid

        # Generate unique lock ID for this instance
        lock_id = str(uuid.uuid4())

        # Lock expires after 5 minutes (stale locks auto-cleanup)
        expires_at = ist_now() + timedelta(minutes=5)

        # Clean up stale locks first (expired locks)
        try:
            db_session.query(SchedulerLock).filter(
                SchedulerLock.expires_at < ist_now()
            ).delete()
            db_session.commit()
        except Exception:
            db_session.rollback()

        # Try to acquire lock: INSERT if user_id doesn't exist
        try:
            # Use INSERT ... ON CONFLICT (PostgreSQL) or try/except (SQLite)
            bind = getattr(db_session, "bind", None)
            dialect_name = getattr(getattr(bind, "dialect", None), "name", "")

            if dialect_name == "postgresql":
                from sqlalchemy import text  # noqa: PLC0415
                # PostgreSQL: Use INSERT ... ON CONFLICT DO NOTHING
                result = db_session.execute(
                    text("""
                        INSERT INTO scheduler_lock (user_id, locked_at, lock_id, expires_at, created_at)
                        VALUES (:user_id, :locked_at, :lock_id, :expires_at, :created_at)
                        ON CONFLICT (user_id) DO NOTHING
                        RETURNING lock_id
                    """),
                    {
                        "user_id": user_id,
                        "locked_at": ist_now(),
                        "lock_id": lock_id,
                        "expires_at": expires_at,
                        "created_at": ist_now(),
                    }
                )
                row = result.fetchone()
                if row:
                    # Lock acquired
                    db_session.commit()
                    return True, lock_id
                else:
                    # Lock already held by another instance
                    db_session.rollback()
                    return False, None
            else:
                # SQLite or other: Use try/except
                try:
                    lock = SchedulerLock(
                        user_id=user_id,
                        locked_at=ist_now(),
                        lock_id=lock_id,
                        expires_at=expires_at,
                    )
                    db_session.add(lock)
                    db_session.commit()
                    return True, lock_id
                except Exception:
                    # Lock already exists (unique constraint violation)
                    db_session.rollback()
                    return False, None
        except Exception as e:
            db_session.rollback()
            # Log but don't fail - allow scheduler to run
            import logging
            logging.warning(f"Failed to acquire scheduler lock for user {user_id}: {e}")
            return False, None
    except Exception:
        # Fail open: don't block scheduler on unexpected DB issues
        return True, None


def _release_paper_scheduler_lock(db_session, lock_id: str | None) -> None:
    """Release table-based scheduler lock (best-effort)."""
    if lock_id is None:
        return
    try:
        from src.infrastructure.db.models import SchedulerLock

        # Delete lock by lock_id (only release our own lock)
        db_session.query(SchedulerLock).filter(
            SchedulerLock.lock_id == lock_id
        ).delete()
        db_session.commit()
    except Exception:
        db_session.rollback()
        pass


def _cleanup_stale_paper_scheduler_lock(
    db_session: Session, user_id: int, logger
) -> bool:
    """
    Clean up stale table-based lock held by dead thread.

    Strategy:
    1. Delete expired locks (auto-cleanup)
    2. Delete lock for this user_id if it exists (force cleanup)
    3. Log detailed information for debugging

    Args:
        db_session: Database session to use for lock operations
        user_id: User ID
        logger: Logger instance for detailed logging

    Returns:
        True if lock was successfully cleaned up, False otherwise
    """
    try:
        from src.infrastructure.db.models import SchedulerLock
        from src.infrastructure.db.timezone_utils import ist_now

        logger.info(
            f"Attempting to clean up stale scheduler lock for user {user_id}",
            action="start_service",
        )

        # Delete expired locks and locks for this user
        deleted = db_session.query(SchedulerLock).filter(
            (SchedulerLock.user_id == user_id) | (SchedulerLock.expires_at < ist_now())
        ).delete()
        db_session.commit()

        if deleted > 0:
            logger.info(
                f"Successfully cleaned up {deleted} stale lock(s) for user {user_id}",
                action="start_service",
            )
            return True
        else:
            logger.debug(
                f"No stale locks found for user {user_id}",
                action="start_service",
            )
            return True  # No locks to clean up is also success
    except Exception as e:
        logger.warning(
            f"Failed to cleanup stale lock for user {user_id}: {e}",
            action="start_service",
        )
        db_session.rollback()
        return False


# CRITICAL: Module-level shared state for thread and service references
# This ensures all MultiUserTradingService instances share the same thread/service dictionaries
# because FastAPI creates a new instance for each API request via dependency injection
_shared_services: dict[int, any] = {}  # user_id -> TradingService instance
_shared_service_threads: dict[int, threading.Thread] = {}  # user_id -> scheduler thread
_shared_locks: dict[int, threading.Lock] = {}  # user_id -> service lock
_shared_start_locks: dict[int, threading.Lock] = {}  # Per-user locks to prevent concurrent starts
_shared_lock_keys: dict[int, str | None] = {}  # user_id -> table-based lock_id (for cleanup on stop)
_shared_state_lock = threading.Lock()  # Lock for thread-safe access to shared state


class MultiUserTradingService:
    """
    Manages trading services for multiple users.

    Each user gets their own isolated TradingService instance with:
    - User-specific broker credentials
    - User-specific trading configuration
    - User-specific data isolation
    - Independent service lifecycle

    NOTE: Uses module-level shared state for thread/service references because
    FastAPI creates a new instance for each API request via dependency injection.
    """

    def __init__(self, db: Session):
        """
        Initialize multi-user trading service manager.

        Args:
            db: Database session
        """
        self.db = db
        # Use module-level shared state so all instances share thread/service references
        self._services = _shared_services
        self._service_threads = _shared_service_threads
        self._locks = _shared_locks
        self._start_locks = _shared_start_locks
        self._lock_keys = _shared_lock_keys  # Module-level lock keys for cleanup
        self._temp_env_files: dict[int, str] = {}  # user_id -> temp env file path (for cleanup)
        self._service_status_repo = ServiceStatusRepository(db)
        self._settings_repo = SettingsRepository(db)
        self._config_repo = UserTradingConfigRepository(db)
        self._notification_repo = NotificationRepository(db)
        self._logger = get_user_logger(
            user_id=0, db=db, module="MultiUserTradingService"
        )  # System-level logger
        self._task_name = "unified_service"
        # Expose ScheduleManager type for tests/introspection without creating a shared instance
        # Actual scheduler uses thread-local instances with thread-local DB sessions
        self._schedule_manager = ScheduleManager

    def get_schedule_manager(self, db_session: Session) -> ScheduleManager:
        """Return a ScheduleManager bound to the provided session.

        Callers are responsible for creating and managing the lifecycle of the
        SQLAlchemy session passed here (e.g., thread-local SessionLocal inside
        scheduler threads). This helper keeps the intended usage explicit and
        avoids accidental reuse of shared state across threads.
        """
        if db_session is None:
            raise ValueError("db_session is required to create a ScheduleManager")

        return self._schedule_manager(db_session)

    def _run_paper_trading_scheduler(  # noqa: PLR0912, PLR0915
        self, service: PaperTradingServiceAdapter, user_id: int
    ):
        """
        Run paper trading service scheduler in background thread.

        CRITICAL: Creates its own database session to avoid thread-safety issues.
        SQLAlchemy sessions are NOT thread-safe and cannot be shared across threads.

        Args:
            service: PaperTradingServiceAdapter instance
            user_id: User ID for this service
        """
        # Create a new database session for this thread
        from src.infrastructure.db.connection_monitor import log_pool_status  # noqa: PLC0415
        from src.infrastructure.db.session import SessionLocal, engine  # noqa: PLC0415

        thread_db = SessionLocal()

        # Create user logger early so it can be used throughout the function
        user_logger = get_user_logger(user_id=user_id, db=thread_db, module="PaperTradingScheduler")

        lock_id: str | None = None
        try:
            # Try to acquire lock with retries to handle stale locks from dead threads
            # This is a defensive approach - cleanup in start_service() should handle most cases
            # But we still retry here as a safety net with longer delays for connection pool recycling
            # CRITICAL: Before failing, check if there's actually another running thread
            # If no thread is running, the lock is held by a dead connection - wait longer
            max_lock_retries = 5  # Increased from 3 to 5 to handle slow connection pool recycling
            lock_retry_delays = [2.0, 3.0, 5.0, 10.0, 15.0]  # Longer delays for connection pool recycling
            acquired = False

            user_logger.info(
                f"Attempting to acquire scheduler lock for user {user_id}...",
                action="scheduler",
            )

            for lock_retry in range(max_lock_retries):
                acquired, lock_id = _try_acquire_paper_scheduler_lock(thread_db, user_id)
                if acquired:
                    if lock_retry > 0:
                        user_logger.info(
                            f"Successfully acquired scheduler lock on retry attempt {lock_retry + 1}",
                            action="scheduler",
                        )
                    else:
                        user_logger.info(
                            f"Successfully acquired scheduler lock for user {user_id}",
                            action="scheduler",
                        )
                    break

                # Lock not acquired - check if there's actually another running thread
                # Use module-level shared state to check for other threads
                # Note: This thread might not be in _shared_service_threads yet (stored in start_service)
                # So we check if there's ANOTHER thread (different object ID) that's alive
                current_thread_id = id(threading.current_thread())
                other_thread = _shared_service_threads.get(user_id)
                other_thread_alive = other_thread and other_thread.is_alive() if other_thread else False

                # Check if this is a different thread (compare thread object IDs)
                # If the stored thread is this thread, then no other thread is running
                is_different_thread = other_thread is not None and id(other_thread) != current_thread_id

                if other_thread_alive and is_different_thread:
                    # Another thread is actually running - don't retry
                    user_logger.warning(
                        f"Lock not acquired for user {user_id} and another scheduler thread "
                        f"(thread_id={id(other_thread)}) is running. "
                        "Exiting this scheduler thread.",
                        action="scheduler",
                    )
                    return

                # No other thread running - lock is held by dead connection in pool
                user_logger.warning(
                    f"Lock not acquired on attempt {lock_retry + 1}/{max_lock_retries} "
                    f"for user {user_id}. No other thread running - lock held by dead connection in pool. "
                    "This may indicate a stale lock from a dead thread.",
                    action="scheduler",
                )

                if lock_retry < max_lock_retries - 1:
                    # Wait longer - the old connection might need more time to close/recycle
                    delay = lock_retry_delays[lock_retry]
                    user_logger.info(
                        f"Waiting {delay}s for stale lock to be released before retry "
                        f"(attempt {lock_retry + 1}/{max_lock_retries})...",
                        action="scheduler",
                    )
                    time.sleep(delay)

            # After all retries, check one more time if another thread is running
            # This handles race conditions where another thread started while we were retrying
            if not acquired:
                current_thread_obj = threading.current_thread()
                current_thread_id = id(current_thread_obj)

                other_thread = _shared_service_threads.get(user_id)
                other_thread_alive = other_thread and other_thread.is_alive() if other_thread else False

                # Check if this is a different thread (compare thread object IDs)
                is_different_thread = other_thread is not None and id(other_thread) != current_thread_id

                if other_thread_alive and is_different_thread:
                    # Another thread started while we were retrying - don't fail
                    user_logger.info(
                        f"Another scheduler thread (thread_id={id(other_thread)}) started while retrying. "
                        "Exiting this scheduler thread.",
                        action="scheduler",
                    )
                    return

                # No thread running after all retries - lock is held by dead connection
                # Connection pool recycles every hour, but we can wait a bit more
                # since we know no other thread is running (the lock is definitely stale)
                user_logger.warning(
                    f"Could not acquire scheduler lock for user {user_id} after "
                    f"{max_lock_retries} attempts. No other thread is running - lock is held by dead connection. "
                    "Waiting additional time for connection pool to recycle...",
                    action="scheduler",
                )

                # Final wait: if no other thread is running, we know the lock is stale
                # Wait up to 2 more minutes (120s) checking every 10 seconds
                final_wait_interval = 10
                final_wait_max = 120
                final_wait_elapsed = 0

                while final_wait_elapsed < final_wait_max:
                    time.sleep(final_wait_interval)
                    final_wait_elapsed += final_wait_interval

                    # Try to acquire lock again
                    acquired, lock_id = _try_acquire_paper_scheduler_lock(thread_db, user_id)
                    if acquired:
                        user_logger.info(
                            f"Successfully acquired scheduler lock for user {user_id} after "
                            f"additional {final_wait_elapsed}s wait (connection pool recycled).",
                            action="scheduler",
                        )
                        break

                    # Check if another thread started while waiting
                    other_thread = _shared_service_threads.get(user_id)
                    other_thread_alive = other_thread and other_thread.is_alive() if other_thread else False
                    is_different_thread = other_thread is not None and id(other_thread) != current_thread_id

                    if other_thread_alive and is_different_thread:
                        user_logger.info(
                            f"Another scheduler thread (thread_id={id(other_thread)}) started while waiting. "
                            "Exiting this scheduler thread.",
                            action="scheduler",
                        )
                        return

                    user_logger.debug(
                        f"Lock still held for user {user_id} after {final_wait_elapsed}s. "
                        f"Waiting {final_wait_interval}s more...",
                        action="scheduler",
                    )

                if not acquired:
                    # Still couldn't acquire after extended wait
                    user_logger.error(
                        f"Could not acquire scheduler lock for user {user_id} after "
                        f"{max_lock_retries} initial attempts + {final_wait_elapsed}s extended wait. "
                        "Lock is held by dead connection in pool. Connection pool recycles every hour. "
                        "Exiting this scheduler thread. The service will need to wait for connection pool recycling "
                        "or you can restart the service/database to release the stale lock.",
                        action="scheduler",
                    )
                    return

            # Create thread-local ScheduleManager to avoid session conflicts
            # CRITICAL: Use thread_db instead of main thread's session
            thread_schedule_manager = ScheduleManager(thread_db)

            user_logger.info("Paper trading scheduler started", action="scheduler")

            # Store lock_id in shared state so stop_service() can track it
            self._lock_keys[user_id] = lock_id

            service.running = True
            last_check = None
            heartbeat_counter = 0  # Log heartbeat every 5 minutes
            pool_log_counter = 0  # Log pool status every 15 minutes

            # Initial heartbeat on start to ensure early commit/rollback paths are exercised
            try:
                thread_status_repo = ServiceStatusRepository(thread_db)
                thread_status_repo.update_heartbeat(user_id)
                thread_db.commit()
            except Exception:
                thread_db.rollback()

            while service.running and not getattr(service, "shutdown_requested", False):
                try:
                    now = datetime.now()
                    current_time = now.time()

                    # Check only once per minute
                    current_minute = now.strftime("%Y-%m-%d %H:%M")
                    if current_minute == last_check:
                        # Check service.running flag more frequently during sleep
                        # This allows faster shutdown when stop_service() is called
                        for _ in range(10):  # Check 10 times in 1 second
                            if not service.running or getattr(service, "shutdown_requested", False):
                                break
                            time.sleep(0.1)  # 100ms per check
                        continue

                    last_check = current_minute

                    # Only run on trading days (Monday-Friday)
                    if now.weekday() >= 5:  # Weekend  # noqa: PLR2004
                        # Check service.running flag more frequently during long sleep
                        # This allows faster shutdown when stop_service() is called
                        for _ in range(60):  # Check 60 times in 60 seconds
                            if not service.running or getattr(service, "shutdown_requested", False):
                                break
                            time.sleep(1)  # 1 second per check
                        continue

                    # Task scheduling (uses database schedule configuration)
                    # Pre-market retry
                    premarket_schedule = thread_schedule_manager.get_schedule("premarket_retry")
                    if premarket_schedule and premarket_schedule.enabled:
                        premarket_time = premarket_schedule.schedule_time
                        if (
                            dt_time(premarket_time.hour, premarket_time.minute)
                            <= current_time
                            < dt_time(premarket_time.hour, premarket_time.minute + 1)
                        ):
                            if not service.tasks_completed.get("premarket_retry"):
                                try:
                                    service.run_premarket_retry()
                                except Exception as e:
                                    user_logger.error(
                                        f"Pre-market retry failed: {e}",
                                        exc_info=True,
                                        action="scheduler",
                                    )

                    # 9:05 AM - Pre-market AMO adjustment
                    if dt_time(9, 5) <= current_time < dt_time(9, 6):
                        if not service.tasks_completed.get("premarket_amo_adjustment"):
                            try:
                                service.adjust_amo_quantities_premarket()
                                service.tasks_completed["premarket_amo_adjustment"] = True
                            except Exception as e:
                                user_logger.error(
                                    f"Pre-market AMO adjustment failed: {e}",
                                    exc_info=True,
                                    action="scheduler",
                                )

                    # 9:15 AM - Execute AMO orders at market open
                    if dt_time(9, 15) <= current_time < dt_time(9, 16):
                        if not service.tasks_completed.get("amo_orders_executed"):
                            try:
                                service.execute_amo_orders_at_market_open()
                                service.tasks_completed["amo_orders_executed"] = True
                            except Exception as e:
                                user_logger.error(
                                    f"AMO order execution failed: {e}",
                                    exc_info=True,
                                    action="scheduler",
                                )

                    # Sell monitoring (continuous during market hours, uses DB schedule)
                    sell_schedule = thread_schedule_manager.get_schedule("sell_monitor")
                    if sell_schedule and sell_schedule.enabled and sell_schedule.is_continuous:
                        start_time = sell_schedule.schedule_time
                        end_time = sell_schedule.end_time or dt_time(15, 30)
                        if current_time >= dt_time(
                            start_time.hour, start_time.minute
                        ) and current_time <= dt_time(end_time.hour, end_time.minute):
                            # Check if sell_monitor is already running before calling
                            if _is_sell_monitor_running(thread_db, user_id):
                                user_logger.debug(
                                    "Skipping sell_monitor - previous execution still running",
                                    action="scheduler",
                                )
                            else:
                                try:
                                    service.run_sell_monitor()
                                except Exception as e:
                                    user_logger.error(
                                        f"Sell monitoring failed: {e}",
                                        exc_info=True,
                                        action="scheduler",
                                    )

                    # 4:00 PM - Analysis (check custom schedule from DB and trigger via
                    # Individual Service Manager)
                    analysis_schedule = thread_schedule_manager.get_schedule("analysis")
                    if analysis_schedule and analysis_schedule.enabled:
                        analysis_time = analysis_schedule.schedule_time
                        analysis_hour = analysis_time.hour
                        analysis_minute = analysis_time.minute
                        if (
                            dt_time(analysis_hour, analysis_minute)
                            <= current_time
                            < dt_time(analysis_hour, analysis_minute + 1)
                        ):
                            if not service.tasks_completed.get("analysis"):
                                try:
                                    from src.application.services.individual_service_manager import (  # noqa: PLC0415, E501
                                        IndividualServiceManager,
                                    )
                                    from src.infrastructure.db.session import (  # noqa: PLC0415
                                        SessionLocal,
                                    )

                                    user_logger.info(
                                        f"Starting analysis task (scheduled at {analysis_time})",
                                        action="scheduler",
                                    )

                                    # Create fresh DB session for analysis (avoid session conflict)
                                    analysis_db = SessionLocal()
                                    try:
                                        # Trigger analysis via Individual Service Manager with fresh session  # noqa: E501
                                        service_manager = IndividualServiceManager(analysis_db)
                                        success, message, _ = service_manager.run_once(
                                            user_id, "analysis", execution_type="scheduled"
                                        )

                                        if success:
                                            service.tasks_completed["analysis"] = True
                                            user_logger.info(
                                                f"Analysis task triggered: {message}",
                                                action="scheduler",
                                            )
                                        else:
                                            user_logger.warning(
                                                f"Failed to trigger analysis: {message}",
                                                action="scheduler",
                                            )
                                    finally:
                                        # Ensure any pending transactions are handled before closing
                                        try:
                                            # Rollback any pending transaction
                                            analysis_db.rollback()
                                        except Exception:  # noqa: S110
                                            pass  # Ignore rollback errors (session may already be closed/rolled back)  # noqa: E501
                                        try:
                                            analysis_db.close()
                                        except Exception:  # noqa: S110
                                            pass  # Ignore close errors if session is in bad state
                                except Exception as e:
                                    user_logger.error(
                                        f"Analysis failed: {e}", exc_info=True, action="scheduler"
                                    )

                    # Buy orders (uses DB schedule)
                    buy_schedule = thread_schedule_manager.get_schedule("buy_orders")
                    if buy_schedule and buy_schedule.enabled:
                        buy_time = buy_schedule.schedule_time
                        if (
                            dt_time(buy_time.hour, buy_time.minute)
                            <= current_time
                            < dt_time(buy_time.hour, buy_time.minute + 1)
                        ):
                            if not service.tasks_completed.get("buy_orders"):
                                try:
                                    service.run_buy_orders()
                                except Exception as e:
                                    user_logger.error(
                                        f"Buy orders failed: {e}",
                                        exc_info=True,
                                        action="scheduler",
                                    )

                    # EOD cleanup (uses DB schedule)
                    eod_schedule = thread_schedule_manager.get_schedule("eod_cleanup")
                    if eod_schedule and eod_schedule.enabled:
                        eod_time = eod_schedule.schedule_time
                        if (
                            dt_time(eod_time.hour, eod_time.minute)
                            <= current_time
                            < dt_time(eod_time.hour, eod_time.minute + 1)
                        ):
                            if not service.tasks_completed.get("eod_cleanup"):
                                try:
                                    service.run_eod_cleanup()
                                except Exception as e:
                                    user_logger.error(
                                        f"EOD cleanup failed: {e}",
                                        exc_info=True,
                                        action="scheduler",
                                    )

                    # Update heartbeat every minute using thread-local session
                    # Use retry logic for reliability (handles database lock contention)
                    heartbeat_update_successful = False
                    max_heartbeat_retries = 3
                    heartbeat_retry_delays = [0.1, 0.2, 0.4]

                    from sqlalchemy.exc import OperationalError  # noqa: PLC0415

                    for retry_attempt in range(max_heartbeat_retries):
                        try:
                            # Create a fresh repository instance to ensure clean state
                            thread_status_repo = ServiceStatusRepository(thread_db)
                            thread_status_repo.update_heartbeat(user_id)
                            thread_db.commit()
                            heartbeat_update_successful = True
                            break
                        except OperationalError as op_err:
                            thread_db.rollback()
                            # Expire all objects to ensure fresh state
                            thread_db.expire_all()
                            is_locked_error = "database is locked" in str(op_err).lower()

                            if retry_attempt < max_heartbeat_retries - 1 and is_locked_error:
                                # Retry on locked errors with exponential backoff
                                time.sleep(heartbeat_retry_delays[retry_attempt])
                                continue
                            else:
                                # Final failure - log error
                                if not is_locked_error:
                                    try:
                                        user_logger.warning(
                                            f"Failed to update heartbeat after {retry_attempt + 1} attempts: {op_err}",
                                            action="scheduler",
                                        )
                                    except Exception:
                                        # Logger might also fail - use Python logger as fallback
                                        import logging  # noqa: PLC0415

                                        logging.warning(
                                            f"Failed to update heartbeat for user {user_id}: {op_err}"
                                        )
                                break
                        except Exception as e:
                            thread_db.rollback()
                            thread_db.expire_all()
                            # Non-OperationalError - don't retry
                            try:
                                user_logger.warning(
                                    f"Failed to update heartbeat (non-retryable error): {e}",
                                    action="scheduler",
                                )
                            except Exception:
                                import logging  # noqa: PLC0415

                                logging.warning(f"Failed to update heartbeat for user {user_id}: {e}")
                            break

                    if heartbeat_update_successful:
                        # Log heartbeat every 5 minutes
                        heartbeat_counter += 1
                        if (
                            heartbeat_counter == 1 or heartbeat_counter % 300 == 0
                        ):  # First update, then every 5 minutes
                            try:
                                user_logger.info(
                                    f"💓 Scheduler heartbeat "  # noqa: E501
                                    f"(running for {heartbeat_counter // 60} minutes)",
                                    action="scheduler",
                                )
                            except Exception:
                                # Logger might fail - continue without logging
                                pass

                        # Log pool status every 15 minutes
                        pool_log_counter += 1
                        if pool_log_counter % 900 == 0:  # Every 15 minutes
                            try:
                                log_pool_status(engine, user_logger)
                            except Exception:
                                pass  # Pool logging failure shouldn't break heartbeat

                    time.sleep(1)

                except Exception as e:
                    user_logger.error(f"Scheduler error: {e}", exc_info=True, action="scheduler")
                    thread_db.rollback()
                    time.sleep(60)

            service.running = False
            user_logger.info("Paper trading scheduler stopped", action="scheduler")
        finally:
            # Update database status to False when thread exits (CRITICAL - must succeed)
            # This ensures database reflects actual service state even if thread
            # crashes/exits unexpectedly
            # Use aggressive retry logic with emergency session fallback for reliability
            max_exit_retries = 5
            exit_retry_delays = [0.2, 0.5, 1.0, 2.0, 5.0]
            exit_status_updated = False

            from sqlalchemy.exc import OperationalError  # noqa: PLC0415

            # Try with existing thread_db first (up to 5 retries)
            for retry_attempt in range(max_exit_retries):
                try:
                    thread_status_repo = ServiceStatusRepository(thread_db)
                    thread_status_repo.update_running(user_id, running=False)
                    thread_status_repo.update_heartbeat(user_id)
                    thread_db.commit()
                    exit_status_updated = True
                    try:
                        user_logger.debug(
                            "Updated database service status to stopped on thread exit",
                            action="scheduler",
                        )
                    except Exception:
                        pass  # Logger might fail, but status is updated
                    break
                except OperationalError as op_err:
                    thread_db.rollback()
                    thread_db.expire_all()
                    is_locked_error = "database is locked" in str(op_err).lower()

                    if retry_attempt < max_exit_retries - 1:
                        # Retry with increasing delays
                        time.sleep(exit_retry_delays[retry_attempt])
                        continue
                    else:
                        # Final failure with thread_db - will try emergency session below
                        pass
                except Exception as e:
                    thread_db.rollback()
                    thread_db.expire_all()
                    # Non-OperationalError - try emergency session immediately
                    break

            # If exit status update failed, try with a fresh session (emergency fallback)
            if not exit_status_updated:
                try:
                    from src.infrastructure.db.session import SessionLocal  # noqa: PLC0415

                    emergency_db = SessionLocal()
                    try:
                        emergency_repo = ServiceStatusRepository(emergency_db)
                        emergency_repo.update_running(user_id, running=False)
                        emergency_repo.update_heartbeat(user_id)
                        emergency_db.commit()
                        exit_status_updated = True
                        try:
                            user_logger.info(
                                "Successfully updated service status using emergency session",
                                action="scheduler",
                            )
                        except Exception:
                            import logging  # noqa: PLC0415

                            logging.info(
                                f"Updated service status for user {user_id} via emergency session"
                            )
                    except Exception as e2:
                        emergency_db.rollback()
                        try:
                            user_logger.error(
                                f"CRITICAL: Emergency service status update failed: {e2}",
                                action="scheduler",
                            )
                        except Exception:
                            import logging  # noqa: PLC0415

                            logging.error(
                                f"CRITICAL: Emergency service status update failed for user {user_id}: {e2}"
                            )
                    finally:
                        try:
                            emergency_db.close()
                        except Exception:  # noqa: S110
                            pass  # Ignore close errors
                except Exception as e3:
                    try:
                        user_logger.error(
                            f"CRITICAL: Could not create emergency session: {e3}",
                            action="scheduler",
                        )
                    except Exception:
                        import logging  # noqa: PLC0415

                        logging.error(
                            f"CRITICAL: Could not create emergency session for user {user_id}: {e3}"
                        )

            # If still not updated, log critical error (but don't fail - cleanup must continue)
            if not exit_status_updated:
                try:
                    user_logger.error(
                        "CRITICAL: Service status could not be updated on exit. "
                        "Database may show stale 'running' status!",
                        action="scheduler",
                    )
                except Exception:
                    import logging  # noqa: PLC0415

                    logging.error(
                        f"CRITICAL: Service status could not be updated on exit for user {user_id}"
                    )

            # Release lock BEFORE closing connection (CRITICAL for PostgreSQL advisory locks)
            # Release table-based lock (works with any connection, no invalidation needed)
            _release_paper_scheduler_lock(thread_db, lock_id)
            # Clear lock_id from shared state after release
            self._lock_keys.pop(user_id, None)

            # Clean up thread-local session
            # Ensure any pending transactions are handled before closing
            try:
                # Rollback any pending transaction
                thread_db.rollback()
            except Exception:  # noqa: S110
                pass  # Ignore rollback errors (session may already be closed/rolled back)
            try:
                thread_db.close()
            except Exception:  # noqa: S110
                pass  # Ignore close errors if session is in bad state

    def start_service(self, user_id: int) -> bool:  # noqa: PLR0915, PLR0912
        """
        Start trading service for a user.

        Args:
            user_id: User ID to start service for

        Returns:
            True if service started successfully, False otherwise
        """
        # Get or create lock for this user (thread-safe using setdefault)
        lock = self._locks.setdefault(user_id, threading.Lock())

        with lock:
            # Check if service already running
            if user_id in self._services:
                # Service already exists - check if it's actually running
                service = self._services[user_id]
                service_thread = self._service_threads.get(user_id)

                if hasattr(service, "running") and service.running:
                    # Verify thread is actually alive (not just running flag)
                    # Give thread a grace period - is_alive() might be False briefly during startup
                    thread_is_alive = False
                    if service_thread:
                        thread_is_alive = service_thread.is_alive()
                        # If thread appears dead, wait a bit - it might be starting
                        if not thread_is_alive:
                            time.sleep(0.5)
                            thread_is_alive = service_thread.is_alive()

                    # If thread is alive, service is running - return early
                    if thread_is_alive:
                        self._logger.info(
                            f"Service already running for user {user_id}; "  # noqa: E501
                            f"not starting another instance",
                            action="start_service",
                        )
                        return True  # Already running

                    # Thread appears dead - clean up stale service
                    # With table-based locks, we don't need to check lock status
                    # The cleanup function will handle stale locks
                    self._logger.warning(
                        f"Service for user {user_id} has running=True but thread is dead. "
                        "Cleaning up stale service instance.",
                        action="start_service",
                    )
                    self._services.pop(user_id, None)
                    self._service_threads.pop(user_id, None)

                    # Clean up stale advisory lock held by dead thread's connection
                    # This prevents the new thread from failing to acquire the lock
                    self._logger.info(
                        f"Detected dead thread for user {user_id}. "
                        "Attempting to clean up stale scheduler lock...",
                        action="start_service",
                    )
                    cleanup_result = _cleanup_stale_paper_scheduler_lock(
                        self.db, user_id, self._logger
                    )
                    if cleanup_result:
                        self._logger.info(
                            f"Successfully cleaned up stale lock for user {user_id}. "
                            "Waiting 2 seconds before starting new thread to ensure lock is released...",
                            action="start_service",
                        )
                        time.sleep(2)  # Give the database time to release the lock
                    else:
                        # Cleanup failed - this shouldn't happen with table-based locks
                        # but log it anyway
                        self._logger.warning(
                            f"Could not clean up stale lock for user {user_id} after cleanup attempts. "
                            "This is unexpected with table-based locks. Proceeding anyway...",
                            action="start_service",
                        )

                    # Continue to start new service below (cleanup should have succeeded)

            try:
                # Get user-specific logger
                user_logger = get_user_logger(user_id=user_id, db=self.db, module="TradingService")
                user_logger.info(
                    "Starting trading service",
                    action="start_service",
                    task_name=self._task_name,
                )

                # Load user settings
                settings = self._settings_repo.get_by_user_id(user_id)
                if not settings:
                    user_logger.error(
                        "User settings not found",
                        action="start_service",
                        task_name=self._task_name,
                    )
                    raise ValueError(f"User settings not found for user_id={user_id}")

                # Phase 2.4: Handle broker vs paper mode
                temp_env_file = None
                broker_creds = None

                if settings.trade_mode.value == "broker":
                    # Broker mode: requires encrypted credentials
                    if not settings.broker_creds_encrypted:
                        user_logger.error(
                            "No broker credentials stored",
                            action="start_service",
                            task_name=self._task_name,
                        )
                        raise ValueError(f"No broker credentials stored for user_id={user_id}")

                    broker_creds_dict = decrypt_broker_credentials(settings.broker_creds_encrypted)
                    if not broker_creds_dict:
                        user_logger.error(
                            "Failed to decrypt broker credentials",
                            action="start_service",
                            task_name=self._task_name,
                        )
                        raise ValueError(
                            f"Failed to decrypt broker credentials for user_id={user_id}"
                        )

                    # Create temporary env file for KotakNeoAuth (maintains backward compatibility)
                    temp_env_file = create_temp_env_file(broker_creds_dict)
                    self._temp_env_files[user_id] = temp_env_file  # Track for cleanup
                    broker_creds = broker_creds_dict  # Pass dict for future use

                    user_logger.info(
                        "Broker mode: credentials loaded and decrypted",
                        action="start_service",
                        task_name=self._task_name,
                    )
                elif settings.trade_mode.value == "paper":
                    # Paper mode: uses simulated trading, no broker credentials needed
                    user_logger.info(
                        "Paper mode: using simulated trading (no broker credentials required)",
                        action="start_service",
                        task_name=self._task_name,
                    )
                    # Paper mode will use MockBrokerAdapter or similar
                else:
                    user_logger.error(
                        f"Unknown trade mode: {settings.trade_mode.value}",
                        action="start_service",
                        task_name=self._task_name,
                    )
                    raise ValueError(
                        f"Unknown trade mode: {settings.trade_mode.value} for user_id={user_id}"
                    )

                # Load user trading configuration and convert to StrategyConfig
                user_config = self._config_repo.get_or_create_default(user_id)
                strategy_config = user_config_to_strategy_config(user_config, db_session=self.db)

                # Create appropriate service based on mode
                if settings.trade_mode.value == "paper":
                    # Paper trading mode - use PaperTradingServiceAdapter
                    service = PaperTradingServiceAdapter(
                        user_id=user_id,
                        db_session=self.db,
                        strategy_config=strategy_config,
                        initial_capital=user_config.paper_trading_initial_capital,
                        storage_path=None,  # Will default to user_3
                        skip_execution_tracking=False,
                    )

                    # Initialize paper trading service
                    if not service.initialize():
                        user_logger.error(
                            "Failed to initialize paper trading service",
                            action="start_service",
                            task_name=self._task_name,
                        )
                        raise RuntimeError("Paper trading service initialization failed")

                    # Store service instance
                    self._services[user_id] = service

                    # Start scheduler in background thread
                    service_thread = threading.Thread(
                        target=self._run_paper_trading_scheduler,
                        args=(service, user_id),
                        daemon=True,
                        name=f"PaperTradingScheduler-{user_id}",
                    )
                    # CRITICAL: Store thread reference BEFORE starting to prevent race condition
                    # If get_service_status() is called immediately, it will find the thread reference
                    self._service_threads[user_id] = service_thread
                    service_thread.start()

                    user_logger.info(
                        "Paper trading service started with scheduler",
                        action="start_service",
                        task_name=self._task_name,
                    )
                else:
                    # Broker mode - use real TradingService
                    service = trading_service_module.TradingService(
                        user_id=user_id,
                        db_session=self.db,
                        broker_creds=broker_creds,
                        strategy_config=strategy_config,
                        env_file=temp_env_file,
                    )

                    # Store service instance
                    self._services[user_id] = service

                    # Start real trading service in background thread
                    service_thread = threading.Thread(
                        target=service.run, daemon=True, name=f"TradingService-{user_id}"
                    )
                    # CRITICAL: Store thread reference BEFORE starting to prevent race condition
                    # If get_service_status() is called immediately, it will find the thread reference
                    self._service_threads[user_id] = service_thread
                    service_thread.start()

                    user_logger.info(
                        "Broker trading service started with scheduler",
                        action="start_service",
                        task_name=self._task_name,
                    )

                # Update service status
                self._service_status_repo.update_running(user_id, running=True)
                self._service_status_repo.update_heartbeat(user_id)

                # Commit status update BEFORE sending notification
                # This ensures status is persisted even if notification fails/rollbacks
                self.db.commit()

                # Send notification for service start
                # Note: This is wrapped in try-except internally, so failures won't affect status
                self._notify_service_started(user_id)

                return True

            except Exception as e:
                # Log error and update status
                user_logger = get_user_logger(user_id=user_id, db=self.db, module="TradingService")
                user_logger.error(
                    "Failed to start trading service",
                    exc_info=e,
                    action="start_service",
                    task_name=self._task_name,
                )

                self._service_status_repo.update_running(user_id, running=False)
                self._service_status_repo.increment_error(user_id, error_message=str(e))
                # Commit error status before raising to ensure it's persisted
                self.db.commit()
                raise

    def stop_service(self, user_id: int) -> bool:
        """
        Stop trading service for a user.

        Args:
            user_id: User ID to stop service for

        Returns:
            True if service stopped successfully, False otherwise
        """
        # Get or create lock for this user (thread-safe using setdefault)
        lock = self._locks.setdefault(user_id, threading.Lock())

        with lock:
            service = self._services.pop(user_id, None)
            service_thread = self._service_threads.pop(user_id, None)

            try:
                # Get user-specific logger
                user_logger = get_user_logger(user_id=user_id, db=self.db, module="TradingService")
                user_logger.info(
                    "Stopping trading service",
                    action="stop_service",
                    task_name=self._task_name,
                )

                # Request shutdown first to allow thread to exit gracefully
                if service:
                    if hasattr(service, "shutdown_requested"):
                        service.shutdown_requested = True
                    if hasattr(service, "running"):
                        service.running = False

                # Wait for service thread to stop (with timeout)
                # The thread's finally block will release the advisory lock
                if service_thread and service_thread.is_alive():
                    user_logger.info(
                        "Waiting for scheduler thread to stop (it will release advisory lock)...",
                        action="stop_service",
                    )
                    service_thread.join(timeout=10.0)
                    if service_thread.is_alive():
                        user_logger.warning(
                            "Scheduler thread did not stop within timeout. "
                            "Advisory lock may remain held until thread exits or connection recycles.",
                            action="stop_service",
                        )
                    else:
                        # Thread stopped successfully - clear lock_id if still present
                        self._lock_keys.pop(user_id, None)

                # Clean up temporary env file (Phase 2.4)
                if user_id in self._temp_env_files:
                    temp_file = self._temp_env_files[user_id]
                    try:
                        if os.path.exists(temp_file):
                            os.unlink(temp_file)
                    except Exception as cleanup_error:
                        user_logger.warning(
                            f"Failed to cleanup temp env file: {cleanup_error}",
                            action="stop_service",
                            task_name=self._task_name,
                        )
                    del self._temp_env_files[user_id]

                # Update service status
                self._service_status_repo.update_running(user_id, running=False)
                self._service_status_repo.update_heartbeat(user_id)

                # Commit status update BEFORE sending notification
                # This ensures status is persisted even if notification fails/rollbacks
                self.db.commit()

                # Send notification for service stop
                # Note: This is wrapped in try-except internally, so failures won't affect status
                self._notify_service_stopped(user_id)

                user_logger.info(
                    "Trading service stopped successfully",
                    action="stop_service",
                    task_name=self._task_name,
                )
                return True

            except Exception as e:
                # Log error
                user_logger = get_user_logger(user_id=user_id, db=self.db, module="TradingService")
                user_logger.error(
                    "Failed to stop trading service",
                    exc_info=e,
                    action="stop_service",
                    task_name=self._task_name,
                )

                self._service_status_repo.increment_error(user_id, error_message=str(e))
                # Commit error status to ensure it's persisted
                self.db.commit()
                return False

    def get_service_status(self, user_id: int) -> any | None:
        """
        Get current service status for a user.

        Automatically detects and cleans up stale services (database shows running=True
        but thread is dead or heartbeat is stale).

        Args:
            user_id: User ID to get status for

        Returns:
            ServiceStatus object or None if not found
        """
        # CRITICAL: Expire all cached objects to ensure we read fresh heartbeat data
        # This prevents reading stale heartbeat from previous runs when service just restarted
        self.db.expire_all()
        status = self._service_status_repo.get(user_id)
        if not status:
            return None

        # Check if service is actually running (thread alive check)
        # CRITICAL: Don't rely on lock checking from different connections - it's unreliable
        # Instead, rely on the thread object itself and give it proper grace periods
        service_thread = self._service_threads.get(user_id)
        thread_is_alive = False

        if service_thread:
            # Give thread multiple grace periods - is_alive() can be unreliable during startup
            for attempt in range(3):  # Check up to 3 times with delays
                thread_is_alive = service_thread.is_alive()
                if thread_is_alive:
                    break
                if attempt < 2:  # Wait before next attempt (except last one)
                    time.sleep(0.3)  # Wait 300ms between checks

        # If database says running=True but thread appears dead, be very conservative
        # Only mark as stale if thread is definitely not in _service_threads AND
        # heartbeat is old enough to indicate it's truly stale (not just starting)
        if status.service_running and not thread_is_alive:
            # If thread is not in _service_threads at all, wait longer and check heartbeat
            if service_thread is None:
                # Thread reference doesn't exist - but wait a bit in case it's being added
                # This is a race condition: thread.start() is called but reference might not be stored yet
                time.sleep(1.0)  # Wait longer - thread reference should be stored within 1 second
                service_thread = self._service_threads.get(user_id)
                if service_thread and service_thread.is_alive():
                    # Thread was just added and is alive - don't mark as stale
                    thread_is_alive = True
                else:
                    # Thread reference still doesn't exist - check heartbeat before marking stale
                    # If heartbeat is recent (< 2 minutes), service might be starting - don't mark as stale
                    if status.last_heartbeat:
                        from datetime import timedelta
                        from src.infrastructure.db.timezone_utils import ist_now

                        now = ist_now()
                        last_heartbeat = status.last_heartbeat
                        if last_heartbeat.tzinfo is None:
                            last_heartbeat = last_heartbeat.replace(tzinfo=now.tzinfo)
                        heartbeat_age = now - last_heartbeat

                        # Only mark as stale if heartbeat is old (> 2 minutes)
                        # This prevents false positives when service just started
                        if heartbeat_age > timedelta(minutes=2):
                            self._logger.warning(
                                f"Detected stale service for user {user_id}: "
                                "database shows running=True but thread reference not found "
                                f"and heartbeat is old ({heartbeat_age.total_seconds():.0f}s). Cleaning up.",
                                action="get_service_status",
                            )
                            # Clean up stale service
                            self._services.pop(user_id, None)
                            self._service_threads.pop(user_id, None)
                            # Update database status
                            self._service_status_repo.update_running(user_id, running=False)
                            self.db.commit()
                            # Refresh status from database
                            status = self._service_status_repo.get(user_id)
                        else:
                            # Heartbeat is recent - service might be starting, don't mark as stale
                            self._logger.debug(
                                f"Service for user {user_id} has no thread reference but heartbeat is recent "
                                f"({heartbeat_age.total_seconds():.0f}s). Not marking as stale - may be starting.",
                                action="get_service_status",
                            )
                    else:
                        # No heartbeat yet - service might be starting, don't mark as stale
                        self._logger.debug(
                            f"Service for user {user_id} has no thread reference and no heartbeat yet. "
                            "Not marking as stale - may be starting.",
                            action="get_service_status",
                        )
            else:
                # Thread reference exists but is_alive() returned False
                # This could be a false negative - be very conservative
                # Only mark as stale if we've checked multiple times and it's consistently dead
                # AND the heartbeat is very old (indicating it's been dead for a while)
                if status.last_heartbeat:
                    from datetime import timedelta
                    from src.infrastructure.db.timezone_utils import ist_now

                    now = ist_now()
                    last_heartbeat = status.last_heartbeat
                    if last_heartbeat.tzinfo is None:
                        last_heartbeat = last_heartbeat.replace(tzinfo=now.tzinfo)
                    heartbeat_age = now - last_heartbeat

                    # Only mark as stale if heartbeat is VERY old (>30 minutes) AND thread is dead
                    # This prevents false positives when service just started
                    if heartbeat_age > timedelta(minutes=30):
                        self._logger.warning(
                            f"Detected stale service for user {user_id}: "
                            f"database shows running=True, thread is dead, "
                            f"and heartbeat is very old ({heartbeat_age.total_seconds():.0f}s). Cleaning up.",
                            action="get_service_status",
                        )
                        # Clean up stale service
                        self._services.pop(user_id, None)
                        self._service_threads.pop(user_id, None)
                        # Update database status
                        self._service_status_repo.update_running(user_id, running=False)
                        self.db.commit()
                        # Refresh status from database
                        status = self._service_status_repo.get(user_id)
                    else:
                        # Heartbeat is recent - thread might just be starting, don't mark as stale
                        self._logger.debug(
                            f"Service for user {user_id} shows dead thread but heartbeat is recent "
                            f"({heartbeat_age.total_seconds():.0f}s). Not marking as stale - may be starting.",
                            action="get_service_status",
                        )
                else:
                    # No heartbeat yet - service might just be starting, don't mark as stale
                    self._logger.debug(
                        f"Service for user {user_id} shows dead thread but no heartbeat yet. "
                        "Not marking as stale - may be starting.",
                        action="get_service_status",
                    )

        # Also check heartbeat age - if heartbeat is very old (>30 minutes), consider stale
        # But only if thread is also consistently dead (already checked above)
        # This is a separate check for cases where thread reference doesn't exist
        if status.service_running and status.last_heartbeat and not thread_is_alive:
            from datetime import timedelta
            from src.infrastructure.db.timezone_utils import ist_now

            now = ist_now()
            # Ensure last_heartbeat is timezone-aware for comparison
            last_heartbeat = status.last_heartbeat
            if last_heartbeat.tzinfo is None:
                last_heartbeat = last_heartbeat.replace(tzinfo=now.tzinfo)
            heartbeat_age = now - last_heartbeat

            # If heartbeat is older than 30 minutes and thread is not alive, mark as stale
            # Use 30 minutes to avoid false positives when service just restarted
            # Don't check lock - rely on thread object and heartbeat age only
            if heartbeat_age > timedelta(minutes=30):
                self._logger.warning(
                    f"Detected stale service for user {user_id}: "
                    f"heartbeat age {heartbeat_age.total_seconds():.0f}s, thread not alive. Cleaning up.",
                    action="get_service_status",
                )
                # Clean up stale service
                self._services.pop(user_id, None)
                self._service_threads.pop(user_id, None)
                # Update database status
                self._service_status_repo.update_running(user_id, running=False)
                self.db.commit()
                # Refresh status from database
                status = self._service_status_repo.get(user_id)

        return status

    def is_service_running(self, user_id: int) -> bool:
        """
        Check if service is running for a user.

        Args:
            user_id: User ID to check

        Returns:
            True if service is running, False otherwise
        """
        if user_id not in self._services:
            return False

        service = self._services[user_id]
        return hasattr(service, "running") and service.running

    def get_position_creation_metrics(self, user_id: int) -> dict[str, int] | None:
        """
        Get position creation metrics for a user's trading service.

        Issue #1 Fix: Returns metrics tracking position creation success/failure rates.

        Args:
            user_id: User ID to get metrics for

        Returns:
            Dict with metrics: success, failed_missing_repos,
            failed_missing_symbol, failed_exception
            Returns None if service is not running or unified_order_monitor
            is not available
        """
        if user_id not in self._services:
            return None

        service = self._services[user_id]

        # Check if service has unified_order_monitor (broker mode)
        if hasattr(service, "unified_order_monitor") and service.unified_order_monitor:
            try:
                return service.unified_order_monitor.get_position_creation_metrics()
            except Exception as e:
                self._logger.warning(
                    f"Failed to get position creation metrics for user {user_id}: {e}",
                    action="get_position_creation_metrics",
                )
                return None

        # Paper trading mode doesn't have unified_order_monitor
        return None

    def get_positions_without_sell_orders(
        self, user_id: int, skip_ema9_check: bool = True
    ) -> list[dict[str, Any]]:
        """
        Issue #5: Get positions without sell orders for a user.

        Returns detailed list of positions that don't have sell orders,
        including reasons why orders weren't placed.

        Args:
            user_id: User ID
            skip_ema9_check: If True (default), skips expensive EMA9 calculation
                for faster response. Set to False for detailed analysis (slower,
                ~1-2s per position).

        Returns:
            List of dicts with position details and reasons
        """
        if user_id not in self._services:
            return []

        service = self._services[user_id]

        # Check if service has unified_order_monitor (broker mode)
        if hasattr(service, "unified_order_monitor") and service.unified_order_monitor:
            try:
                sell_manager = service.unified_order_monitor.sell_manager
                if sell_manager:
                    return sell_manager.get_positions_without_sell_orders(
                        use_broker_api=False, skip_ema9_check=skip_ema9_check
                    )
            except Exception as e:
                self._logger.warning(
                    f"Failed to get positions without sell orders for user {user_id}: {e}",
                    action="get_positions_without_sell_orders",
                )
                return []

        # Paper trading mode or service not available
        return []

    def list_active_services(self) -> list[int]:
        """
        Get list of user IDs with active services.

        Returns:
            List of user IDs with running services
        """
        return [
            user_id
            for user_id, service in self._services.items()
            if hasattr(service, "running") and service.running
        ]

    def _get_telegram_notifier(self, user_id: int):
        """Get Telegram notifier instance with database session and user-specific chat ID"""
        try:
            # Check if telegram notifier module is available
            try:
                from modules.kotak_neo_auto_trader.telegram_notifier import (  # noqa: PLC0415
                    TelegramNotifier,
                )
            except ImportError:
                return None

            # Get user's notification preferences to get Telegram chat ID and bot token
            pref_service = NotificationPreferenceService(self.db)
            preferences = pref_service.get_preferences(user_id)

            # Check if Telegram is enabled for this user
            if not preferences or not preferences.telegram_enabled:
                return None

            # Get bot token from user preferences first, then fall back to environment
            bot_token = preferences.telegram_bot_token if preferences else None
            if not bot_token:
                bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

            chat_id = preferences.telegram_chat_id if preferences else None

            # Only create notifier if both bot token and chat ID are available
            if not bot_token:
                return None
            if not chat_id:
                return None

            # Create a new TelegramNotifier instance (not singleton) for this user
            # This is necessary because each user has a different chat_id
            return TelegramNotifier(
                bot_token=bot_token,
                chat_id=chat_id,
                enabled=True,
                db_session=self.db,
            )
        except Exception as e:
            user_logger = get_user_logger(
                user_id=user_id, db=self.db, module="MultiUserTradingService"
            )
            user_logger.warning(f"Failed to get Telegram notifier: {e}")
            return None

    def _notify_service_started(self, user_id: int) -> None:
        """Send notification when unified service starts"""
        try:
            pref_service = NotificationPreferenceService(self.db)

            # Check if in-app notifications are enabled
            if pref_service.should_notify(
                user_id, NotificationEventType.SERVICE_STARTED, channel="in_app"
            ):
                message = (  # noqa: E501
                    "Unified Trading Service\nStatus: Running\n"
                    "All scheduled tasks will execute automatically."
                )
                notification = self._notification_repo.create(
                    user_id=user_id,
                    type="service",
                    level="info",
                    title="Unified Service Started",
                    message=message,
                )
                try:
                    user_logger = get_user_logger(
                        user_id=user_id, db=self.db, module="MultiUserTradingService"
                    )
                    user_logger.info(
                        "Created in-app notification for unified service start",
                        action="notify_service_started",
                        notification_id=notification.id,
                    )
                except Exception:
                    # Logging failure shouldn't prevent notification from being created
                    pass

            # Send Telegram notification if enabled
            if pref_service.should_notify(
                user_id, NotificationEventType.SERVICE_STARTED, channel="telegram"
            ):
                try:
                    notifier = self._get_telegram_notifier(user_id)
                    if notifier and notifier.enabled:
                        message_text = (
                            "🚀 *Unified Trading Service Started*\n\n"
                            "All scheduled tasks will execute automatically."
                        )
                        notifier.notify_system_alert(
                            alert_type="SERVICE_STARTED",
                            message_text=message_text,
                            severity="INFO",
                            user_id=user_id,
                        )
                except Exception as e:
                    user_logger = get_user_logger(
                        user_id=user_id, db=self.db, module="MultiUserTradingService"
                    )
                    user_logger.warning(f"Failed to send Telegram notification: {e}")

            # Send Email notification if enabled
            if pref_service.should_notify(
                user_id, NotificationEventType.SERVICE_STARTED, channel="email"
            ):
                try:
                    from services.email_notifier import EmailNotifier  # noqa: PLC0415

                    email_notifier = EmailNotifier()
                    if email_notifier.is_available():
                        preferences = pref_service.get_preferences(user_id)
                        if preferences and preferences.email_address:
                            email_notifier.send_service_notification(
                                email=preferences.email_address,
                                title="Unified Trading Service Started",
                                message=(  # noqa: E501
                                    "Unified Trading Service has started. "
                                    "All scheduled tasks will execute automatically."
                                ),
                                level="info",
                            )
                except Exception as e:
                    user_logger = get_user_logger(
                        user_id=user_id, db=self.db, module="MultiUserTradingService"
                    )
                    user_logger.warning(f"Failed to send email notification: {e}")

        except Exception as e:
            user_logger = get_user_logger(
                user_id=user_id, db=self.db, module="MultiUserTradingService"
            )
            user_logger.error(
                f"Failed to send service started notification: {e}",
                exc_info=e,
                action="notify_service_started",
            )

    def _notify_service_stopped(self, user_id: int) -> None:
        """Send notification when unified service stops"""
        try:
            pref_service = NotificationPreferenceService(self.db)

            # Check if in-app notifications are enabled
            if pref_service.should_notify(
                user_id, NotificationEventType.SERVICE_STOPPED, channel="in_app"
            ):
                message = (  # noqa: E501
                    "Unified Trading Service\nStatus: Stopped\n"
                    "All scheduled tasks have been halted."
                )
                notification = self._notification_repo.create(
                    user_id=user_id,
                    type="service",
                    level="info",
                    title="Unified Service Stopped",
                    message=message,
                )
                user_logger = get_user_logger(
                    user_id=user_id, db=self.db, module="MultiUserTradingService"
                )
                user_logger.info(
                    "Created in-app notification for unified service stop",
                    action="notify_service_stopped",
                    notification_id=notification.id,
                )

            # Send Telegram notification if enabled
            if pref_service.should_notify(
                user_id, NotificationEventType.SERVICE_STOPPED, channel="telegram"
            ):
                try:
                    notifier = self._get_telegram_notifier(user_id)
                    if notifier and notifier.enabled:
                        message_text = (
                            "🛑 *Unified Trading Service Stopped*\n\n"
                            "All scheduled tasks have been halted."
                        )
                        notifier.notify_system_alert(
                            alert_type="SERVICE_STOPPED",
                            message_text=message_text,
                            severity="INFO",
                            user_id=user_id,
                        )
                except Exception as e:
                    user_logger = get_user_logger(
                        user_id=user_id, db=self.db, module="MultiUserTradingService"
                    )
                    user_logger.warning(f"Failed to send Telegram notification: {e}")

            # Send Email notification if enabled
            if pref_service.should_notify(
                user_id, NotificationEventType.SERVICE_STOPPED, channel="email"
            ):
                try:
                    from services.email_notifier import EmailNotifier  # noqa: PLC0415

                    email_notifier = EmailNotifier()
                    if email_notifier.is_available():
                        preferences = pref_service.get_preferences(user_id)
                        if preferences and preferences.email_address:
                            email_notifier.send_service_notification(
                                email=preferences.email_address,
                                title="Unified Trading Service Stopped",
                                message=(  # noqa: E501
                                    "Unified Trading Service has been stopped. "
                                    "All scheduled tasks have been halted."
                                ),
                                level="info",
                            )
                except Exception as e:
                    user_logger = get_user_logger(
                        user_id=user_id, db=self.db, module="MultiUserTradingService"
                    )
                    user_logger.warning(f"Failed to send email notification: {e}")

        except Exception as e:
            user_logger = get_user_logger(
                user_id=user_id, db=self.db, module="MultiUserTradingService"
            )
            user_logger.error(
                f"Failed to send service stopped notification: {e}",
                exc_info=e,
                action="notify_service_stopped",
            )
