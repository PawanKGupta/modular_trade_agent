from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Annotated

# ruff: noqa: B008
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Positions, TradeMode, Users
from src.infrastructure.persistence.orders_repository import OrdersRepository
from src.infrastructure.persistence.pnl_audit_repository import PnlAuditRepository
from src.infrastructure.persistence.pnl_repository import PnlRepository
from src.infrastructure.persistence.positions_repository import PositionsRepository

from ..core.deps import get_current_user, get_db
from ..schemas.pnl import ClosedPositionDetail, DailyPnl, PaginatedClosedPositions, PnlSummary
from ..services.pnl_calculation_service import PnlCalculationService

try:
    from utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

router = APIRouter()


def _get_paper_trading_account_data(user_id: int) -> dict | None:
    """Fetch current account P&L from paper trading store."""
    try:
        import json
        from pathlib import Path

        store_path = Path(f"paper_trading/user_{user_id}/account.json")
        if store_path.exists():
            with open(store_path) as f:
                return json.load(f)
    except Exception as e:
        logger.debug(f"Could not load paper trading account data for user {user_id}: {e}")
    return None


def _calculate_portfolio_unrealized_pnl(user_id: int) -> float:
    """Calculate current unrealized P&L from holdings using live prices (matching portfolio calculation)."""
    try:
        import json
        from pathlib import Path

        import yfinance as yf

        store_path = Path(f"paper_trading/user_{user_id}")
        holdings_file = store_path / "holdings.json"

        if not holdings_file.exists():
            return 0.0

        with open(holdings_file) as f:
            holdings_data = json.load(f)

        unrealized_pnl_total = 0.0

        for symbol, holding in holdings_data.items():
            qty = holding.get("quantity", 0)
            avg_price = float(holding.get("average_price", 0))

            # Try to fetch live price
            try:
                ticker = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
                stock = yf.Ticker(ticker)
                live_price = stock.info.get("currentPrice") or stock.info.get("regularMarketPrice")
                current_price = (
                    float(live_price) if live_price else float(holding.get("current_price", 0))
                )
            except Exception:
                current_price = float(holding.get("current_price", 0))

            cost_basis = qty * avg_price
            market_value = qty * current_price
            pnl = market_value - cost_basis
            unrealized_pnl_total += pnl

        return unrealized_pnl_total
    except Exception as e:
        logger.debug(f"Could not calculate unrealized P&L for user {user_id}: {e}")
        return 0.0


def _ensure_pnl_records(user_id: int, start: date, end: date, db: Session):
    """Populate PnL if missing by looking at earliest order date and calculating entire range."""
    repo = PnlRepository(db)

    # Get earliest order date
    orders_repo = OrdersRepository(db)
    orders = orders_repo.list(user_id)
    order_dates = [o.placed_at.date() for o in orders if getattr(o, "placed_at", None)]

    if not order_dates:
        # No orders at all; return empty
        return []

    # Calculate from earliest order date or the requested start, whichever is earlier
    calc_start = min(min(order_dates), start)

    # Always run backfill to ensure full coverage (upsert handles duplicates)
    service = PnlCalculationService(db)
    service.calculate_date_range(user_id, calc_start, end)

    # Now fetch the range
    return repo.range(user_id, start, end)


def _compute_closed_trade_stats(user_id: int, db: Session, trade_mode: TradeMode | None):
    """Compute realized P&L stats from closed positions (trade-level).

    Returns: (total_realized, trades_green, trades_red, min_pnl, max_pnl, avg_pnl)
    """
    # Fetch closed positions for user
    qry = db.query(Positions).filter(
        Positions.user_id == user_id, Positions.closed_at != None
    )  # noqa: E711
    positions = qry.all()

    pnls: list[float] = []

    # Optional trade_mode filter by matching the buy order
    orders_repo = OrdersRepository(db)

    for pos in positions:
        if trade_mode is not None:
            buy_order = None
            try:
                # Reuse service helper logic inline: find a BUY order near opened_at
                orders = orders_repo.list(user_id)
                for order in orders:
                    if (
                        order.symbol == pos.symbol
                        and order.side == "buy"
                        and order.placed_at
                        and pos.opened_at
                        and abs((order.placed_at - pos.opened_at).total_seconds()) < 3600
                    ):
                        buy_order = order
                        break
            except Exception:
                buy_order = None

            if not buy_order or (getattr(buy_order, "trade_mode", None) != trade_mode):
                continue

        pnl_val: float | None = None

        # Prefer realized_pnl stored on position
        if pos.realized_pnl is not None:
            try:
                pnl_val = float(pos.realized_pnl)
            except Exception:
                pnl_val = None
        # Fallback: derive from exit_price and sold quantity if available
        if pnl_val is None and pos.exit_price is not None and pos.avg_price is not None:
            sold_qty = 0.0
            if pos.sell_order_id:
                try:
                    sell_order = orders_repo.get(pos.sell_order_id)
                    if sell_order:
                        sold_qty = float(
                            getattr(sell_order, "execution_qty", None) or sell_order.quantity or 0.0
                        )
                except Exception:
                    sold_qty = 0.0
            if sold_qty > 0:
                pnl_val = (float(pos.exit_price) - float(pos.avg_price)) * sold_qty

        if pnl_val is None:
            # Skip if we cannot determine realized for this trade
            continue

        pnls.append(pnl_val)

    trades_green = sum(1 for x in pnls if x >= 0)
    trades_red = sum(1 for x in pnls if x < 0)
    total_realized = sum(pnls) if pnls else 0.0
    min_pnl = min(pnls) if pnls else 0.0
    max_pnl = max(pnls) if pnls else 0.0
    avg_pnl = (total_realized / len(pnls)) if pnls else 0.0

    # If no DB trades found, try paper-trading transactions.json fallback (SELL entries)
    if not pnls:
        closed_pnls = _load_paper_trading_closed_trade_pnls(user_id)
        if closed_pnls:
            pnls = closed_pnls
            trades_green = sum(1 for x in pnls if x >= 0)
            trades_red = sum(1 for x in pnls if x < 0)
            total_realized = sum(pnls)
            min_pnl = min(pnls)
            max_pnl = max(pnls)
            avg_pnl = (total_realized / len(pnls)) if pnls else 0.0

    return total_realized, trades_green, trades_red, min_pnl, max_pnl, avg_pnl


def _calculate_unrealized_from_open_positions(
    user_id: int, db: Session, trade_mode: TradeMode | None
) -> float:
    """Compute unrealized P&L from open positions using live prices via yfinance.

    Falls back to 0 if live price unavailable. Assumes NSE symbols by default.
    """
    try:
        import yfinance as yf  # noqa: PLC0415

        qry = db.query(Positions).filter(
            Positions.user_id == user_id, Positions.closed_at == None
        )  # noqa: E711
        positions = qry.all()

        orders_repo = OrdersRepository(db)
        total_unrealized = 0.0

        for pos in positions:
            # Optional trade_mode filter
            if trade_mode is not None:
                buy_order = None
                try:
                    orders = orders_repo.list(user_id)
                    for order in orders:
                        if (
                            order.symbol == pos.symbol
                            and order.side == "buy"
                            and order.placed_at
                            and pos.opened_at
                            and abs((order.placed_at - pos.opened_at).total_seconds()) < 3600
                        ):
                            buy_order = order
                            break
                except Exception:
                    buy_order = None

                if not buy_order or (getattr(buy_order, "trade_mode", None) != trade_mode):
                    continue

            qty = float(pos.quantity or 0.0)
            avg_price = float(pos.avg_price or 0.0)

            # Fetch live price; assume NSE suffix if missing
            symbol = pos.symbol or ""
            ticker = f"{symbol}.NS" if symbol and not symbol.endswith((".NS", ".BO")) else symbol
            try:
                stock = yf.Ticker(ticker)
                live_price = stock.info.get("currentPrice") or stock.info.get("regularMarketPrice")
                current_price = float(live_price) if live_price else avg_price
            except Exception:
                current_price = avg_price

            total_unrealized += qty * (current_price - avg_price)

        return total_unrealized
    except Exception as e:
        logger.debug(f"Could not calculate unrealized from positions for user {user_id}: {e}")
        return 0.0


def _load_paper_trading_closed_trade_pnls(user_id: int) -> list[float]:
    """Fallback: Load realized PnL of closed trades from paper_trading transactions.json (SELL entries)."""
    try:
        import json
        from pathlib import Path

        tx_file = Path(f"paper_trading/user_{user_id}/transactions.json")
        if not tx_file.exists():
            return []
        with open(tx_file) as f:
            tx = json.load(f)
        pnls: list[float] = []
        for t in tx:
            if t.get("transaction_type") == "SELL":
                pnl = float(t.get("realized_pnl", 0.0) or 0.0)
                pnls.append(pnl)
        return pnls
    except Exception:
        return []


@router.get("/daily", response_model=list[DailyPnl])
def daily_pnl(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    trade_mode: str | None = Query(default=None, description="Filter by 'paper' or 'broker'"),
    include_unrealized: bool = Query(
        default=False, description="Include open trades on current day"
    ),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    # default to last 30 days
    end = end or date.today()
    start = start or (end - timedelta(days=30))

    # Parse trade_mode if provided (only process if it's a string)
    mode: TradeMode | None = None
    if trade_mode and isinstance(trade_mode, str):
        try:
            mode = TradeMode(trade_mode.lower())
        except Exception:
            raise HTTPException(
                status_code=400, detail="Invalid trade_mode. Use 'paper' or 'broker'."
            )

    # First, try to get from PnlDaily table (more efficient if already calculated)
    pnl_repo = PnlRepository(db)
    pnl_records = pnl_repo.range(current.id, start, end)

    # Get closed positions for the date range to extract symbols and trade counts
    positions_repo = PositionsRepository(db)
    closed_positions_qry = db.query(Positions).filter(
        Positions.user_id == current.id,
        Positions.closed_at.isnot(None),  # noqa: E711
    )
    # Filter by date range
    start_datetime = datetime.combine(start, datetime.min.time())
    end_datetime = datetime.combine(end, datetime.max.time())
    closed_positions_qry = closed_positions_qry.filter(
        Positions.closed_at >= start_datetime,
        Positions.closed_at <= end_datetime,
    )

    # Optional trade_mode filter
    if mode is not None:
        orders_repo = OrdersRepository(db)
        all_orders = orders_repo.list(current.id)[0]  # Returns (orders, count)
        buy_order_symbols = {
            order.symbol
            for order in all_orders
            if order.side == "buy" and getattr(order, "trade_mode", None) == mode
        }
        closed_positions_qry = closed_positions_qry.filter(Positions.symbol.in_(buy_order_symbols))

    closed_positions = closed_positions_qry.all()

    # Group closed positions by date
    symbols_by_date: dict[date, list[str]] = defaultdict(list)
    trades_count_by_date: dict[date, int] = defaultdict(int)
    for pos in closed_positions:
        if pos.closed_at:
            closed_date = pos.closed_at.date()
            if closed_date >= start and closed_date <= end:
                symbols_by_date[closed_date].append(pos.symbol)
                trades_count_by_date[closed_date] += 1

    series: list[DailyPnl] = []

    # If we have PnlDaily records, use them (includes realized + unrealized - fees)
    if pnl_records:
        for record in pnl_records:
            # Calculate total PnL: realized + unrealized - fees
            total_pnl = (
                (record.realized_pnl or 0.0) + (record.unrealized_pnl or 0.0) - (record.fees or 0.0)
            )
            # Get unique symbols for this date
            symbols_list = list(set(symbols_by_date.get(record.date, [])))
            series.append(
                DailyPnl(
                    date=record.date,
                    pnl=round(float(total_pnl), 2),
                    realized_pnl=round(float(record.realized_pnl or 0.0), 2),
                    unrealized_pnl=round(float(record.unrealized_pnl or 0.0), 2),
                    fees=round(float(record.fees or 0.0), 2),
                    trades_count=trades_count_by_date.get(record.date, 0),
                    symbols=symbols_list if symbols_list else None,
                )
            )
    else:
        # Fallback: calculate from positions dynamically
        service = PnlCalculationService(db)
        realized_by_date = service.calculate_realized_pnl(current.id, mode, None)

        # Filter by requested range and build daily series from DB closed trades
        for d, val in realized_by_date.items():
            if d >= start and d <= end:
                symbols_list = list(set(symbols_by_date.get(d, [])))
                series.append(
                    DailyPnl(
                        date=d,
                        pnl=round(float(val or 0.0), 2),
                        realized_pnl=round(float(val or 0.0), 2),
                        unrealized_pnl=None,
                        fees=None,
                        trades_count=trades_count_by_date.get(d, 0),
                        symbols=symbols_list if symbols_list else None,
                    )
                )

    # Fallback: if DB has no realized data, derive from paper-trading transactions SELL entries
    if len(series) == 0:
        try:
            import json
            from pathlib import Path

            tx_file = Path(f"paper_trading/user_{current.id}/transactions.json")
            if tx_file.exists():
                with open(tx_file) as f:
                    tx = json.load(f)
                daily_map: dict[date, float] = {}
                for t in tx:
                    if t.get("transaction_type") == "SELL":
                        ts = t.get("timestamp")
                        pnl = float(t.get("realized_pnl", 0.0) or 0.0)
                        if ts:
                            from datetime import datetime as dt

                            day = dt.fromisoformat(ts.replace("Z", "+00:00")).date()
                            if day >= start and day <= end:
                                daily_map[day] = daily_map.get(day, 0.0) + pnl
                for d, val in sorted(daily_map.items()):
                    symbols_list = list(set(symbols_by_date.get(d, [])))
                    series.append(
                        DailyPnl(
                            date=d,
                            pnl=round(val, 2),
                            realized_pnl=round(val, 2),
                            unrealized_pnl=None,
                            fees=None,
                            trades_count=trades_count_by_date.get(d, 0),
                            symbols=symbols_list if symbols_list else None,
                        )
                    )
        except Exception:
            pass

    # Optionally include today's unrealized from open positions by adding to today's bucket
    if include_unrealized:
        today = date.today()
        if today >= start and today <= end:
            unrealized_today = _calculate_unrealized_from_open_positions(current.id, db, mode)
            # Find existing today's entry or append new
            found = False
            for i, item in enumerate(series):
                if item.date == today:
                    new_pnl = item.pnl + unrealized_today
                    series[i] = DailyPnl(
                        date=today,
                        pnl=round(new_pnl, 2),
                        realized_pnl=item.realized_pnl,
                        unrealized_pnl=round(unrealized_today, 2) if unrealized_today else item.unrealized_pnl,
                        fees=item.fees,
                        trades_count=item.trades_count,
                        symbols=item.symbols,
                    )
                    found = True
                    break
            if not found:
                series.append(
                    DailyPnl(
                        date=today,
                        pnl=round(unrealized_today, 2),
                        realized_pnl=None,
                        unrealized_pnl=round(unrealized_today, 2),
                        fees=None,
                        trades_count=0,
                        symbols=None,
                    )
                )

    # Sort by date ascending for chart consistency
    series.sort(key=lambda x: x.date)
    return series


@router.get("/summary", response_model=PnlSummary)
def pnl_summary(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    trade_mode: str | None = Query(default=None, description="Filter by 'paper' or 'broker'"),
    include_unrealized: bool = Query(
        default=False, description="Include open trades with live prices"
    ),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    end = end or date.today()
    start = start or (end - timedelta(days=30))

    # Parse trade_mode if provided (only process if it's a string)
    mode: TradeMode | None = None
    if trade_mode and isinstance(trade_mode, str):
        try:
            mode = TradeMode(trade_mode.lower())
        except Exception:
            raise HTTPException(
                status_code=400, detail="Invalid trade_mode. Use 'paper' or 'broker'."
            )

    # Compute trade-level stats from positions
    (
        total_realized,
        trades_green,
        trades_red,
        min_trade_pnl,
        max_trade_pnl,
        avg_trade_pnl,
    ) = _compute_closed_trade_stats(current.id, db, mode)

    # Compute unrealized from open positions if requested
    total_unrealized = 0.0
    if include_unrealized:
        total_unrealized = _calculate_unrealized_from_open_positions(current.id, db, mode)

    total = total_realized + total_unrealized

    # Fallback: if DB has no trades, use paper trading store to avoid blank UI
    if total_realized == 0.0 and trades_green == 0 and trades_red == 0:
        account_data = _get_paper_trading_account_data(current.id)
        if account_data:
            realized = float(account_data.get("realized_pnl", 0.0) or 0.0)
            unrealized = (
                _calculate_portfolio_unrealized_pnl(current.id) if include_unrealized else 0.0
            )
            total_realized = realized
            total_unrealized = unrealized
            total = realized + unrealized
            # Map to one pseudo-trade for counts if needed
            trades_green = 1 if total >= 0 else 0
            trades_red = 0 if total >= 0 else 1
            min_trade_pnl = total
            max_trade_pnl = total
            avg_trade_pnl = total
            logger.info(
                f"User {current.id}: PnL summary fallback using portfolio-style (realized={realized}, unrealized={unrealized})"
            )

    # Build response, mapping daysGreen/Red to trade counts per expectation
    return PnlSummary(
        totalPnl=round(total, 2),
        totalRealizedPnl=round(total_realized, 2),
        totalUnrealizedPnl=round(total_unrealized, 2),
        tradesGreen=trades_green,
        tradesRed=trades_red,
        minTradePnl=round(min_trade_pnl, 2),
        maxTradePnl=round(max_trade_pnl, 2),
        avgTradePnl=round(avg_trade_pnl, 2),
        daysGreen=trades_green,
        daysRed=trades_red,
    )


@router.get("/audit-history", response_model=list[dict])
def audit_history(
    limit: int = Query(default=50, ge=1, le=500),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Get P&L calculation audit history for the current user (Phase 0.5).

    Returns list of calculation audit records showing when calculations were run,
    their status, performance metrics, and results.
    """
    try:
        audit_repo = PnlAuditRepository(db)

        if status:
            audits = audit_repo.get_by_status(current.id, status, limit=limit)
        else:
            audits = audit_repo.get_by_user(current.id, limit=limit)

        # Convert to dict for response
        return [
            {
                "id": audit.id,
                "calculation_type": audit.calculation_type,
                "date_range_start": (
                    audit.date_range_start.isoformat() if audit.date_range_start else None
                ),
                "date_range_end": (
                    audit.date_range_end.isoformat() if audit.date_range_end else None
                ),
                "positions_processed": audit.positions_processed,
                "orders_processed": audit.orders_processed,
                "pnl_records_created": audit.pnl_records_created,
                "pnl_records_updated": audit.pnl_records_updated,
                "duration_seconds": audit.duration_seconds,
                "status": audit.status,
                "error_message": audit.error_message,
                "triggered_by": audit.triggered_by,
                "created_at": audit.created_at.isoformat(),
            }
            for audit in audits
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch audit history: {str(e)}"
        ) from e


@router.post("/calculate")
def calculate_pnl(
    target_date: date | None = Query(default=None),
    trade_mode: str | None = Query(default=None),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Trigger on-demand P&L calculation for a specific date or today.

    Args:
        target_date: Date to calculate P&L for (defaults to today)
        trade_mode: Filter by trade mode ('paper' or 'broker'). If None, includes all.

    Returns:
        Calculated PnlDaily record
    """
    try:
        service = PnlCalculationService(db)
        calculation_date = target_date or date.today()

        # Parse trade_mode if provided (only process if it's a string)
        mode = None
        if trade_mode and isinstance(trade_mode, str):
            try:
                mode = TradeMode(trade_mode.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid trade_mode: {trade_mode}. Must be 'paper' or 'broker'",
                ) from None

        record = service.calculate_daily_pnl(current.id, calculation_date, mode)

        return {
            "date": record.date.isoformat(),
            "realized_pnl": record.realized_pnl,
            "unrealized_pnl": record.unrealized_pnl,
            "fees": record.fees,
            "total_pnl": record.realized_pnl + record.unrealized_pnl - record.fees,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate P&L: {str(e)}") from e


@router.post("/backfill")
def backfill_pnl(
    start_date: date = Query(...),
    end_date: date = Query(...),
    trade_mode: str | None = Query(default=None),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Backfill historical P&L data for a date range.

    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        trade_mode: Filter by trade mode ('paper' or 'broker'). If None, includes all.

    Returns:
        Summary of backfill operation
    """
    try:
        # Validate date range
        if start_date > end_date:
            raise HTTPException(status_code=400, detail="start_date must be <= end_date")

        # Limit to 1 year at a time to prevent long-running operations
        max_days = 365
        if (end_date - start_date).days > max_days:
            raise HTTPException(
                status_code=400,
                detail=f"Date range cannot exceed {max_days} days. Please split into smaller ranges.",
            )

        service = PnlCalculationService(db)

        # Parse trade_mode if provided (only process if it's a string)
        mode = None
        if trade_mode and isinstance(trade_mode, str):
            try:
                mode = TradeMode(trade_mode.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid trade_mode: {trade_mode}. Must be 'paper' or 'broker'",
                ) from None

        records = service.calculate_date_range(current.id, start_date, end_date, mode)

        return {
            "message": "Backfill completed successfully",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "records_created": len(records),
            "trade_mode": trade_mode,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to backfill P&L: {str(e)}") from e


def _get_stock_name(symbol: str) -> str | None:
    """Get stock name from yfinance for display purposes."""
    try:
        import yfinance as yf  # noqa: PLC0415

        # Remove broker suffixes like -EQ, -BE for ticker lookup
        base_symbol = symbol.split("-")[0] if "-" in symbol else symbol
        ticker = f"{base_symbol}.NS"

        stock = yf.Ticker(ticker)
        info = stock.info
        # Try multiple fields for stock name
        name = (
            info.get("longName")
            or info.get("shortName")
            or info.get("name")
            or base_symbol
        )
        return name if name and name != base_symbol else None
    except Exception:
        return None


@router.get("/closed-positions", response_model=PaginatedClosedPositions)
def get_closed_positions(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 10,
    trade_mode: str | None = Query(default=None, description="Filter by 'paper' or 'broker'"),
    sort_by: str = Query(
        default="closed_at", description="Sort field: closed_at, symbol, realized_pnl, opened_at"
    ),
    sort_order: str = Query(default="desc", description="Sort order: asc or desc"),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Get paginated closed positions with stock names for PnL page.

    Returns closed positions sorted by the specified field with pagination support.
    """
    # Parse trade_mode
    mode: TradeMode | None = None
    if trade_mode and isinstance(trade_mode, str):
        try:
            mode = TradeMode(trade_mode.lower())
        except Exception:
            raise HTTPException(
                status_code=400, detail="Invalid trade_mode. Use 'paper' or 'broker'."
            )

    # Build base query
    qry = db.query(Positions).filter(
        Positions.user_id == current.id,
        Positions.closed_at.isnot(None),  # noqa: E711
    )

    # Filter by trade_mode if specified (match via buy order)
    if mode is not None:
        orders_repo = OrdersRepository(db)
        # Get all buy orders for this user
        all_orders = orders_repo.list(current.id)[0]  # Returns (orders, count)
        buy_order_symbols = {
            order.symbol
            for order in all_orders
            if order.side == "buy" and getattr(order, "trade_mode", None) == mode
        }
        qry = qry.filter(Positions.symbol.in_(buy_order_symbols))

    # Calculate total count before pagination
    total_count = qry.count()

    # Apply sorting
    sort_field_map = {
        "closed_at": Positions.closed_at,
        "opened_at": Positions.opened_at,
        "symbol": Positions.symbol,
        "realized_pnl": Positions.realized_pnl,
    }
    sort_field = sort_field_map.get(sort_by, Positions.closed_at)
    sort_func = desc if sort_order.lower() == "desc" else asc
    qry = qry.order_by(sort_func(sort_field))

    # Apply pagination
    offset = (page - 1) * page_size
    positions = qry.offset(offset).limit(page_size).all()

    # Convert to response models with stock names
    items: list[ClosedPositionDetail] = []
    for pos in positions:
        stock_name = _get_stock_name(pos.symbol)
        items.append(
            ClosedPositionDetail(
                id=pos.id,
                symbol=pos.symbol,
                stock_name=stock_name,
                quantity=float(pos.quantity) if pos.quantity else 0.0,
                avg_price=float(pos.avg_price) if pos.avg_price else 0.0,
                exit_price=float(pos.exit_price) if pos.exit_price else None,
                opened_at=pos.opened_at.isoformat() if pos.opened_at else "",
                closed_at=pos.closed_at.isoformat() if pos.closed_at else "",
                realized_pnl=float(pos.realized_pnl) if pos.realized_pnl is not None else None,
                realized_pnl_pct=float(pos.realized_pnl_pct) if pos.realized_pnl_pct is not None else None,
                exit_reason=pos.exit_reason,
            )
        )

    total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0

    return PaginatedClosedPositions(
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
