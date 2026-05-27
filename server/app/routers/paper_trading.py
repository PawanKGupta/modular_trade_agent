"""
Paper Trading API endpoints
"""

import logging
from datetime import date, datetime
from typing import Annotated, Any

import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from modules.kotak_neo_auto_trader.infrastructure.persistence import PaperTradeStore
from modules.kotak_neo_auto_trader.infrastructure.simulation import PaperTradeReporter
from modules.kotak_neo_auto_trader.services import (
    compute_sell_target,
    get_indicator_service,
    get_price_service,
)
from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_base_symbol
from src.infrastructure.db.models import (
    OrderStatus,
    PnlDaily,
    TradeMode,
    Users,
)
from src.infrastructure.db.models import (
    Positions as PositionsModel,
)
from src.infrastructure.persistence.orders_repository import OrdersRepository
from src.infrastructure.persistence.pnl_repository import PnlRepository
from src.infrastructure.persistence.positions_repository import PositionsRepository
from src.infrastructure.persistence.settings_repository import SettingsRepository
from src.infrastructure.persistence.user_trading_config_repository import (
    UserTradingConfigRepository,
)

from ..core.deps import get_current_user, get_db, require_entitlement
from ..services.pnl_calculation_service import PnlCalculationService

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_entitlement("paper_trading"))])


class PaperTradingAccount(BaseModel):
    initial_capital: float
    available_cash: float
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    portfolio_value: float
    total_value: float
    return_percentage: float


class PaperTradingHolding(BaseModel):
    symbol: str
    quantity: int
    average_price: float
    current_price: float
    cost_basis: float
    market_value: float
    pnl: float
    pnl_percentage: float
    target_price: float | None = None  # Frozen EMA9 target
    distance_to_target: float | None = None  # % to reach target
    reentry_count: int = 0  # Number of re-entries for this position
    reentries: list[dict[str, Any]] | None = None  # Re-entry details array
    entry_rsi: float | None = None  # RSI10 at initial entry
    initial_entry_price: float | None = None  # Initial entry price (before re-entries)


class PaperTradingOrder(BaseModel):
    order_id: str
    symbol: str
    transaction_type: str
    quantity: int
    order_type: str
    status: str
    execution_price: float | None = None
    created_at: str
    executed_at: str | None = None
    metadata: dict[str, Any] | None = None  # Order metadata (entry_type, rsi_level, etc.)


class PaperTradingTransaction(BaseModel):
    order_id: str
    symbol: str
    transaction_type: str  # BUY or SELL
    quantity: int
    price: float
    order_value: float
    charges: float
    timestamp: str


class ClosedPosition(BaseModel):
    symbol: str
    entry_price: float
    exit_price: float
    quantity: int
    buy_date: str
    sell_date: str
    holding_days: int
    realized_pnl: float
    pnl_percentage: float
    charges: float
    slippage: float | None = None  # Difference between expected and executed price (Phase 1)


class TradeHistory(BaseModel):
    transactions: list[PaperTradingTransaction]
    closed_positions: list[ClosedPosition]
    statistics: dict[str, Any]


class PaperTradingPortfolio(BaseModel):
    account: PaperTradingAccount
    holdings: list[PaperTradingHolding]
    recent_orders: list[PaperTradingOrder]
    order_statistics: dict


class PaginatedPaperTradingOrders(BaseModel):
    """Paginated response for paper trading recent orders"""

    items: list[PaperTradingOrder]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedPaperTradingPortfolio(BaseModel):
    """Paginated paper trading portfolio response"""

    account: PaperTradingAccount
    holdings: list[PaperTradingHolding]
    recent_orders: PaginatedPaperTradingOrders
    order_statistics: dict


class PaginatedClosedPositions(BaseModel):
    """Paginated response for closed positions"""

    items: list[ClosedPosition]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedTransactions(BaseModel):
    """Paginated response for transactions"""

    items: list[PaperTradingTransaction]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedTradeHistory(BaseModel):
    """Paginated trade history response"""

    transactions: PaginatedTransactions
    closed_positions: PaginatedClosedPositions
    statistics: dict[str, Any]


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except Exception:
        return None


def _upsert_pnl_from_closed_positions(
    user_id: int, closed_positions: list[ClosedPosition], db: Session
) -> None:
    """Aggregate realized PnL by sell date and upsert PnlDaily records."""
    if not closed_positions:
        return

    try:
        pnl_repo = PnlRepository(db)
        daily_totals: dict[date, dict[str, float]] = {}

        for pos in closed_positions:
            sell_date = _parse_iso_date(pos.sell_date)
            if not sell_date:
                continue

            totals = daily_totals.setdefault(sell_date, {"realized": 0.0, "fees": 0.0})
            totals["realized"] += float(pos.realized_pnl or 0.0)
            totals["fees"] += float(pos.charges or 0.0)

        for day, totals in daily_totals.items():
            record = PnlDaily(
                user_id=user_id,
                date=day,
                realized_pnl=totals["realized"],
                unrealized_pnl=0.0,
                fees=totals["fees"],
            )
            pnl_repo.upsert(record)
    except Exception as e:
        logger.warning(f"Skipping PnL sync from history for user {user_id}: {e}")


def _empty_paginated_portfolio(
    initial_capital: float,
    *,
    page: int,
    page_size: int,
) -> PaginatedPaperTradingPortfolio:
    """Portfolio shell when the user has no paper activity yet."""
    cash = initial_capital
    return PaginatedPaperTradingPortfolio(
        account=PaperTradingAccount(
            initial_capital=initial_capital,
            available_cash=cash,
            total_pnl=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            portfolio_value=0.0,
            total_value=cash,
            return_percentage=0.0,
        ),
        holdings=[],
        recent_orders=PaginatedPaperTradingOrders(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0,
        ),
        order_statistics={
            "total_orders": 0,
            "buy_orders": 0,
            "sell_orders": 0,
            "completed_orders": 0,
            "pending_orders": 0,
            "cancelled_orders": 0,
            "rejected_orders": 0,
            "success_rate": 0.0,
        },
    )


def _get_paper_initial_capital(db: Session, user_id: int) -> float:
    """Configured paper starting balance (DB)."""
    config = UserTradingConfigRepository(db).get_or_create_default(user_id)
    return float(getattr(config, "paper_trading_initial_capital", 0.0) or 0.0)


def _is_paper_position(
    pos: PositionsModel,
    all_orders: list,
    user_settings,
) -> bool:
    """True when a position belongs to paper trading (same rules as open-holdings filter)."""
    for order in all_orders:
        if (
            order.symbol == pos.symbol
            and order.side == "buy"
            and order.placed_at
            and pos.opened_at
            and abs((order.placed_at - pos.opened_at).total_seconds()) < 3600
            and getattr(order, "trade_mode", None) == TradeMode.PAPER
        ):
            return True

    has_broker_order = any(
        o.symbol == pos.symbol
        and o.side == "buy"
        and getattr(o, "trade_mode", None) == TradeMode.BROKER
        for o in all_orders
    )
    if has_broker_order:
        return False

    return bool(user_settings and user_settings.trade_mode == TradeMode.PAPER)


def _sum_paper_realized_pnl(
    db: Session,
    user_id: int,
    all_orders: list,
    user_settings,
) -> float:
    """Sum realized P&L from closed paper positions (DB; matches trade history)."""
    closed_positions = (
        db.query(PositionsModel)
        .filter(
            PositionsModel.user_id == user_id,
            PositionsModel.closed_at.isnot(None),
        )
        .all()
    )
    total = 0.0
    for pos in closed_positions:
        if _is_paper_position(pos, all_orders, user_settings):
            total += float(pos.realized_pnl or 0.0)
    return total


def _derive_available_cash(
    initial_capital: float,
    realized_pnl: float,
    unrealized_pnl: float,
    portfolio_value: float,
) -> float:
    """
    Cash balance implied by DB P&L and open marks.

    Ensures total_value = initial_capital + total_pnl (consistent with trade history).
    """
    return initial_capital + realized_pnl + unrealized_pnl - portfolio_value


@router.get("/portfolio", response_model=PaginatedPaperTradingPortfolio)
def get_paper_trading_portfolio(  # noqa: PLR0915, PLR0912, B008
    page: Annotated[
        int,
        Query(ge=1, description="Page number for recent orders (1-based)"),
    ] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=500, description="Number of recent orders per page"),
    ] = 10,
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """Get paper trading portfolio for the current user (DB-only account metrics)."""
    try:
        if db is None:
            return _empty_paginated_portfolio(0.0, page=page, page_size=page_size)

        settings_repo = SettingsRepository(db)
        user_settings = settings_repo.get_by_user_id(current.id)
        positions_repo = PositionsRepository(db)
        orders_repo = OrdersRepository(db)
        initial_capital = _get_paper_initial_capital(db, current.id)

        all_positions = positions_repo.list(current.id)
        all_orders, _ = orders_repo.list(current.id)
        open_positions = [pos for pos in all_positions if pos.closed_at is None]

        paper_positions = [
            pos
            for pos in open_positions
            if _is_paper_position(pos, all_orders, user_settings)
        ]

        realized_pnl = _sum_paper_realized_pnl(db, current.id, all_orders, user_settings)

        # Fetch live prices using yfinance (broker-agnostic)
        portfolio_value = 0.0
        all_holdings_to_process = list(paper_positions)
        for position in all_holdings_to_process:
            qty = position.quantity or 0
            if qty > 0:
                # Construct ticker from symbol (add .NS if not present)
                symbol = position.symbol
                ticker = (
                    f"{symbol}.NS"
                    if not symbol.endswith(".NS") and not symbol.endswith(".BO")
                    else symbol
                )
                # Remove broker suffixes like -EQ, -BE for ticker lookup
                if "-" in ticker:
                    ticker = ticker.split("-")[0] + ".NS"
                try:
                    stock = yf.Ticker(ticker)
                    live_price = stock.info.get("currentPrice") or stock.info.get(
                        "regularMarketPrice"
                    )
                    current_price = float(live_price) if live_price else position.avg_price or 0.0
                except Exception:
                    # Fallback to avg_price if live fetch fails
                    current_price = position.avg_price or 0.0
                portfolio_value += qty * current_price

        # Load target prices from DATABASE sell orders ONLY (single source of truth)
        # No file fallback - database is the only source for target prices
        target_prices = {}
        try:
            active_sell_orders, _ = orders_repo.list(
                current.id,
                side="sell",
                status=[OrderStatus.PENDING, OrderStatus.ONGOING],
            )
            for order in active_sell_orders:
                if order.price and order.price > 0:
                    symbol = order.symbol
                    base_symbol = extract_base_symbol(symbol).upper()
                    if symbol not in target_prices:
                        target_prices[symbol] = float(order.price)
                    if base_symbol not in target_prices:
                        target_prices[base_symbol] = float(order.price)
                    logger.debug(
                        f"Loaded target from DB sell order: {symbol} "
                        f"(base: {base_symbol}) = {order.price}"
                    )
        except Exception as e:
            logger.debug(f"Could not load target prices from database: {e}")

        # Helper function to get live price
        def get_live_price(symbol: str) -> float | None:
            """Fetch live price for a symbol using yfinance"""
            try:
                ticker = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
                stock = yf.Ticker(ticker)
                price = stock.info.get("currentPrice") or stock.info.get("regularMarketPrice")
                return float(price) if price else None
            except Exception as e:
                logger.debug(f"Failed to fetch live price for {symbol}: {e}")
                return None

        # Calculate target prices on-the-fly if not available (same realtime EMA9 as broker/paper)
        _paper_price_service = get_price_service(live_price_manager=None, enable_caching=True)
        _paper_indicator_service = get_indicator_service(
            price_service=_paper_price_service, enable_caching=True
        )

        def calculate_ema9_target(symbol: str) -> float | None:
            """Realtime EMA9 sell target (Yahoo LTP; no Kotak required)."""
            try:
                base = extract_base_symbol(symbol).upper()
                ticker = f"{base}.NS"
                broker_symbol = symbol if "-" in symbol else f"{base}-EQ"
                return compute_sell_target(
                    ticker,
                    broker_symbol=broker_symbol,
                    indicator_service=_paper_indicator_service,
                    price_service=_paper_price_service,
                    live_price_manager=None,
                    exchange="NSE",
                    round_price=True,
                )
            except Exception as e:
                logger.debug(f"Failed to calculate EMA9 for {symbol}: {e}")
                return None

        # Holdings (calculate unrealized P&L with live prices) - from database
        holdings = []
        unrealized_pnl_total = 0.0

        # DB positions are the single source of truth
        all_holdings_for_display = sorted(
            list(paper_positions),
            key=lambda p: p.symbol,
        )
        for position in all_holdings_for_display:
            symbol = position.symbol
            qty = position.quantity or 0
            avg_price = position.avg_price or 0.0

            # Skip positions with zero quantity
            if qty <= 0:
                continue

            # Construct ticker for price lookup (add .NS if not present)
            ticker = symbol
            if not ticker.endswith(".NS") and not ticker.endswith(".BO"):
                # Remove broker suffixes like -EQ, -BE for ticker lookup
                base_symbol = symbol.split("-")[0] if "-" in symbol else symbol
                ticker = f"{base_symbol}.NS"
            # Remove broker suffixes from existing ticker
            elif "-" in ticker:
                base_symbol = ticker.split("-")[0]
                if base_symbol.endswith(".NS") or base_symbol.endswith(".BO"):
                    ticker = base_symbol
                else:
                    ticker = f"{base_symbol}.NS"

            # Fetch live price, fallback to avg_price if fetch fails
            current_price = get_live_price(symbol.split("-")[0] if "-" in symbol else symbol)
            if current_price is None:
                current_price = avg_price
                logger.debug(f"Using avg_price for {symbol}: {current_price}")

            cost_basis = qty * avg_price
            market_value = qty * current_price
            pnl = market_value - cost_basis
            # P&L percentage: calculate based on price change
            if avg_price > 0:
                pnl_pct = (current_price - avg_price) / avg_price * 100
            else:
                pnl_pct = 0.0

            # Accumulate unrealized P&L
            unrealized_pnl_total += pnl

            # Get target price (frozen EMA9) from database sell order if available
            # Try both full symbol and base symbol for target price lookup
            base_symbol_for_target = symbol.split("-")[0] if "-" in symbol else symbol
            target_price = target_prices.get(symbol)  # Try full symbol first
            if target_price is None:
                target_price = target_prices.get(base_symbol_for_target)  # Try base symbol

            # ONLY calculate EMA9 if NO sell order exists (don't recalculate if order exists)
            if target_price is None:
                # Calculate on-the-fly only if no sell order placed yet
                target_price = calculate_ema9_target(base_symbol_for_target)
                logger.debug(
                    f"Calculated EMA9 target for {base_symbol_for_target} (no sell order found): {target_price}"
                )

            distance_to_target = None
            if target_price and current_price > 0:
                distance_to_target = (target_price - current_price) / current_price * 100

            # Get reentry details from position (already loaded from database)
            reentry_count = position.reentry_count or 0
            entry_rsi = position.entry_rsi
            initial_entry_price = position.initial_entry_price

            # Parse reentries JSON field
            reentries_list = None
            if position.reentries:
                if isinstance(position.reentries, dict):
                    # New format: {"reentries": [...], "current_cycle": ...}
                    reentries_list = position.reentries.get("reentries", [])
                elif isinstance(position.reentries, list):
                    # Old format: direct array
                    reentries_list = position.reentries
                else:
                    reentries_list = []
            else:
                reentries_list = []

            holdings.append(
                PaperTradingHolding(
                    symbol=symbol,
                    quantity=qty,
                    average_price=avg_price,
                    current_price=current_price,
                    cost_basis=cost_basis,
                    market_value=market_value,
                    pnl=pnl,
                    pnl_percentage=pnl_pct,
                    target_price=target_price,
                    distance_to_target=distance_to_target,
                    reentry_count=reentry_count,
                    reentries=reentries_list,
                    entry_rsi=entry_rsi,
                    initial_entry_price=initial_entry_price,
                )
            )

        total_pnl = realized_pnl + unrealized_pnl_total
        available_cash = _derive_available_cash(
            initial_capital, realized_pnl, unrealized_pnl_total, portfolio_value
        )
        total_value = available_cash + portfolio_value
        return_pct = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0.0

        account = PaperTradingAccount(
            initial_capital=initial_capital,
            available_cash=available_cash,
            total_pnl=total_pnl,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl_total,
            portfolio_value=portfolio_value,
            total_value=total_value,
            return_percentage=return_pct,
        )

        # Recent orders - read from database (with pagination)
        try:
            all_orders, _ = orders_repo.list(user_id=current.id)

            # Filter for paper trading orders and sort by placed_at descending
            db_orders = [
                o
                for o in all_orders
                if hasattr(o, "trade_mode") and o.trade_mode and o.trade_mode == TradeMode.PAPER
            ]
            db_orders.sort(key=lambda o: o.placed_at if o.placed_at else datetime.min, reverse=True)

            # Apply pagination
            total_orders_count = len(db_orders)
            offset = (page - 1) * page_size
            paginated_orders = db_orders[offset : offset + page_size]
            total_pages = (
                (total_orders_count + page_size - 1) // page_size if total_orders_count > 0 else 0
            )
        except Exception as e:
            logger.error(f"Error fetching orders from database: {e}", exc_info=True)
            paginated_orders = []
            all_orders = []
            total_orders_count = 0
            total_pages = 0

        recent_orders = []
        for db_order in paginated_orders:
            try:
                # Map database status to UI status
                status_map = {
                    "pending": "OPEN",  # PENDING orders shown as OPEN in UI
                    "ongoing": "OPEN",  # ONGOING orders shown as OPEN in UI
                    "closed": "COMPLETE",
                    "cancelled": "CANCELLED",
                    "failed": "FAILED",
                }
                status_value = (
                    db_order.status.value.lower()
                    if hasattr(db_order.status, "value")
                    else str(db_order.status).lower()
                )
                ui_status = status_map.get(status_value, status_value.upper())

                # Get execution price (avg_price if executed, price if pending)
                execution_price = db_order.avg_price if db_order.avg_price else db_order.price

                recent_orders.append(
                    PaperTradingOrder(
                        order_id=db_order.broker_order_id or db_order.order_id or "",
                        symbol=db_order.symbol or "",
                        transaction_type=(
                            db_order.side.upper() if db_order.side else "BUY"
                        ),  # 'buy' or 'sell' -> 'BUY' or 'SELL'
                        quantity=int(db_order.quantity) if db_order.quantity else 0,
                        order_type=(
                            db_order.order_type.upper() if db_order.order_type else "MARKET"
                        ),  # 'market' or 'limit' -> 'MARKET' or 'LIMIT'
                        status=ui_status,
                        execution_price=execution_price,
                        created_at=db_order.placed_at.isoformat() if db_order.placed_at else "",
                        executed_at=db_order.filled_at.isoformat() if db_order.filled_at else None,
                        metadata=getattr(db_order, "order_metadata", None)
                        or getattr(db_order, "metadata", None),  # Include order metadata
                    )
                )
            except Exception as e:
                logger.warning(
                    f"Error processing order {db_order.id if hasattr(db_order, 'id') else 'unknown'}: {e}",
                    exc_info=True,
                )
                continue

        # Order statistics - calculate from database orders
        all_db_orders = [
            o
            for o in all_orders
            if hasattr(o, "trade_mode") and o.trade_mode and o.trade_mode == TradeMode.PAPER
        ]

        total_orders = len(all_db_orders)
        buy_orders = sum(1 for o in all_db_orders if o.side.lower() == "buy")
        sell_orders = sum(1 for o in all_db_orders if o.side.lower() == "sell")

        def get_status_value(order):
            """Safely get status value from order"""
            if hasattr(order.status, "value"):
                return order.status.value.lower()
            return str(order.status).lower()

        completed_orders = [o for o in all_db_orders if get_status_value(o) == "closed"]
        pending_orders = [o for o in all_db_orders if get_status_value(o) in ["pending", "ongoing"]]
        cancelled_orders = [o for o in all_db_orders if get_status_value(o) == "cancelled"]
        rejected_orders = [o for o in all_db_orders if get_status_value(o) == "failed"]

        success_rate = (len(completed_orders) / total_orders * 100) if total_orders > 0 else 0.0

        # Count re-entry orders (orders with entry_type="REENTRY" in metadata)
        reentry_count = sum(
            1
            for db_order in all_db_orders
            if getattr(db_order, "order_metadata", None)
            and getattr(db_order, "order_metadata", {}).get("entry_type") == "REENTRY"
        )

        order_statistics = {
            "total_orders": total_orders,
            "buy_orders": buy_orders,
            "sell_orders": sell_orders,
            "completed_orders": len(completed_orders),
            "pending_orders": len(pending_orders),
            "cancelled_orders": len(cancelled_orders),
            "rejected_orders": len(rejected_orders),
            "success_rate": success_rate,
            "reentry_orders": reentry_count,
        }

        return PaginatedPaperTradingPortfolio(
            account=account,
            holdings=holdings,
            recent_orders=PaginatedPaperTradingOrders(
                items=recent_orders,
                total=total_orders_count,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            ),
            order_statistics=order_statistics,
        )

    except HTTPException:
        # Re-raise HTTPException as-is (e.g., 404 for account not initialized)
        raise
    except Exception as e:
        logger.exception(f"Error fetching paper trading portfolio for user {current.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch portfolio: {str(e)}") from e


@router.get("/history", response_model=PaginatedTradeHistory)
def get_paper_trading_history(  # noqa: PLR0915
    positions_page: Annotated[
        int,
        Query(ge=1, description="Page number for closed positions (1-based)"),
    ] = 1,
    positions_page_size: Annotated[
        int,
        Query(ge=1, le=500, description="Number of closed positions per page"),
    ] = 10,
    transactions_page: Annotated[
        int,
        Query(ge=1, description="Page number for transactions (1-based)"),
    ] = 1,
    transactions_page_size: Annotated[
        int,
        Query(ge=1, le=500, description="Number of transactions per page"),
    ] = 10,
    current: Users = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> PaginatedTradeHistory:
    """
    Get complete paper trading transaction history

    Returns:
        - All transactions (buys and sells)
        - Closed positions with P&L
        - Statistics
    """
    try:
        # Prefer DB-backed trade history: Orders + closed Positions
        positions_repo = PositionsRepository(db)
        orders_repo = OrdersRepository(db)

        # Build transactions from Orders
        fee_rate = getattr(PnlCalculationService, "DEFAULT_FEE_RATE", 0.0)
        orders, _ = orders_repo.list(current.id)
        transactions_db: list[PaperTradingTransaction] = []
        for o in orders:
            try:
                qty = int(o.quantity or 0)
                price = float(o.avg_price or o.price or 0.0)
                val = qty * price
                charges = round(val * fee_rate, 6) if fee_rate else 0.0
                transactions_db.append(
                    PaperTradingTransaction(
                        order_id=str(getattr(o, "order_id", None) or o.id),
                        symbol=o.symbol,
                        transaction_type=("BUY" if (o.side or "").lower() == "buy" else "SELL"),
                        quantity=qty,
                        price=price,
                        order_value=val,
                        charges=charges,
                        timestamp=(
                            o.placed_at.isoformat() if getattr(o, "placed_at", None) else ""
                        ),
                    )
                )
            except Exception:
                continue

        # Build closed positions from Positions (strictly from Positions table)
        closed_positions_db: list[ClosedPosition] = []
        db_positions = (
            db.query(PositionsModel)
            .filter(
                PositionsModel.user_id == current.id, PositionsModel.closed_at != None
            )  # noqa: E711
            .all()
        )

        for pos in db_positions:
            try:
                entry_price = float(pos.avg_price or 0.0)
                exit_price = float(pos.exit_price or 0.0)
                realized = float(pos.realized_pnl or 0.0)
                # Quantity comes from the Positions table
                qty = int(getattr(pos, "quantity", 0) or 0)
                # If closed positions set quantity to 0, try to recover from sell order
                if qty == 0 and pos.sell_order_id:
                    try:
                        sell_order = orders_repo.get(pos.sell_order_id)
                        if sell_order and sell_order.quantity:
                            qty = int(sell_order.quantity)
                    except Exception:
                        pass
                # As a safety fallback only if quantity is still missing, infer from realized and prices
                if (
                    qty == 0
                    and exit_price
                    and entry_price
                    and (exit_price != entry_price)
                    and realized
                ):
                    try:
                        qty = int(round(realized / (exit_price - entry_price)))
                    except Exception:
                        qty = 0

                # Approximate combined charges via fee rate
                charges = 0.0
                if fee_rate and qty > 0:
                    buy_val = qty * entry_price
                    sell_val = qty * exit_price
                    charges = round((buy_val + sell_val) * fee_rate, 6)

                buy_date_str = pos.opened_at.isoformat() if pos.opened_at else ""
                sell_date_str = pos.closed_at.isoformat() if pos.closed_at else ""
                holding_days = 0
                try:
                    if pos.opened_at and pos.closed_at:
                        holding_days = (pos.closed_at.date() - pos.opened_at.date()).days
                except Exception:
                    holding_days = 0

                pnl_pct = 0.0
                try:
                    cost = (entry_price * qty) + charges
                    pnl_pct = (realized / cost * 100) if cost > 0 else 0.0
                except Exception:
                    pnl_pct = 0.0

                # Calculate slippage (difference between expected and executed price)
                slippage = None
                if pos.sell_order_id:
                    try:
                        sell_order = orders_repo.get(pos.sell_order_id)
                        if sell_order and sell_order.price and sell_order.execution_price:
                            slippage = abs(sell_order.execution_price - sell_order.price)
                    except Exception:
                        pass

                closed_positions_db.append(
                    ClosedPosition(
                        symbol=pos.symbol,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        quantity=qty,
                        buy_date=buy_date_str,
                        sell_date=sell_date_str,
                        holding_days=holding_days,
                        realized_pnl=realized,
                        pnl_percentage=pnl_pct,
                        charges=charges,
                        slippage=slippage,
                    )
                )
            except Exception:
                continue

        # Apply pagination to closed positions
        closed_positions_sorted = sorted(
            closed_positions_db,
            key=lambda p: p.sell_date,
            reverse=True,
        )
        total_positions_count = len(closed_positions_sorted)
        positions_offset = (positions_page - 1) * positions_page_size
        paginated_positions = closed_positions_sorted[
            positions_offset : positions_offset + positions_page_size
        ]
        positions_total_pages = (
            (total_positions_count + positions_page_size - 1) // positions_page_size
            if total_positions_count > 0
            else 0
        )

        # Apply pagination to transactions
        transactions_sorted = sorted(
            transactions_db,
            key=lambda t: t.timestamp,
            reverse=True,
        )
        total_transactions_count = len(transactions_sorted)
        transactions_offset = (transactions_page - 1) * transactions_page_size
        paginated_transactions = transactions_sorted[
            transactions_offset : transactions_offset + transactions_page_size
        ]
        transactions_total_pages = (
            (total_transactions_count + transactions_page_size - 1) // transactions_page_size
            if total_transactions_count > 0
            else 0
        )

        # Upsert PnL from all closed positions (before pagination)
        _upsert_pnl_from_closed_positions(current.id, closed_positions_db, db)

        total_trades = len(closed_positions_db)
        profitable_trades = sum(1 for p in closed_positions_db if p.realized_pnl > 0)
        losing_trades = sum(1 for p in closed_positions_db if p.realized_pnl < 0)
        breakeven_trades = sum(1 for p in closed_positions_db if p.realized_pnl == 0)

        total_profit = sum(p.realized_pnl for p in closed_positions_db if p.realized_pnl > 0)
        total_loss = sum(p.realized_pnl for p in closed_positions_db if p.realized_pnl < 0)
        net_pnl = sum(p.realized_pnl for p in closed_positions_db)

        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0.0
        avg_profit = total_profit / profitable_trades if profitable_trades > 0 else 0.0
        avg_loss = total_loss / losing_trades if losing_trades > 0 else 0.0

        statistics = {
            "total_trades": total_trades,
            "profitable_trades": profitable_trades,
            "losing_trades": losing_trades,
            "breakeven_trades": breakeven_trades,
            "win_rate": win_rate,
            "total_profit": total_profit,
            "total_loss": total_loss,
            "net_pnl": net_pnl,
            "avg_profit_per_trade": avg_profit,
            "avg_loss_per_trade": avg_loss,
            "total_transactions": len(transactions_db),
        }

        return PaginatedTradeHistory(
            transactions=PaginatedTransactions(
                items=paginated_transactions,
                total=total_transactions_count,
                page=transactions_page,
                page_size=transactions_page_size,
                total_pages=transactions_total_pages,
            ),
            closed_positions=PaginatedClosedPositions(
                items=paginated_positions,
                total=total_positions_count,
                page=positions_page,
                page_size=positions_page_size,
                total_pages=positions_total_pages,
            ),
            statistics=statistics,
        )

    except Exception as e:
        logger.exception(f"Error fetching paper trading history for user {current.id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch trade history: {str(e)}"
        ) from e
