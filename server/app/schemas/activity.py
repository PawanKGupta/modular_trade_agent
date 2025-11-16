from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ActivityItem(BaseModel):
    id: int
    ts: datetime
    event: str
    detail: str | None = None
    level: Literal["info", "warn", "error"] = "info"
