from collections import deque
from datetime import datetime
from typing import Any


def _fifo_match_orders(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute closed positions using FIFO matching from a list of transactions.

    Transactions should be ordered chronologically (oldest first).

    Returns list of closed position dicts with keys:
      symbol, quantity, avg_price, opened_at, closed_at, exit_price, realized_pnl, realized_pnl_pct
    """
    buy_lots: dict[str, deque] = {}
    closed_positions: list[dict[str, Any]] = []

    for t in transactions:
        symbol = t.get("symbol")
        side = (t.get("side") or "").lower()
        qty = float(t.get("quantity") or 0)
        if qty <= 0:
            continue
        price = t.get("execution_price") or t.get("avg_price") or t.get("price")
        try:
            price = float(price) if price is not None else None
        except Exception:
            price = None
        ts = t.get("placed_at")
        # Normalize timestamp
        if isinstance(ts, str):
            try:
                ts_val = datetime.fromisoformat(ts)
            except Exception:
                ts_val = None
        else:
            ts_val = ts

        if side == "buy":
            if symbol not in buy_lots:
                buy_lots[symbol] = deque()
            buy_lots[symbol].append({"qty": qty, "price": price, "ts": ts_val})

        elif side == "sell":
            remaining = qty
            sell_price = price
            if symbol not in buy_lots or len(buy_lots[symbol]) == 0:
                # No matching buys available; skip unmatched sells
                continue

            while remaining > 0 and buy_lots[symbol]:
                lot = buy_lots[symbol][0]
                lot_qty = lot["qty"]
                matched = min(remaining, lot_qty)
                entry_price = lot["price"]
                opened_at = lot.get("ts")
                closed_at = ts_val

                realized = None
                realized_pct = None
                if entry_price is not None and sell_price is not None:
                    realized = (sell_price - entry_price) * matched
                    try:
                        realized_pct = (
                            (sell_price - entry_price) / entry_price * 100
                            if entry_price != 0
                            else None
                        )
                    except Exception:
                        realized_pct = None

                closed_positions.append(
                    {
                        "symbol": symbol,
                        "quantity": float(matched),
                        "avg_price": float(entry_price) if entry_price is not None else None,
                        "opened_at": opened_at.isoformat() if opened_at else None,
                        "closed_at": closed_at.isoformat() if closed_at else None,
                        "exit_price": float(sell_price) if sell_price is not None else None,
                        "realized_pnl": float(realized) if realized is not None else None,
                        "realized_pnl_pct": (
                            float(realized_pct) if realized_pct is not None else None
                        ),
                    }
                )

                # decrement lot
                if matched >= lot_qty:
                    buy_lots[symbol].popleft()
                else:
                    lot["qty"] = lot_qty - matched

                remaining -= matched

    return closed_positions
