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


class ClosedPositionDetail(BaseModel):
    id: int
    symbol: str
    stock_name: str | None  # Resolved from yfinance
    quantity: float
    avg_price: float
    exit_price: float | None
    opened_at: str
    closed_at: str
    realized_pnl: float | None
    realized_pnl_pct: float | None
    exit_reason: str | None


class PaginatedClosedPositions(BaseModel):
    items: list[ClosedPositionDetail]
    total: int
    page: int
    page_size: int
    total_pages: int
