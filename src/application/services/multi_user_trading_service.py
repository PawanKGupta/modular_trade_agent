"""
Multi-User Trading Service Wrapper

Manages trading service instances for multiple users, ensuring isolation
and proper lifecycle management.
"""

from __future__ import annotations

import threading

from sqlalchemy.orm import Session

from src.infrastructure.db.timezone_utils import ist_now
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
                # Load user settings
                settings = self._settings_repo.get_by_user_id(user_id)
                if not settings:
                    raise ValueError(f"User settings not found for user_id={user_id}")

                # Check trade mode
                if settings.trade_mode.value != "broker":
                    raise ValueError(
                        f"User {user_id} is in {settings.trade_mode.value} mode, "
                        "broker mode required for trading service"
                    )

                # Load broker credentials
                if not settings.broker_creds_encrypted:
                    raise ValueError(f"No broker credentials stored for user_id={user_id}")

                # TODO: Decrypt broker credentials
                # broker_creds = decrypt_broker_creds(settings.broker_creds_encrypted)

                # Load user trading configuration
                # TODO: Use user_config when initializing TradingService (2.3)
                _user_config = self._config_repo.get_or_create_default(user_id)

                # TODO: Initialize TradingService with user context
                # This will be implemented in 2.3 User Context Integration
                # For now, we'll create a placeholder
                # service = TradingService(
                #     user_id=user_id,
                #     db=self.db,
                #     broker_creds=broker_creds,
                #     user_config=user_config
                # )

                # Store service instance
                # self._services[user_id] = service

                # Update service status
                status = self._service_status_repo.get_or_create(user_id)
                status.service_running = True
                status.last_heartbeat = ist_now()
                self._service_status_repo.update(status)

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
                status = self._service_status_repo.get_or_create(user_id)
                status.service_running = False
                status.error_count += 1
                status.last_error = str(e)
                self._service_status_repo.update(status)
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
                service = self._services[user_id]

                # Request shutdown
                if hasattr(service, "shutdown_requested"):
                    service.shutdown_requested = True

                # Wait for service to stop (with timeout)
                # TODO: Implement graceful shutdown

                # Remove service instance
                del self._services[user_id]

                # Update service status
                status = self._service_status_repo.get_or_create(user_id)
                status.service_running = False
                status.last_heartbeat = ist_now()
                self._service_status_repo.update(status)

                return True

            except Exception as e:
                # Log error
                status = self._service_status_repo.get_or_create(user_id)
                status.error_count += 1
                status.last_error = str(e)
                self._service_status_repo.update(status)
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
