"""
Multi-User Trading Service Wrapper

Manages trading service instances for multiple users, ensuring isolation
and proper lifecycle management.
"""

from __future__ import annotations

import threading

from sqlalchemy.orm import Session

from src.infrastructure.db.timezone_utils import ist_now
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
        self._service_status_repo = ServiceStatusRepository(db)
        self._settings_repo = SettingsRepository(db)
        self._config_repo = UserTradingConfigRepository(db)
        self._logger = get_user_logger(
            user_id=0, db=db, module="MultiUserTradingService"
        )  # System-level logger

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
                user_logger = get_user_logger(
                    user_id=user_id, db=self.db, module="TradingService"
                )
                user_logger.info("Starting trading service", action="start_service")

                # Load user settings
                settings = self._settings_repo.get_by_user_id(user_id)
                if not settings:
                    user_logger.error("User settings not found", action="start_service")
                    raise ValueError(f"User settings not found for user_id={user_id}")

                # Check trade mode
                if settings.trade_mode.value != "broker":
                    user_logger.warning(
                        "Service start failed - not in broker mode",
                        trade_mode=settings.trade_mode.value,
                        action="start_service",
                    )
                    raise ValueError(
                        f"User {user_id} is in {settings.trade_mode.value} mode, "
                        "broker mode required for trading service"
                    )

                # Load broker credentials
                if not settings.broker_creds_encrypted:
                    user_logger.error(
                        "No broker credentials stored", action="start_service"
                    )
                    raise ValueError(f"No broker credentials stored for user_id={user_id}")

                # TODO: Decrypt broker credentials (Phase 2.4)
                # For now, we'll need to handle this - broker_creds should be a dict
                # broker_creds = decrypt_broker_creds(settings.broker_creds_encrypted)
                # Temporary: create broker_creds dict from encrypted data
                # This is a placeholder until Phase 2.4 implements proper decryption
                broker_creds = {}  # TODO: Decrypt from settings.broker_creds_encrypted

                # Load user trading configuration and convert to StrategyConfig
                user_config = self._config_repo.get_or_create_default(user_id)
                from src.application.services.config_converter import (
                    user_config_to_strategy_config,
                )

                strategy_config = user_config_to_strategy_config(user_config)

                # Initialize TradingService with user context (Phase 2.3)
                from modules.kotak_neo_auto_trader.run_trading_service import (
                    TradingService,
                )

                service = TradingService(
                    user_id=user_id,
                    db_session=self.db,
                    broker_creds=broker_creds,
                    strategy_config=strategy_config,
                    env_file=None,  # Will use broker_creds instead (Phase 2.4)
                )

                # Store service instance
                self._services[user_id] = service

                # Update service status
                self._service_status_repo.update_running(user_id, running=True)
                self._service_status_repo.update_heartbeat(user_id)

                user_logger.info("Trading service started successfully", action="start_service")

                # TODO: Start service in background thread
                # service_thread = threading.Thread(
                #     target=service.run,
                #     daemon=True,
                #     name=f"TradingService-{user_id}"
                # )
                # service_thread.start()

                return True

            except Exception as e:
                # Log error and update status
                user_logger = get_user_logger(
                    user_id=user_id, db=self.db, module="TradingService"
                )
                user_logger.error(
                    "Failed to start trading service",
                    exc_info=e,
                    action="start_service",
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
            return False  # Service was never started

        with self._locks[user_id]:
            if user_id not in self._services:
                return False  # Service not running

            try:
                # Get user-specific logger
                user_logger = get_user_logger(
                    user_id=user_id, db=self.db, module="TradingService"
                )
                user_logger.info("Stopping trading service", action="stop_service")

                service = self._services[user_id]

                # Request shutdown
                if hasattr(service, "shutdown_requested"):
                    service.shutdown_requested = True

                # Wait for service to stop (with timeout)
                # TODO: Implement graceful shutdown

                # Remove service instance
                del self._services[user_id]

                # Update service status
                self._service_status_repo.update_running(user_id, running=False)
                self._service_status_repo.update_heartbeat(user_id)

                user_logger.info("Trading service stopped successfully", action="stop_service")
                return True

            except Exception as e:
                # Log error
                user_logger = get_user_logger(
                    user_id=user_id, db=self.db, module="TradingService"
                )
                user_logger.error(
                    "Failed to stop trading service",
                    exc_info=e,
                    action="stop_service",
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
