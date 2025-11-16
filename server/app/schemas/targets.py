from datetime import datetime

from pydantic import BaseModel


class TargetItem(BaseModel):
    id: int
    symbol: str
    target_price: float
    note: str | None = None
    created_at: datetime
