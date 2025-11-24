import logging
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.orm import Session

from src.infrastructure.db.models import OrderStatus as DbOrderStatus
from src.infrastructure.db.models import Users
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.orders_repository import OrdersRepository

from ..core.deps import get_current_user, get_db
from ..schemas.orders import OrderResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=list[OrderResponse])  # noqa: PLR0913
def list_orders(
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

        # map DB columns to API model field names
        result = []
        for o in items:
            try:
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

        # Update order for retry (keep as FAILED, update retry metadata)
        order.retry_count = (order.retry_count or 0) + 1
        order.last_retry_attempt = ist_now()
        if not order.first_failed_at:
            order.first_failed_at = ist_now()
        # Update reason to indicate manual retry
        if order.reason:
            order.reason = f"{order.reason} (Manual retry requested)"
        else:
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


@router.get("/statistics", response_model=dict)
def get_order_statistics(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
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
