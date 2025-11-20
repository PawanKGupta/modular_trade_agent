import logging
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.orm import Session

from src.infrastructure.db.models import OrderStatus as DbOrderStatus
from src.infrastructure.db.models import Users
from src.infrastructure.persistence.orders_repository import OrdersRepository

from ..core.deps import get_current_user, get_db
from ..schemas.orders import OrderResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=list[OrderResponse])
def list_orders(
    status: Annotated[
        Literal[
            "amo",
            "ongoing",
            "sell",
            "closed",
            "failed",
            "retry_pending",
            "rejected",
            "pending_execution",
        ]
        | None,
        Query(),
    ] = None,
    db: Session = Depends(get_db),  # noqa: B008 - FastAPI dependency injection
    current: Users = Depends(get_current_user),  # noqa: B008 - FastAPI dependency injection
) -> list[OrderResponse]:
    try:
        repo = OrdersRepository(db)
        # Map string status to enum member
        status_map = {
            "amo": DbOrderStatus.AMO,
            "ongoing": DbOrderStatus.ONGOING,
            "sell": DbOrderStatus.SELL,
            "closed": DbOrderStatus.CLOSED,
            "failed": DbOrderStatus.FAILED,
            "retry_pending": DbOrderStatus.RETRY_PENDING,
            "rejected": DbOrderStatus.REJECTED,
            "pending_execution": DbOrderStatus.PENDING_EXECUTION,
        }
        db_status = status_map.get(status) if status else None
        items = repo.list(current.id, db_status)

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
                    status=o.status.value if o.status else "amo",
                    created_at=format_datetime(o.placed_at),
                    updated_at=format_datetime(o.closed_at),
                    # Order monitoring fields
                    failure_reason=getattr(o, "failure_reason", None),
                    first_failed_at=format_datetime(getattr(o, "first_failed_at", None)),
                    last_retry_attempt=format_datetime(getattr(o, "last_retry_attempt", None)),
                    retry_count=getattr(o, "retry_count", 0) or 0,
                    rejection_reason=getattr(o, "rejection_reason", None),
                    cancelled_reason=getattr(o, "cancelled_reason", None),
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
