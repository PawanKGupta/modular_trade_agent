"""
Paper Trading API endpoints
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Users
from modules.kotak_neo_auto_trader.infrastructure.persistence import PaperTradeStore
from modules.kotak_neo_auto_trader.infrastructure.simulation import PaperTradeReporter

from ..core.deps import get_current_user, get_db

logger = logging.getLogger(__name__)

router = APIRouter()


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


class PaperTradingOrder(BaseModel):
    order_id: str
    symbol: str
    transaction_type: str
    quantity: int
    order_type: str
    status: str
    execution_price: Optional[float] = None
    created_at: str
    executed_at: Optional[str] = None


class PaperTradingPortfolio(BaseModel):
    account: PaperTradingAccount
    holdings: list[PaperTradingHolding]
    recent_orders: list[PaperTradingOrder]
    order_statistics: dict


@router.get("/portfolio", response_model=PaperTradingPortfolio)
def get_paper_trading_portfolio(
    db: Session = Depends(get_db), current: Users = Depends(get_current_user)
):
    """Get paper trading portfolio for the current user"""
    try:
        storage_path = f"paper_trading/user_{current.id}"
        store_path = Path(storage_path)

        if not store_path.exists():
            # Return empty portfolio if no data exists
            return PaperTradingPortfolio(
                account=PaperTradingAccount(
                    initial_capital=0.0,
                    available_cash=0.0,
                    total_pnl=0.0,
                    realized_pnl=0.0,
                    unrealized_pnl=0.0,
                    portfolio_value=0.0,
                    total_value=0.0,
                    return_percentage=0.0,
                ),
                holdings=[],
                recent_orders=[],
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

        store = PaperTradeStore(storage_path, auto_save=False)
        reporter = PaperTradeReporter(store)

        # Account information
        account_data = store.get_account()
        if not account_data:
            raise HTTPException(status_code=404, detail="Paper trading account not initialized")

        # Calculate portfolio value
        holdings_data = store.get_all_holdings()
        portfolio_value = sum(
            h.get("quantity", 0) * float(h.get("current_price", 0))
            for h in holdings_data.values()
        )
        total_value = account_data["available_cash"] + portfolio_value
        return_pct = (
            ((total_value - account_data["initial_capital"]) / account_data["initial_capital"])
            * 100
            if account_data["initial_capital"] > 0
            else 0.0
        )

        account = PaperTradingAccount(
            initial_capital=account_data["initial_capital"],
            available_cash=account_data["available_cash"],
            total_pnl=account_data.get("total_pnl", 0.0),
            realized_pnl=account_data.get("realized_pnl", 0.0),
            unrealized_pnl=account_data.get("unrealized_pnl", 0.0),
            portfolio_value=portfolio_value,
            total_value=total_value,
            return_percentage=return_pct,
        )

        # Holdings
        holdings = []
        for symbol, holding in sorted(holdings_data.items()):
            qty = holding.get("quantity", 0)
            avg_price = float(holding.get("average_price", 0))
            current_price = float(holding.get("current_price", 0))
            cost_basis = qty * avg_price
            market_value = qty * current_price
            pnl = market_value - cost_basis
            pnl_pct = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0.0

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
                )
            )

        # Recent orders (last 50)
        orders_data = store.get_all_orders()
        orders_data.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        recent_orders = []
        for order in orders_data[:50]:
            recent_orders.append(
                PaperTradingOrder(
                    order_id=order.get("order_id", ""),
                    symbol=order.get("symbol", ""),
                    transaction_type=order.get("transaction_type", ""),
                    quantity=order.get("quantity", 0),
                    order_type=order.get("order_type", ""),
                    status=order.get("status", ""),
                    execution_price=order.get("execution_price")
                    or order.get("limit_price")
                    or None,
                    created_at=order.get("created_at", ""),
                    executed_at=order.get("executed_at"),
                )
            )

        # Order statistics
        stats = reporter.order_statistics()
        total_orders = stats.get("total_orders", 0)
        success_rate = (
            (stats.get("completed_orders", 0) / total_orders * 100) if total_orders > 0 else 0.0
        )

        order_statistics = {
            "total_orders": total_orders,
            "buy_orders": stats.get("buy_orders", 0),
            "sell_orders": stats.get("sell_orders", 0),
            "completed_orders": stats.get("completed_orders", 0),
            "pending_orders": stats.get("pending_orders", 0),
            "cancelled_orders": stats.get("cancelled_orders", 0),
            "rejected_orders": stats.get("rejected_orders", 0),
            "success_rate": success_rate,
        }

        return PaperTradingPortfolio(
            account=account,
            holdings=holdings,
            recent_orders=recent_orders,
            order_statistics=order_statistics,
        )

    except Exception as e:
        logger.exception(f"Error fetching paper trading portfolio for user {current.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch portfolio: {str(e)}")

