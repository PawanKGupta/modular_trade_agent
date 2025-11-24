from typing import Literal

from pydantic import BaseModel

OrderStatus = Literal[
    "pending",  # Merged: AMO + PENDING_EXECUTION
    "ongoing",
    "closed",
    "failed",  # Merged: FAILED + RETRY_PENDING + REJECTED
    "cancelled",
    # Note: SELL status removed - use side='sell' to identify sell orders
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
    # Unified reason field (replaces failure_reason, rejection_reason, cancelled_reason)
    reason: str | None = None
    # Order monitoring fields
    first_failed_at: str | None = None
    last_retry_attempt: str | None = None
    retry_count: int = 0
    last_status_check: str | None = None
    execution_price: float | None = None
    execution_qty: float | None = None
    execution_time: str | None = None
    # Entry type and source tracking
    entry_type: str | None = None  # 'initial', 'reentry', 'manual'
    is_manual: bool = False  # Derived from orig_source == 'manual'
