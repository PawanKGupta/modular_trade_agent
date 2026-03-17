from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeKotakRestClient:
    """
    Stateful in-memory Kotak REST simulator for integration tests.

    Supports the subset of endpoints used by Kotak wrappers:
    - orders: place/modify/cancel/get_order_book/get_order_history
    - portfolio: holdings/positions/limits
    """

    holdings_rows: list[dict[str, Any]] = field(default_factory=list)
    positions_rows: list[dict[str, Any]] = field(default_factory=list)
    order_book_rows: list[dict[str, Any]] = field(default_factory=list)
    limits_payload: dict[str, Any] = field(
        default_factory=lambda: {"data": {"cash": 0.0, "availableMargin": 0.0}}
    )
    _id_counter: int = 700000000
    placed_orders: list[dict[str, Any]] = field(default_factory=list)
    modified_orders: list[dict[str, Any]] = field(default_factory=list)
    cancelled_orders: list[str] = field(default_factory=list)

    def _next_order_id(self) -> str:
        self._id_counter += 1
        return str(self._id_counter)

    # ----- Portfolio -----
    def get_holdings(self) -> dict[str, Any]:
        return {"data": list(self.holdings_rows)}

    def get_positions(self) -> dict[str, Any]:
        return {"data": list(self.positions_rows)}

    def get_limits(self, seg: str = "ALL", exch: str = "ALL", prod: str = "ALL") -> dict[str, Any]:
        _ = (seg, exch, prod)
        return self.limits_payload

    # ----- Orders -----
    def get_order_book(self) -> dict[str, Any]:
        return {"data": list(self.order_book_rows)}

    def order_report(self) -> dict[str, Any]:
        return self.get_order_book()

    def get_order_history(self, order_id: str) -> dict[str, Any]:
        for row in self.order_book_rows:
            oid = row.get("nOrdNo") or row.get("neoOrdNo") or row.get("orderId")
            if str(oid) == str(order_id):
                return {"data": [row]}
        return {"data": []}

    def place_order(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        # Supports both place_order(jData) and place_order(**kwargs) wrapper paths.
        if args and isinstance(args[0], dict):
            data = args[0]
            symbol = str(data.get("ts") or "").upper()
            qty = int(float(data.get("qt") or 0))
            price = float(data.get("pr") or 0)
            side = str(data.get("tt") or "B").upper()
            order_type = str(data.get("pt") or "L").upper()
            exchange_segment = str(data.get("es") or "nse_cm")
            token = str(data.get("tk") or "1001")
        else:
            symbol = str(kwargs.get("trading_symbol") or kwargs.get("ts") or "").upper()
            qty = int(float(kwargs.get("quantity") or kwargs.get("qt") or 0))
            price = float(kwargs.get("price") or kwargs.get("pr") or 0)
            side = str(kwargs.get("transaction_type") or kwargs.get("tt") or "B").upper()
            order_type = str(kwargs.get("order_type") or kwargs.get("pt") or "L").upper()
            exchange_segment = str(kwargs.get("exchange_segment") or kwargs.get("es") or "nse_cm")
            token = str(kwargs.get("token") or kwargs.get("tk") or "1001")

        order_id = self._next_order_id()
        row = {
            "nOrdNo": order_id,
            "neoOrdNo": order_id,
            "orderId": order_id,
            "trdSym": symbol,
            "ts": symbol,
            "qty": str(qty),
            "prc": str(price),
            "trnsTp": "S" if side in ("S", "SELL") else "B",
            "tt": "S" if side in ("S", "SELL") else "B",
            "ordSt": "open",
            "stat": "open",
            "prcTp": order_type,
            "pt": order_type,
            "es": exchange_segment,
            "tk": token,
            "pc": "CNC",
        }
        self.order_book_rows.append(row)
        self.placed_orders.append(row)
        return {"stat": "Ok", "nOrdNo": order_id, "data": {"orderId": order_id}}

    def modify_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        order_id = str(payload.get("no") or payload.get("order_id") or payload.get("orderId") or "")
        for row in self.order_book_rows:
            oid = row.get("nOrdNo") or row.get("neoOrdNo") or row.get("orderId")
            if str(oid) != order_id:
                continue
            if "qt" in payload and payload.get("qt") is not None:
                row["qty"] = str(payload.get("qt"))
            if "pr" in payload and payload.get("pr") is not None:
                row["prc"] = str(payload.get("pr"))
            if "tp" in payload and payload.get("tp") is not None:
                row["trgPrc"] = str(payload.get("tp"))
            self.modified_orders.append({"order_id": order_id, "payload": dict(payload)})
            return {"stat": "Ok", "nOrdNo": order_id}
        return {"stat": "Not_Ok", "message": f"Order {order_id} not found"}

    def cancel_order(self, order_no: str | None = None, amo: str | None = None) -> dict[str, Any]:
        _ = amo
        target = str(order_no or "")
        for row in self.order_book_rows:
            oid = row.get("nOrdNo") or row.get("neoOrdNo") or row.get("orderId")
            if str(oid) != target:
                continue
            row["ordSt"] = "cancelled"
            row["stat"] = "cancelled"
            self.cancelled_orders.append(target)
            return {"stat": "Ok", "nOrdNo": target}
        return {"stat": "Not_Ok", "message": f"Order {target} not found"}


@dataclass
class FakeKotakAuth:
    """Minimal auth simulator used by Kotak wrappers."""

    rest_client: FakeKotakRestClient
    authenticated: bool = True

    def get_rest_client(self) -> FakeKotakRestClient:
        return self.rest_client

    def get_client(self) -> FakeKotakRestClient:
        return self.rest_client

    def is_authenticated(self) -> bool:
        return self.authenticated

    def login(self) -> bool:
        self.authenticated = True
        return True

    def logout(self) -> bool:
        self.authenticated = False
        return True

    def force_relogin(self) -> bool:
        self.authenticated = True
        return True


@dataclass
class FakeStockSignalFeed:
    """Deterministic indicator simulator keyed by ticker."""

    ema9_by_ticker: dict[str, float]

    def get_ema9(self, ticker: str, broker_symbol: str | None = None, symbol: str | None = None) -> float | None:
        _ = (broker_symbol, symbol)
        return self.ema9_by_ticker.get(ticker)
