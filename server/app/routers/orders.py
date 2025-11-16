from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.infrastructure.db.models import OrderStatus as DbOrderStatus
from src.infrastructure.db.models import Users
from src.infrastructure.persistence.orders_repository import OrdersRepository

from ..core.deps import get_current_user, get_db
from ..schemas.orders import OrderResponse

router = APIRouter()


@router.get("/", response_model=list[OrderResponse])
def list_orders(
    status: Annotated[Literal["amo", "ongoing", "sell", "closed"] | None, Query()] = None,
    db: Session = Depends(get_db),  # noqa: B008 - FastAPI dependency injection
    current: Users = Depends(get_current_user),  # noqa: B008 - FastAPI dependency injection
) -> list[OrderResponse]:
    repo = OrdersRepository(db)
    db_status = DbOrderStatus(status) if status else None
    items = repo.list(current.id, db_status)
    # map DB columns to API model field names
    return [
        OrderResponse(
            id=o.id,
            symbol=o.symbol,
            side=o.side if o.side in ("buy", "sell") else "buy",  # type: ignore[arg-type]
            quantity=o.quantity,
            price=o.price,
            status=o.status.value,
            created_at=o.placed_at.isoformat() if o.placed_at else None,
            updated_at=o.closed_at.isoformat() if o.closed_at else None,
        )
        for o in items
    ]
