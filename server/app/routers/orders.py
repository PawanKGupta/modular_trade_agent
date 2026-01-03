import logging
from datetime import datetime
from math import floor
from pathlib import Path
from typing import Annotated, Literal

import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.orm import Session

from modules.kotak_neo_auto_trader import config as kotak_config
from modules.kotak_neo_auto_trader.infrastructure.broker_factory import BrokerFactory
from modules.kotak_neo_auto_trader.shared_session_manager import (
    get_shared_session_manager,
)
from modules.kotak_neo_auto_trader.utils.order_field_extractor import (
    OrderFieldExtractor,
)
from src.application.services.broker_credentials import (
    create_temp_env_file,
    decrypt_broker_credentials,
)
from src.application.services.conflict_detection_service import ConflictDetectionService
from src.infrastructure.db.models import OrderStatus as DbOrderStatus
from src.infrastructure.db.models import TradeMode, Users
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.individual_service_status_repository import (
    IndividualServiceStatusRepository,
)
from src.infrastructure.persistence.orders_repository import OrdersRepository
from src.infrastructure.persistence.settings_repository import SettingsRepository
from src.infrastructure.persistence.user_trading_config_repository import (
    UserTradingConfigRepository,
)

from ..core.deps import get_current_user, get_db
from ..schemas.orders import OrderResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def _is_order_monitoring_active(user_id: int, db: Session) -> bool:
    """
    Check if order monitoring is active (unified service or sell_monitor individual service).

    Returns:
        True if unified service OR sell_monitor service is running
    """
    try:
        # Check unified service
        conflict_service = ConflictDetectionService(db)
        if conflict_service.is_unified_service_running(user_id):
            return True

        # Check sell_monitor individual service
        status_repo = IndividualServiceStatusRepository(db)
        sell_monitor_status = status_repo.get_by_user_and_task(user_id, "sell_monitor")
        if sell_monitor_status and sell_monitor_status.is_running:
            return True
    except Exception as e:
        logger.debug(f"Error checking order monitoring status: {e}")

    return False


def _recalculate_order_quantity(order, user_id: int, db: Session, order_id: int) -> None:
    """
    Recalculate order quantity based on current price and capital per trade.

    Updates order.quantity and order.price in place.
    """
    try:
        # Get user's trading config (capital per trade)
        trading_config_repo = UserTradingConfigRepository(db)
        trading_config = trading_config_repo.get(user_id)
        user_capital = trading_config.capital_per_trade if trading_config else 20000.0

        # Get current price from yfinance
        from modules.kotak_neo_auto_trader.utils.symbol_utils import get_ticker_from_full_symbol

        ticker = getattr(order, "ticker", None) or get_ticker_from_full_symbol(order.symbol)
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if hist.empty:
            # Fallback to order price if current price unavailable
            current_price = order.price or 0.0
            logger.warning(
                f"Could not fetch current price for {ticker}, using order price {current_price}"
            )
        else:
            current_price = float(hist["Close"].iloc[-1])

        if current_price <= 0:
            raise ValueError(f"Invalid current price: {current_price}")

        # Calculate execution capital (simplified - use user_capital directly)
        # In production, this would use LiquidityCapitalService like AutoTradeEngine
        execution_capital = user_capital

        # Calculate new quantity
        new_qty = max(kotak_config.MIN_QTY, floor(execution_capital / current_price))

        # Update order quantity and price
        old_qty = order.quantity
        order.quantity = new_qty
        order.price = current_price

        logger.info(
            f"Recalculated quantity for order {order_id} ({order.symbol}): "
            f"{old_qty} -> {new_qty} shares "
            f"(capital: Rs {user_capital:,.0f}, price: Rs {current_price:.2f})"
        )
    except Exception as calc_error:
        logger.warning(
            f"Failed to recalculate quantity for order {order_id}: {calc_error}. "
            "Using original quantity."
        )
        # Continue with original quantity if recalculation fails


@router.get("/", response_model=list[OrderResponse])
def list_orders(  # noqa: PLR0913
    status: Annotated[
        Literal[
            "pending",  # Merged: AMO + PENDING_EXECUTION
            "ongoing",
            "closed",
            "failed",  # Merged: FAILED + RETRY_PENDING + REJECTED
            "cancelled",
            # Note: SELL status removed - use side='sell' to filter sell orders
        ]
        | None,
        Query(description="Filter by order status"),
    ] = None,
    reason: Annotated[
        str | None,
        Query(description="Filter by reason (partial match)"),
    ] = None,
    from_date: Annotated[
        str | None,
        Query(description="Filter orders from this date (ISO format: YYYY-MM-DD)"),
    ] = None,
    to_date: Annotated[
        str | None,
        Query(description="Filter orders to this date (ISO format: YYYY-MM-DD)"),
    ] = None,
    db: Session = Depends(get_db),  # noqa: B008 - FastAPI dependency injection
    current: Users = Depends(get_current_user),  # noqa: B008 - FastAPI dependency injection
) -> list[OrderResponse]:
    try:
        repo = OrdersRepository(db)
        # Map string status to enum member
        status_map = {
            "pending": DbOrderStatus.PENDING,  # Merged: AMO + PENDING_EXECUTION
            "ongoing": DbOrderStatus.ONGOING,
            "closed": DbOrderStatus.CLOSED,
            "failed": DbOrderStatus.FAILED,  # Merged: FAILED + RETRY_PENDING + REJECTED
            "cancelled": DbOrderStatus.CANCELLED,
            # Note: SELL status removed - use side='sell' to filter sell orders
        }
        db_status = status_map.get(status) if status else None
        items = repo.list(current.id, db_status)

        # Apply additional filters
        if reason:
            items = [
                o
                for o in items
                if getattr(o, "reason", None) and reason.lower() in getattr(o, "reason", "").lower()
            ]

        if from_date or to_date:
            try:
                from_date_obj = datetime.fromisoformat(from_date) if from_date else None
                to_date_obj = datetime.fromisoformat(to_date) if to_date else None

                filtered_items = []
                for o in items:
                    # Use placed_at for date filtering
                    order_date = o.placed_at
                    if order_date:
                        if from_date_obj and order_date < from_date_obj:
                            continue
                        if to_date_obj and order_date > to_date_obj:
                            continue
                    filtered_items.append(o)
                items = filtered_items
            except ValueError as e:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid date format: {str(e)}. Use ISO format (YYYY-MM-DD)",
                ) from e

        # Helper function to format datetime fields
        def format_datetime(dt_value):
            if dt_value is None:
                return None
            if isinstance(dt_value, str):
                return dt_value
            if isinstance(dt_value, datetime):
                return dt_value.isoformat()
            return str(dt_value)

        # Get user settings once for broker name lookup
        settings_repo = SettingsRepository(db)
        user_settings = settings_repo.get_by_user_id(current.id)
        broker_name = user_settings.broker if user_settings else None

        # Helper function to format broker name for display
        def format_broker_name(broker: str | None) -> str:
            """Format broker name for display (e.g., 'kotak-neo' -> 'Kotak Neo')"""
            if not broker:
                return "Broker"
            # Convert kebab-case to Title Case
            return broker.replace("-", " ").title()

        # map DB columns to API model field names
        result = []
        for o in items:
            try:
                # Get trade_mode from order and determine display name (Phase 0.1)
                trade_mode_display = None
                if hasattr(o, "trade_mode") and o.trade_mode:
                    trade_mode_value = (
                        o.trade_mode.value if hasattr(o.trade_mode, "value") else str(o.trade_mode)
                    )
                    if trade_mode_value == "paper":
                        trade_mode_display = "Paper"
                    elif trade_mode_value == "broker":
                        # Use broker name from settings, or fallback to "Broker"
                        trade_mode_display = (
                            format_broker_name(broker_name) if broker_name else "Broker"
                        )

                order_response = OrderResponse(
                    id=o.id,
                    symbol=o.symbol,
                    side=o.side if o.side in ("buy", "sell") else "buy",  # type: ignore[arg-type]
                    quantity=o.quantity,
                    price=o.price,
                    status=o.status.value if o.status else "pending",
                    created_at=format_datetime(o.placed_at),
                    updated_at=format_datetime(o.closed_at),
                    # Unified reason field
                    reason=getattr(o, "reason", None),
                    # Order monitoring fields
                    first_failed_at=format_datetime(getattr(o, "first_failed_at", None)),
                    last_retry_attempt=format_datetime(getattr(o, "last_retry_attempt", None)),
                    retry_count=getattr(o, "retry_count", 0) or 0,
                    last_status_check=format_datetime(getattr(o, "last_status_check", None)),
                    execution_price=getattr(o, "execution_price", None),
                    execution_qty=getattr(o, "execution_qty", None),
                    execution_time=format_datetime(getattr(o, "execution_time", None)),
                    # Entry type and source tracking
                    entry_type=getattr(o, "entry_type", None),
                    is_manual=getattr(o, "orig_source", None) == "manual",
                    # Phase 0.1: Trade mode display name
                    trade_mode_display=trade_mode_display,
                )
                result.append(order_response)
            except Exception as e:
                logger.error(f"Error serializing order {o.id}: {e}", exc_info=True)
                # Skip this order and continue
                continue

        return result
    except Exception as e:
        logger.exception(f"Error listing orders for user {current.id}: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list orders: {str(e)}",
        ) from e


@router.post("/{order_id}/retry", response_model=OrderResponse)
def retry_order(
    order_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
) -> OrderResponse:
    """
    Retry a failed order.

    Marks the order as FAILED (retriable) and updates retry metadata.
    The actual retry will be handled by AutoTradeEngine on next run.
    Note: All FAILED orders are retriable until expiry.
    """
    try:
        repo = OrdersRepository(db)
        order = repo.get(order_id)

        if not order:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found",
            )

        if order.user_id != current.id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this order",
            )

        # Only allow retry for FAILED orders (merged: FAILED + RETRY_PENDING + REJECTED)
        if order.status != DbOrderStatus.FAILED:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot retry order with status {order.status.value}. "
                    "Only failed orders can be retried."
                ),
            )

        # Recalculate quantity based on current price and capital per trade
        _recalculate_order_quantity(order, current.id, db, order_id)

        # Update order for retry (keep as FAILED, update retry metadata)
        order.retry_count = (order.retry_count or 0) + 1
        order.last_retry_attempt = ist_now()
        if not order.first_failed_at:
            order.first_failed_at = ist_now()
        # Update reason to indicate manual retry (remove duplicate "Manual retry requested")
        if order.reason and "(Manual retry requested)" not in order.reason:
            order.reason = f"{order.reason} (Manual retry requested)"
        elif not order.reason:
            order.reason = "Manual retry requested"

        updated_order = repo.update(order)

        # Format response
        def format_datetime(dt_value):
            if dt_value is None:
                return None
            if isinstance(dt_value, str):
                return dt_value
            if isinstance(dt_value, datetime):
                return dt_value.isoformat()
            return str(dt_value)

        return OrderResponse(
            id=updated_order.id,
            symbol=updated_order.symbol,
            side=updated_order.side if updated_order.side in ("buy", "sell") else "buy",  # type: ignore[arg-type]
            quantity=updated_order.quantity,
            price=updated_order.price,
            status=updated_order.status.value if updated_order.status else "failed",
            created_at=format_datetime(updated_order.placed_at),
            updated_at=format_datetime(updated_order.closed_at),
            reason=getattr(updated_order, "reason", None),
            first_failed_at=format_datetime(getattr(updated_order, "first_failed_at", None)),
            last_retry_attempt=format_datetime(getattr(updated_order, "last_retry_attempt", None)),
            retry_count=getattr(updated_order, "retry_count", 0) or 0,
            last_status_check=format_datetime(getattr(updated_order, "last_status_check", None)),
            execution_price=getattr(updated_order, "execution_price", None),
            execution_qty=getattr(updated_order, "execution_qty", None),
            execution_time=format_datetime(getattr(updated_order, "execution_time", None)),
            entry_type=getattr(updated_order, "entry_type", None),
            is_manual=getattr(updated_order, "orig_source", None) == "manual",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error retrying order {order_id} for user {current.id}: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry order: {str(e)}",
        ) from e


@router.delete("/{order_id}")
def drop_order(
    order_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
) -> dict[str, str]:
    """
    Drop an order from the retry queue.

    Marks the order as CLOSED, removing it from retry tracking.
    """
    try:
        repo = OrdersRepository(db)
        order = repo.get(order_id)

        if not order:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found",
            )

        if order.user_id != current.id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this order",
            )

        # Only allow dropping FAILED orders (merged: FAILED + RETRY_PENDING + REJECTED)
        if order.status != DbOrderStatus.FAILED:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot drop order with status {order.status.value}. "
                    "Only failed orders can be dropped."
                ),
            )

        # Mark as closed
        order.status = DbOrderStatus.CLOSED
        order.closed_at = ist_now()
        repo.update(order)

        return {"message": f"Order {order_id} dropped from retry queue"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error dropping order {order_id} for user {current.id}: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to drop order: {str(e)}",
        ) from e


@router.post("/sync", response_model=dict)
def sync_order_status(
    order_id: Annotated[
        int | None,
        Query(
            description="Optional: Sync specific order. If None, syncs all pending/ongoing orders"
        ),
    ] = None,
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
) -> dict:
    """
    Manually sync order status from broker.

    Useful when:
    - Order monitoring service is not running
    - Force refresh order status
    - Troubleshooting order status issues

    Args:
        order_id: Optional order ID to sync specific order.
            If None, syncs all pending/ongoing orders.

    Returns:
        Dict with sync results: {
            "message": str,
            "sync_performed": bool,
            "monitoring_active": bool,
            "synced": int,
            "updated": int,
            "executed": int,
            "rejected": int,
            "cancelled": int,
            "errors": list[str]
        }
    """
    try:
        # Perform manual sync
        settings_repo = SettingsRepository(db)
        settings = settings_repo.get_by_user_id(current.id)

        if not settings:
            raise HTTPException(
                status_code=400,
                detail="User settings not found",
            )

        # Handle paper trading mode
        if settings.trade_mode == TradeMode.PAPER:
            # For paper trading, orders are executed immediately (simulated)
            # No broker sync needed, but we can refresh the orders list
            repo = OrdersRepository(db)
            if order_id:
                # Sync specific order - for paper trading, just refresh from DB
                order = repo.get(order_id)
                if not order or order.user_id != current.id:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Order {order_id} not found",
                    )
                if order.trade_mode != TradeMode.PAPER:
                    raise HTTPException(
                        status_code=400,
                        detail="Order is not a paper trading order",
                    )
                # Paper trading orders are already up-to-date (executed immediately)
                return {
                    "message": "Paper trading orders are executed immediately. No sync needed.",
                    "sync_performed": False,
                    "monitoring_active": False,
                    "synced": 1,
                    "updated": 0,
                    "executed": 0,
                    "rejected": 0,
                    "cancelled": 0,
                    "errors": [],
                }
            else:
                # Sync all paper trading orders - just refresh from DB
                all_orders = repo.list(current.id, status=None)
                paper_orders = [
                    o
                    for o in all_orders
                    if o.trade_mode == TradeMode.PAPER
                    and o.status in [DbOrderStatus.PENDING, DbOrderStatus.ONGOING]
                ]
                paper_msg = (
                    f"Paper trading orders are executed immediately. "
                    f"Found {len(paper_orders)} active paper orders."
                )
                return {
                    "message": paper_msg,
                    "sync_performed": False,
                    "monitoring_active": False,
                    "synced": len(paper_orders),
                    "updated": 0,
                    "executed": 0,
                    "rejected": 0,
                    "cancelled": 0,
                    "errors": [],
                }

        # Handle broker mode
        if settings.trade_mode != TradeMode.BROKER:
            raise HTTPException(
                status_code=400,
                detail="Broker mode or paper trading mode required for order sync",
            )

        if not settings.broker_creds_encrypted:
            raise HTTPException(
                status_code=400,
                detail="Broker credentials not configured",
            )

        # Check if monitoring is active (after validating broker mode/creds)
        if _is_order_monitoring_active(current.id, db):
            return {
                "message": (
                    "Order monitoring service is active. Status syncs automatically every minute."
                ),
                "sync_performed": False,
                "monitoring_active": True,
                "synced": 0,
                "updated": 0,
                "executed": 0,
                "rejected": 0,
                "cancelled": 0,
                "errors": [],
            }

        # Get broker session
        broker_creds = decrypt_broker_credentials(settings.broker_creds_encrypted)
        env_file = create_temp_env_file(broker_creds)

        try:
            session_manager = get_shared_session_manager()
            auth = session_manager.get_or_create_session(current.id, env_file, db)

            broker = BrokerFactory.create_broker("kotak_neo", auth)
            if not broker.connect():
                raise HTTPException(
                    status_code=503,
                    detail="Failed to connect to broker",
                )

            # Fetch broker orders
            orders_api = broker.orders if hasattr(broker, "orders") else None
            if not orders_api:
                raise HTTPException(
                    status_code=500,
                    detail="Broker orders API not available",
                )

            try:
                orders_response = orders_api.get_orders()
                if orders_response is None:
                    logger.warning("Broker get_orders() returned None")
                    orders_response = {}
            except Exception as e:
                logger.error(f"Error fetching broker orders: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to fetch broker orders: {str(e)}",
                ) from e

            broker_orders = (
                orders_response.get("data", []) if isinstance(orders_response, dict) else []
            )

            # Get orders to sync
            repo = OrdersRepository(db)
            if order_id:
                # Sync specific order
                order = repo.get(order_id)
                if not order or order.user_id != current.id:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Order {order_id} not found",
                    )
                orders_to_sync = [order]
            else:
                # Sync all pending/ongoing orders
                all_orders = repo.list(current.id, status=None)
                orders_to_sync = [
                    o
                    for o in all_orders
                    if o.status in [DbOrderStatus.PENDING, DbOrderStatus.ONGOING]
                ]

            # Sync each order
            stats = {
                "synced": 0,
                "updated": 0,
                "executed": 0,
                "rejected": 0,
                "cancelled": 0,
                "errors": [],
            }

            for db_order in orders_to_sync:
                stats["synced"] += 1
                order_id_str = db_order.broker_order_id or db_order.order_id
                if not order_id_str:
                    stats["errors"].append(f"Order {db_order.id} has no broker_order_id")
                    continue

                # Find order in broker orders
                broker_order = None
                for bo in broker_orders:
                    try:
                        broker_order_id = OrderFieldExtractor.get_order_id(bo)
                        if broker_order_id and broker_order_id == str(order_id_str):
                            broker_order = bo
                            break
                    except Exception as e:
                        logger.debug(f"Error extracting order ID from broker order: {e}")
                        continue

                if not broker_order:
                    # Order not found in broker - might be executed and removed
                    # Check holdings to see if it was executed (optional enhancement)
                    continue

                # Extract status
                status = OrderFieldExtractor.get_status(broker_order)
                status_lower = status.lower() if status else ""

                if not status_lower:
                    continue

                # Update order status
                try:
                    if status_lower in ["rejected", "reject"]:
                        try:
                            rejection_reason = (
                                OrderFieldExtractor.get_rejection_reason(broker_order)
                                or "Rejected by broker"
                            )
                        except Exception as e:
                            logger.warning(f"Error extracting rejection reason: {e}")
                            rejection_reason = "Rejected by broker"
                        repo.mark_rejected(db_order, rejection_reason)
                        stats["rejected"] += 1
                        stats["updated"] += 1
                    elif status_lower in ["cancelled", "cancel"]:
                        try:
                            cancelled_reason = (
                                OrderFieldExtractor.get_rejection_reason(broker_order)
                                or "Cancelled"
                            )
                        except Exception as e:
                            logger.warning(f"Error extracting cancellation reason: {e}")
                            cancelled_reason = "Cancelled"
                        repo.mark_cancelled(db_order, cancelled_reason)
                        stats["cancelled"] += 1
                        stats["updated"] += 1
                    elif status_lower in ["executed", "filled", "complete"]:
                        try:
                            execution_price = OrderFieldExtractor.get_price(broker_order)
                            if execution_price is None or execution_price <= 0:
                                logger.warning(
                                    f"Invalid execution price for order {db_order.id}: "
                                    f"{execution_price}"
                                )
                                execution_price = db_order.price or 0.0

                            execution_qty = (
                                OrderFieldExtractor.get_filled_quantity(broker_order)
                                or OrderFieldExtractor.get_quantity(broker_order)
                                or db_order.quantity
                            )
                            if execution_qty is None or execution_qty <= 0:
                                logger.warning(
                                    f"Invalid execution qty for order {db_order.id}: "
                                    f"{execution_qty}"
                                )
                                execution_qty = db_order.quantity

                            repo.mark_executed(
                                db_order,
                                execution_price=execution_price,
                                execution_qty=execution_qty,
                            )
                            stats["executed"] += 1
                            stats["updated"] += 1
                        except Exception as e:
                            logger.error(
                                f"Error marking order {db_order.id} as executed: {e}", exc_info=True
                            )
                            stats["errors"].append(
                                f"Order {db_order.id}: Failed to mark as executed: {str(e)}"
                            )
                    elif status_lower in ["pending", "open", "trigger_pending"]:
                        # Update last_status_check
                        repo.update_status_check(db_order)
                        stats["updated"] += 1
                except Exception as e:
                    stats["errors"].append(f"Error updating order {db_order.id}: {str(e)}")

            return {
                "message": "Order sync completed",
                "sync_performed": True,
                "monitoring_active": False,
                **stats,
            }

        finally:
            # Cleanup temp env file
            try:
                Path(env_file).unlink(missing_ok=True)
            except Exception as cleanup_error:
                logger.debug(f"Failed to cleanup temp env file: {cleanup_error}")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error syncing order status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync order status: {str(e)}",
        ) from e


@router.get("/statistics", response_model=dict)
def get_order_statistics(
    current_user: Users = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Get order statistics for monitoring.

    Phase 11: Monitoring metrics endpoint.

    Returns:
        Dict with order statistics including status distribution
    """
    repo = OrdersRepository(db)
    stats = repo.get_order_statistics(current_user.id)

    return stats
