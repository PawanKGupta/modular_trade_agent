"""
Error Capture and Storage

Captures exceptions with full context and stores them in ErrorLog table.
"""

from __future__ import annotations

import traceback
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.infrastructure.persistence.error_log_repository import ErrorLogRepository
from src.infrastructure.persistence.service_status_repository import ServiceStatusRepository
from src.infrastructure.persistence.user_trading_config_repository import (
    UserTradingConfigRepository,
)


def capture_exception(
    user_id: int,
    exception: Exception,
    context: dict[str, Any],
    db: Session,
    include_user_state: bool = True,
) -> None:
    """
    Capture exception with full context and store in ErrorLog table.
    
    Args:
        user_id: User ID who encountered the error
        exception: Exception object to capture
        context: Additional context data (symbol, order_id, etc.)
        db: Database session
        include_user_state: Whether to include user config and service status
    """
    try:
        error_repo = ErrorLogRepository(db)

        # Build comprehensive context
        error_context: dict[str, Any] = context.copy()

        if include_user_state:
            # Add user configuration at time of error
            try:
                config_repo = UserTradingConfigRepository(db)
                user_config = config_repo.get(user_id)
                if user_config:
                    # Convert config to dict (exclude sensitive/internal fields)
                    error_context["user_config"] = {
                        "rsi_oversold": user_config.rsi_oversold,
                        "user_capital": user_config.user_capital,
                        "max_portfolio_size": user_config.max_portfolio_size,
                        "ml_enabled": user_config.ml_enabled,
                    }
            except Exception:
                pass  # Non-fatal if config fetch fails

            # Add service status at time of error
            try:
                status_repo = ServiceStatusRepository(db)
                service_status = status_repo.get(user_id)
                if service_status:
                    error_context["service_status"] = {
                        "service_running": service_status.service_running,
                        "error_count": service_status.error_count,
                        "last_heartbeat": (
                            service_status.last_heartbeat.isoformat()
                            if service_status.last_heartbeat
                            else None
                        ),
                    }
            except Exception:
                pass  # Non-fatal if status fetch fails

        # Get traceback
        tb_str = traceback.format_exc()

        # Create error log entry
        error_repo.create(
            user_id=user_id,
            error_type=type(exception).__name__[:128],  # Truncate to max length
            error_message=str(exception)[:1024],  # Truncate to max length
            traceback=tb_str[:8192] if tb_str else None,  # Truncate to max length
            context=error_context if error_context else None,
        )

    except Exception as e:
        # Fallback: if error capture itself fails, at least log it
        # This prevents error capture from breaking the application
        import logging

        logger = logging.getLogger("TradeAgent.ErrorCapture")
        logger.error(
            f"Failed to capture exception for user {user_id}: {e}",
            exc_info=True,
            extra={"original_exception": str(exception)},
        )

