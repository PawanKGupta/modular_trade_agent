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
    status: Annotated[Literal["amo", "ongoing", "sell", "closed"] | None, Query()] = None,
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
        }
        db_status = status_map.get(status) if status else None
        items = repo.list(current.id, db_status)

        # map DB columns to API model field names
        result = []
        for o in items:
            try:
                # Handle datetime fields - they might be strings from raw SQL or datetime objects
                created_at_str = None
                if o.placed_at:
                    if isinstance(o.placed_at, str):
                        created_at_str = o.placed_at
                    elif isinstance(o.placed_at, datetime):
                        created_at_str = o.placed_at.isoformat()
                    else:
                        created_at_str = str(o.placed_at)

                updated_at_str = None
                if o.closed_at:
                    if isinstance(o.closed_at, str):
                        updated_at_str = o.closed_at
                    elif isinstance(o.closed_at, datetime):
                        updated_at_str = o.closed_at.isoformat()
                    else:
                        updated_at_str = str(o.closed_at)

                order_response = OrderResponse(
                    id=o.id,
                    symbol=o.symbol,
                    side=o.side if o.side in ("buy", "sell") else "buy",  # type: ignore[arg-type]
                    quantity=o.quantity,
                    price=o.price,
                    status=o.status.value if o.status else "amo",
                    created_at=created_at_str,
                    updated_at=updated_at_str,
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
