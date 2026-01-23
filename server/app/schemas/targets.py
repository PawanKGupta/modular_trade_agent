from datetime import datetime

from pydantic import BaseModel


class TargetItem(BaseModel):
    """Target item schema for API responses (Phase 0.4)"""

    id: int
    symbol: str
    target_price: float
    entry_price: float
    current_price: float | None = None
    quantity: float
    distance_to_target: float | None = None
    distance_to_target_absolute: float | None = None
    target_type: str = "ema9"
    is_active: bool = True
    achieved_at: datetime | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime
