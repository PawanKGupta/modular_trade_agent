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

from sqlalchemy.orm import Session

import modules.kotak_neo_auto_trader.run_trading_service as trading_service_module
from src.application.services.broker_credentials import (
    create_temp_env_file,
    decrypt_broker_credentials,
)
from src.application.services.config_converter import user_config_to_strategy_config
from src.application.services.paper_trading_service_adapter import PaperTradingServiceAdapter
from src.infrastructure.logging import get_user_logger
from src.infrastructure.persistence.service_status_repository import ServiceStatusRepository
from src.infrastructure.persistence.settings_repository import SettingsRepository
from src.infrastructure.persistence.user_trading_config_repository import (
    UserTradingConfigRepository,
)


class MultiUserTradingService:
    """
    Manages trading services for multiple users.

    Each user gets their own isolated TradingService instance with:
    - User-specific broker credentials
    - User-specific trading configuration
    - User-specific data isolation
    - Independent service lifecycle
    """

    def __init__(self, db: Session):
        """
        Initialize multi-user trading service manager.

        Args:
            db: Database session
        """
        self.db = db
        self._services: dict[int, any] = {}  # user_id -> TradingService instance
        self._locks: dict[int, threading.Lock] = {}  # user_id -> service lock
        self._temp_env_files: dict[int, str] = {}  # user_id -> temp env file path (for cleanup)
        self._service_threads: dict[int, threading.Thread] = {}  # user_id -> scheduler thread
        self._service_status_repo = ServiceStatusRepository(db)
        self._settings_repo = SettingsRepository(db)
        self._config_repo = UserTradingConfigRepository(db)
        self._logger = get_user_logger(
            user_id=0, db=db, module="MultiUserTradingService"
        )  # System-level logger
        self._task_name = "unified_service"

    def _run_paper_trading_scheduler(self, service: PaperTradingServiceAdapter, user_id: int):
        """
        Run paper trading service scheduler in background thread.

        Args:
            service: PaperTradingServiceAdapter instance
            user_id: User ID for this service
        """
        user_logger = get_user_logger(user_id=user_id, db=self.db, module="PaperTradingScheduler")
        user_logger.info("Paper trading scheduler started", action="scheduler")

        service.running = True
        last_check = None

        while service.running and not getattr(service, "shutdown_requested", False):
            try:
                now = datetime.now()
                current_time = now.time()

                # Check only once per minute
                current_minute = now.strftime("%Y-%m-%d %H:%M")
                if current_minute == last_check:
                    time.sleep(1)
                    continue

                last_check = current_minute

                # Only run on trading days (Monday-Friday)
                if now.weekday() >= 5:  # Weekend
                    time.sleep(60)
                    continue

                # Task scheduling (matches real trading service)
                # 9:00 AM - Pre-market retry
                if dt_time(9, 0) <= current_time < dt_time(9, 1):
                    if not service.tasks_completed.get("premarket_retry"):
                        try:
                            service.run_premarket_retry()
                        except Exception as e:
                            user_logger.error(
                                f"Pre-market retry failed: {e}", exc_info=True, action="scheduler"
                            )

                # 9:15 AM onwards - Sell monitoring (continuous during market hours)
                if current_time >= dt_time(9, 15) and dt_time(9, 15) <= current_time <= dt_time(
                    15, 30
                ):
                    try:
                        service.run_sell_monitor()
                    except Exception as e:
                        user_logger.error(
                            f"Sell monitoring failed: {e}", exc_info=True, action="scheduler"
                        )

                # 9:30 AM, 10:30 AM, etc. - Position monitoring (hourly at :30)
                if current_time.minute == 30 and 9 <= now.hour <= 15:
                    hour_key = now.strftime("%Y-%m-%d %H")
                    if not service.tasks_completed.get("position_monitor", {}).get(hour_key):
                        try:
                            service.run_position_monitor()
                        except Exception as e:
                            user_logger.error(
                                f"Position monitoring failed: {e}",
                                exc_info=True,
                                action="scheduler",
                            )

                # 4:00 PM - Analysis (handled by individual service - skip)
                # 4:05 PM - Buy orders
                if dt_time(16, 5) <= current_time < dt_time(16, 6):
                    if not service.tasks_completed.get("buy_orders"):
                        try:
                            service.run_buy_orders()
                        except Exception as e:
                            user_logger.error(
                                f"Buy orders failed: {e}", exc_info=True, action="scheduler"
                            )

                # 6:00 PM - EOD cleanup
                if dt_time(18, 0) <= current_time < dt_time(18, 1):
                    if not service.tasks_completed.get("eod_cleanup"):
                        try:
                            service.run_eod_cleanup()
                        except Exception as e:
                            user_logger.error(
                                f"EOD cleanup failed: {e}", exc_info=True, action="scheduler"
                            )

                # Update heartbeat every minute
                try:
                    self._service_status_repo.update_heartbeat(user_id)
                    self.db.commit()
                except Exception as e:
                    user_logger.warning(f"Failed to update heartbeat: {e}", action="scheduler")

                time.sleep(1)

            except Exception as e:
                user_logger.error(f"Scheduler error: {e}", exc_info=True, action="scheduler")
                time.sleep(60)

        service.running = False
        user_logger.info("Paper trading scheduler stopped", action="scheduler")

    def start_service(self, user_id: int) -> bool:
        """
        Start trading service for a user.

        Args:
            user_id: User ID to start service for

        Returns:
            True if service started successfully, False otherwise
        """
        # Get or create lock for this user
        if user_id not in self._locks:
            self._locks[user_id] = threading.Lock()

        with self._locks[user_id]:
            # Check if service already running
            if user_id in self._services:
                # Service already exists - check if it's actually running
                service = self._services[user_id]
                if hasattr(service, "running") and service.running:
                    return True  # Already running

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
                strategy_config = user_config_to_strategy_config(user_config)

                # Create appropriate service based on mode
                if settings.trade_mode.value == "paper":
                    # Paper trading mode - use PaperTradingServiceAdapter
                    service = PaperTradingServiceAdapter(
                        user_id=user_id,
                        db_session=self.db,
                        strategy_config=strategy_config,
                        initial_capital=100000.0,  # Default capital, can be made configurable
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
                    service_thread.start()
                    self._service_threads[user_id] = service_thread

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
                    service_thread.start()
                    self._service_threads[user_id] = service_thread

                    user_logger.info(
                        "Broker trading service started with scheduler",
                        action="start_service",
                        task_name=self._task_name,
                    )

                # Update service status
                self._service_status_repo.update_running(user_id, running=True)
                self._service_status_repo.update_heartbeat(user_id)

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
                raise

    def stop_service(self, user_id: int) -> bool:
        """
        Stop trading service for a user.

        Args:
            user_id: User ID to stop service for

        Returns:
            True if service stopped successfully, False otherwise
        """
        if user_id not in self._locks:
            # Create lock to make stop idempotent even if service was never started
            self._locks[user_id] = threading.Lock()

        with self._locks[user_id]:
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

                # Request shutdown
                if service:
                    if hasattr(service, "shutdown_requested"):
                        service.shutdown_requested = True
                    if hasattr(service, "running"):
                        service.running = False

                # Wait for service thread to stop (with timeout)
                if service_thread and service_thread.is_alive():
                    user_logger.info(
                        "Waiting for scheduler thread to stop...", action="stop_service"
                    )
                    service_thread.join(timeout=10.0)
                    if service_thread.is_alive():
                        user_logger.warning(
                            "Scheduler thread did not stop within timeout",
                            action="stop_service",
                        )

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
                return False

    def get_service_status(self, user_id: int) -> any | None:
        """
        Get current service status for a user.

        Args:
            user_id: User ID to get status for

        Returns:
            ServiceStatus object or None if not found
        """
        return self._service_status_repo.get(user_id)

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
