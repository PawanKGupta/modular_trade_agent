from typing import Literal

from pydantic import BaseModel

OrderStatus = Literal[
    "amo",
    "ongoing",
    "sell",
    "closed",
    "failed",
    "retry_pending",
    "rejected",
    "pending_execution",
]


class OrderResponse(BaseModel):
    id: int
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float | None
    status: OrderStatus
    created_at: str | None = None
    updated_at: str | None = None
    # Order monitoring fields
    failure_reason: str | None = None
    first_failed_at: str | None = None
    last_retry_attempt: str | None = None
    retry_count: int = 0
    rejection_reason: str | None = None
    cancelled_reason: str | None = None
    last_status_check: str | None = None
    execution_price: float | None = None
    execution_qty: float | None = None
    execution_time: str | None = None
