from typing import Literal

from pydantic import BaseModel

OrderStatus = Literal["amo", "ongoing", "sell", "closed"]


class OrderResponse(BaseModel):
    id: int
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float | None
    status: OrderStatus
    created_at: str | None = None
    updated_at: str | None = None
