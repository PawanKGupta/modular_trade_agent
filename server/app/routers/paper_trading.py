"""
Paper Trading API endpoints
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from modules.kotak_neo_auto_trader.infrastructure.persistence import PaperTradeStore
from modules.kotak_neo_auto_trader.infrastructure.simulation import PaperTradeReporter
from src.infrastructure.db.models import Users

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
    target_price: float | None = None  # Frozen EMA9 target
    distance_to_target: float | None = None  # % to reach target


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


class TradeHistory(BaseModel):
    transactions: list[PaperTradingTransaction]
    closed_positions: list[ClosedPosition]
    statistics: dict[str, Any]


class PaperTradingPortfolio(BaseModel):
    account: PaperTradingAccount
    holdings: list[PaperTradingHolding]
    recent_orders: list[PaperTradingOrder]
    order_statistics: dict


@router.get("/portfolio", response_model=PaperTradingPortfolio)
def get_paper_trading_portfolio(  # noqa: PLR0915, PLR0912, B008
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
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

        # Fetch live prices using yfinance (broker-agnostic)
        import yfinance as yf  # noqa: PLC0415

        portfolio_value = 0.0
        for symbol, h in holdings_data.items():
            qty = h.get("quantity", 0)
            ticker = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
            try:
                stock = yf.Ticker(ticker)
                live_price = stock.info.get("currentPrice") or stock.info.get("regularMarketPrice")
                current_price = (
                    float(live_price) if live_price else float(h.get("current_price", 0))
                )
            except Exception:
                # Fallback to stored price if live fetch fails
                current_price = float(h.get("current_price", 0))
            portfolio_value += qty * current_price

        total_value = account_data["available_cash"] + portfolio_value
        return_pct = (
            ((total_value - account_data["initial_capital"]) / account_data["initial_capital"])
            * 100
            if account_data["initial_capital"] > 0
            else 0.0
        )

        # Get realized P&L from stored account (from completed trades)
        realized_pnl = account_data.get("realized_pnl", 0.0)

        # Load target prices from service adapter's active_sell_orders
        target_prices = {}
        try:
            # Try to load active sell orders from service adapter storage
            import json  # noqa: PLC0415

            sell_orders_file = store_path / "active_sell_orders.json"
            if sell_orders_file.exists():
                with open(sell_orders_file) as f:
                    active_sell_orders = json.load(f)
                    for symbol, order_info in active_sell_orders.items():
                        target_prices[symbol] = float(order_info.get("target_price", 0))
                        logger.debug(f"Loaded target for {symbol}: {target_prices[symbol]}")
        except Exception as e:
            logger.debug(f"Could not load target prices: {e}")

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

        # Calculate target prices on-the-fly if not available
        def calculate_ema9_target(symbol: str) -> float | None:
            """Calculate EMA9 target for a holding"""
            try:
                import pandas_ta as ta  # noqa: PLC0415

                from core.data_fetcher import fetch_ohlcv_yf  # noqa: PLC0415

                ticker = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
                data = fetch_ohlcv_yf(ticker, days=60, interval="1d")

                if data is None or data.empty:
                    return None

                # Use lowercase column names (as returned by fetch_ohlcv_yf)
                data["ema9"] = ta.ema(data["close"], length=9)
                ema9 = data.iloc[-1]["ema9"]

                return float(ema9) if not data.iloc[-1]["ema9"] != data.iloc[-1]["ema9"] else None
            except Exception as e:
                logger.debug(f"Failed to calculate EMA9 for {symbol}: {e}")
                return None

        # Holdings (calculate unrealized P&L with live prices)
        holdings = []
        unrealized_pnl_total = 0.0

        for symbol, holding in sorted(holdings_data.items()):
            qty = holding.get("quantity", 0)
            avg_price = float(holding.get("average_price", 0))

            # Fetch live price, fallback to stored price if fetch fails
            current_price = get_live_price(symbol)
            if current_price is None:
                current_price = float(holding.get("current_price", 0))
                logger.debug(f"Using stored price for {symbol}: {current_price}")

            cost_basis = qty * avg_price
            market_value = qty * current_price
            pnl = market_value - cost_basis
            pnl_pct = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0.0

            # Accumulate unrealized P&L
            unrealized_pnl_total += pnl

            # Get target price (frozen EMA9) if available, or calculate it
            target_price = target_prices.get(symbol)
            if target_price is None:
                # Calculate on-the-fly if no sell order placed yet
                target_price = calculate_ema9_target(symbol)

            distance_to_target = None
            if target_price and current_price > 0:
                distance_to_target = (target_price - current_price) / current_price * 100

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
                )
            )

        # Calculate total P&L with live prices
        total_pnl = realized_pnl + unrealized_pnl_total

        # Create account object with recalculated P&L
        account = PaperTradingAccount(
            initial_capital=account_data["initial_capital"],
            available_cash=account_data["available_cash"],
            total_pnl=total_pnl,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl_total,
            portfolio_value=portfolio_value,
            total_value=total_value,
            return_percentage=return_pct,
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
        raise HTTPException(status_code=500, detail=f"Failed to fetch portfolio: {str(e)}") from e


@router.get("/history", response_model=TradeHistory)
def get_paper_trading_history(  # noqa: PLR0915
    current: Users = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> TradeHistory:
    """
    Get complete paper trading transaction history

    Returns:
        - All transactions (buys and sells)
        - Closed positions with P&L
        - Statistics
    """
    try:
        # Get user's paper trading storage path
        store_path = Path("paper_trading") / f"user_{current.id}"

        if not store_path.exists():
            # Return empty history if no data exists
            return TradeHistory(
                transactions=[],
                closed_positions=[],
                statistics={
                    "total_trades": 0,
                    "profitable_trades": 0,
                    "losing_trades": 0,
                    "breakeven_trades": 0,
                    "win_rate": 0.0,
                    "total_profit": 0.0,
                    "total_loss": 0.0,
                    "net_pnl": 0.0,
                    "avg_profit_per_trade": 0.0,
                    "avg_loss_per_trade": 0.0,
                    "total_transactions": 0,
                },
            )

        # Initialize store
        store = PaperTradeStore(storage_path=str(store_path), auto_save=False)

        # Get all transactions
        all_transactions = store.get_all_transactions()

        # Convert transactions to response format
        transactions = [
            PaperTradingTransaction(
                order_id=t.get("order_id", ""),
                symbol=t.get("symbol", ""),
                transaction_type=t.get("transaction_type", ""),
                quantity=t.get("quantity", 0),
                price=t.get("price", 0.0),
                order_value=t.get("order_value", 0.0),
                charges=t.get("charges", 0.0),
                timestamp=t.get("timestamp", ""),
            )
            for t in all_transactions
        ]

        # Calculate closed positions from transactions
        # Group by symbol and match buys with sells
        closed_positions = []
        symbol_transactions: dict[str, dict[str, list]] = {}

        # Group transactions by symbol
        for txn in all_transactions:
            symbol = txn.get("symbol", "")
            if symbol not in symbol_transactions:
                symbol_transactions[symbol] = {"buys": [], "sells": []}

            if txn.get("transaction_type") == "BUY":
                symbol_transactions[symbol]["buys"].append(txn)
            elif txn.get("transaction_type") == "SELL":
                symbol_transactions[symbol]["sells"].append(txn)

        # Match buys with sells to create closed positions (FIFO)
        for symbol, txns in symbol_transactions.items():
            buys = sorted(txns["buys"], key=lambda x: x.get("timestamp", ""))
            sells = sorted(txns["sells"], key=lambda x: x.get("timestamp", ""))

            buy_queue = buys.copy()
            sell_queue = sells.copy()

            while buy_queue and sell_queue:
                buy = buy_queue[0]
                sell = sell_queue[0]

                buy_qty_remaining = buy.get("quantity", 0)
                sell_qty_remaining = sell.get("quantity", 0)

                # Match quantities
                matched_qty = min(buy_qty_remaining, sell_qty_remaining)

                if matched_qty > 0:
                    # Create closed position
                    buy_price = buy.get("price", 0.0)
                    sell_price = sell.get("price", 0.0)
                    buy_charges = buy.get("charges", 0.0)
                    sell_charges = sell.get("charges", 0.0)

                    # Calculate P&L
                    cost = (buy_price * matched_qty) + buy_charges
                    revenue = (sell_price * matched_qty) - sell_charges
                    pnl = revenue - cost
                    pnl_pct = (pnl / cost * 100) if cost > 0 else 0.0

                    # Calculate holding period
                    buy_date_str = buy.get("timestamp", "")
                    sell_date_str = sell.get("timestamp", "")
                    holding_days = 0

                    try:
                        buy_date = datetime.fromisoformat(buy_date_str)
                        sell_date = datetime.fromisoformat(sell_date_str)
                        holding_days = (sell_date - buy_date).days
                    except (ValueError, TypeError):
                        holding_days = 0

                    closed_positions.append(
                        ClosedPosition(
                            symbol=symbol,
                            entry_price=buy_price,
                            exit_price=sell_price,
                            quantity=matched_qty,
                            buy_date=buy_date_str,
                            sell_date=sell_date_str,
                            holding_days=holding_days,
                            realized_pnl=pnl,
                            pnl_percentage=pnl_pct,
                            charges=buy_charges + sell_charges,
                        )
                    )

                    # Update quantities
                    buy["quantity"] = buy_qty_remaining - matched_qty
                    sell["quantity"] = sell_qty_remaining - matched_qty

                # Remove fully matched transactions
                if buy.get("quantity", 0) == 0:
                    buy_queue.pop(0)
                if sell.get("quantity", 0) == 0:
                    sell_queue.pop(0)

        # Calculate statistics
        total_trades = len(closed_positions)
        profitable_trades = sum(1 for p in closed_positions if p.realized_pnl > 0)
        losing_trades = sum(1 for p in closed_positions if p.realized_pnl < 0)
        breakeven_trades = sum(1 for p in closed_positions if p.realized_pnl == 0)

        total_profit = sum(p.realized_pnl for p in closed_positions if p.realized_pnl > 0)
        total_loss = sum(p.realized_pnl for p in closed_positions if p.realized_pnl < 0)
        net_pnl = sum(p.realized_pnl for p in closed_positions)

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
            "total_transactions": len(all_transactions),
        }

        return TradeHistory(
            transactions=transactions, closed_positions=closed_positions, statistics=statistics
        )

    except Exception as e:
        logger.exception(f"Error fetching paper trading history for user {current.id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch trade history: {str(e)}"
        ) from e
