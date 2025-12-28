"""
Dashboard Metrics API endpoints

Provides enhanced metrics for the dashboard including win rate, average profit,
best/worst trades, and other trading performance statistics.
"""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Orders, Positions, TradeMode, Users
from src.infrastructure.db.session import engine
from src.infrastructure.db.connection_monitor import get_pool_status, check_pool_health
from src.infrastructure.persistence.settings_repository import SettingsRepository

from ..core.deps import get_current_user, get_db

router = APIRouter()


class TradeMetrics(BaseModel):
    """Dashboard metrics for trading performance"""

    total_trades: int
    profitable_trades: int
    losing_trades: int
    win_rate: float  # percentage (0-100)
    average_profit_per_trade: float
    best_trade_profit: float | None
    worst_trade_loss: float | None
    total_realized_pnl: float
    best_trade_symbol: str | None
    worst_trade_symbol: str | None
    days_traded: int
    avg_holding_period_days: float


@router.get("/dashboard/metrics", response_model=TradeMetrics)
def get_dashboard_metrics(
    period_days: int = Query(default=30, ge=1, le=365),
    trade_mode: str | None = Query(default=None),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Get dashboard metrics for the current user.

    Args:
        period_days: Number of days to look back (default: 30)
        trade_mode: Filter by trade mode ('paper' or 'broker'). If None, includes all.

    Returns:
        TradeMetrics with trading performance statistics
    """
    try:
        settings_repo = SettingsRepository(db)
        settings = settings_repo.ensure_default(current.id)

        # Parse trade_mode if provided
        mode = None
        if trade_mode:
            try:
                mode = TradeMode(trade_mode.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid trade_mode: {trade_mode}. Must be 'paper' or 'broker'",
                ) from None

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        # Query closed positions within the date range
        stmt = select(Positions).where(
            Positions.user_id == current.id,
            Positions.closed_at.isnot(None),
            Positions.closed_at >= start_date,
            Positions.closed_at <= end_date,
        )

        positions = list(db.execute(stmt).scalars().all())

        if mode:
            # Filter by trade mode by checking buy order
            filtered_positions = []
            for pos in positions:
                if pos.buy_order_id:
                    buy_order = db.query(Orders).filter(Orders.id == pos.buy_order_id).first()
                    if buy_order and buy_order.trade_mode == mode:
                        filtered_positions.append(pos)
            positions = filtered_positions

        # Calculate metrics
        total_trades = len(positions)

        if total_trades == 0:
            return TradeMetrics(
                total_trades=0,
                profitable_trades=0,
                losing_trades=0,
                win_rate=0.0,
                average_profit_per_trade=0.0,
                best_trade_profit=None,
                worst_trade_loss=None,
                total_realized_pnl=0.0,
                best_trade_symbol=None,
                worst_trade_symbol=None,
                days_traded=0,
                avg_holding_period_days=0.0,
            )

        # Calculate P&L metrics
        profitable_trades = sum(1 for p in positions if (p.realized_pnl or 0) > 0)
        losing_trades = sum(1 for p in positions if (p.realized_pnl or 0) < 0)
        total_profit = sum(p.realized_pnl for p in positions if (p.realized_pnl or 0) > 0)
        total_loss = sum(p.realized_pnl for p in positions if (p.realized_pnl or 0) < 0)
        total_realized_pnl = sum(p.realized_pnl or 0 for p in positions)

        # Find best and worst trades
        best_trade = max(
            (p for p in positions if (p.realized_pnl or 0) > 0),
            key=lambda p: p.realized_pnl,
            default=None,
        )
        worst_trade = min(
            (p for p in positions if (p.realized_pnl or 0) < 0),
            key=lambda p: p.realized_pnl,
            default=None,
        )

        # Calculate holding period
        holding_periods = []
        for pos in positions:
            if pos.opened_at and pos.closed_at:
                period = (pos.closed_at - pos.opened_at).days
                holding_periods.append(period)

        avg_holding_days = sum(holding_periods) / len(holding_periods) if holding_periods else 0.0

        # Calculate unique trading days
        trading_dates = set()
        for pos in positions:
            if pos.closed_at:
                trading_dates.add(pos.closed_at.date())

        # Calculate metrics
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0.0
        avg_profit_per_trade = (
            total_profit / profitable_trades if profitable_trades > 0 else 0.0
        )

        return TradeMetrics(
            total_trades=total_trades,
            profitable_trades=profitable_trades,
            losing_trades=losing_trades,
            win_rate=round(win_rate, 2),
            average_profit_per_trade=round(avg_profit_per_trade, 2),
            best_trade_profit=round(best_trade.realized_pnl, 2) if best_trade else None,
            worst_trade_loss=round(worst_trade.realized_pnl, 2) if worst_trade else None,
            total_realized_pnl=round(total_realized_pnl, 2),
            best_trade_symbol=best_trade.symbol if best_trade else None,
            worst_trade_symbol=worst_trade.symbol if worst_trade else None,
            days_traded=len(trading_dates),
            avg_holding_period_days=round(avg_holding_days, 2),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to calculate metrics: {str(e)}"
        ) from e


@router.get("/dashboard/metrics/daily", response_model=dict)
def get_daily_metrics(
    date_str: str | None = Query(default=None),
    trade_mode: str | None = Query(default=None),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Get metrics for a specific day.

    Args:
        date_str: Date in YYYY-MM-DD format (defaults to today)
        trade_mode: Filter by trade mode ('paper' or 'broker'). If None, includes all.

    Returns:
        Daily metrics including trades executed and P&L for that day
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()

        settings_repo = SettingsRepository(db)
        settings = settings_repo.ensure_default(current.id)

        # Parse trade_mode if provided
        mode = None
        if trade_mode:
            try:
                mode = TradeMode(trade_mode.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid trade_mode: {trade_mode}. Must be 'paper' or 'broker'",
                ) from None

        # Query closed positions for the specific day
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())

        stmt = select(Positions).where(
            Positions.user_id == current.id,
            Positions.closed_at.isnot(None),
            Positions.closed_at >= start_datetime,
            Positions.closed_at <= end_datetime,
        )

        positions = list(db.execute(stmt).scalars().all())

        if mode:
            # Filter by trade mode
            filtered_positions = []
            for pos in positions:
                if pos.buy_order_id:
                    buy_order = db.query(Orders).filter(Orders.id == pos.buy_order_id).first()
                    if buy_order and buy_order.trade_mode == mode:
                        filtered_positions.append(pos)
            positions = filtered_positions

        # Calculate daily metrics
        daily_trades = len(positions)
        profitable_count = sum(1 for p in positions if (p.realized_pnl or 0) > 0)
        daily_pnl = sum(p.realized_pnl or 0 for p in positions)
        win_rate = (profitable_count / daily_trades * 100) if daily_trades > 0 else 0.0

        return {
            "date": target_date.isoformat(),
            "trades": daily_trades,
            "profitable_trades": profitable_count,
            "losing_trades": daily_trades - profitable_count,
            "daily_pnl": round(daily_pnl, 2),
            "win_rate": round(win_rate, 2),
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD") from None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to calculate daily metrics: {str(e)}"
        ) from e


class ConnectionPoolStatus(BaseModel):
    """Database connection pool health status"""

    pool_size: int
    checked_in: int
    checked_out: int
    overflow: int
    max_overflow: int
    total_connections: int
    utilization_percent: float
    is_healthy: bool
    health_message: str


@router.get("/system/db-pool", response_model=ConnectionPoolStatus)
def get_db_connection_pool_status(
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Get database connection pool status and health metrics.

    Requires authentication. Returns current pool utilization and health status.

    Returns:
        ConnectionPoolStatus with pool metrics and health status
    """
    try:
        # Get pool status
        status = get_pool_status(engine)

        # Check pool health
        is_healthy, health_message = check_pool_health(engine)

        return ConnectionPoolStatus(
            pool_size=status["pool_size"],
            checked_in=status["checked_in"],
            checked_out=status["checked_out"],
            overflow=status["overflow"],
            max_overflow=status["max_overflow"],
            total_connections=status["total_connections"],
            utilization_percent=status["utilization_percent"],
            is_healthy=is_healthy,
            health_message=health_message,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get pool status: {str(e)}"
        ) from e
