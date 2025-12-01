from datetime import date

from pydantic import BaseModel


class DailyPnl(BaseModel):
    date: date
    pnl: float


class PnlSummary(BaseModel):
    totalPnl: float
    daysGreen: int
    daysRed: int
