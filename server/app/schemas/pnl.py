from datetime import date

from pydantic import BaseModel


class DailyPnl(BaseModel):
    date: date
    pnl: float


class PnlSummary(BaseModel):
    # Aggregate totals
    totalPnl: float
    totalRealizedPnl: float
    totalUnrealizedPnl: float

    # Trade-level stats (closed trades)
    tradesGreen: int  # profitable trades count
    tradesRed: int  # loss trades count
    minTradePnl: float
    maxTradePnl: float
    avgTradePnl: float

    # Backward-compat fields (mapped to trade counts to match expectation)
    daysGreen: int
    daysRed: int
