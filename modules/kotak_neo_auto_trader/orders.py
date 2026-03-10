#!/usr/bin/env python3
"""
Orders Management Module for Kotak Neo (REST, SDK-free)

Compatibility layer for `auto_trade_engine`, `sell_engine`, etc.
Uses `KotakRestClient` from `KotakNeoAuth.get_rest_client()`.
"""

from __future__ import annotations

from typing import Any

from utils.logger import logger

try:
    from .auth import KotakNeoAuth
    from .auth_handler import handle_reauth
except ImportError:  # pragma: no cover
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
    from modules.kotak_neo_auto_trader.auth_handler import handle_reauth


class KotakNeoOrders:
    def __init__(self, auth: KotakNeoAuth):
        self.auth = auth
        logger.info("KotakNeoOrders (REST) initialized")

    def _rest(self):
        if hasattr(self.auth, "get_client"):
            return self.auth.get_client()
        return self.auth.get_rest_client()

    # -------------------- Placement --------------------

    @handle_reauth
    def place_equity_order(
        self,
        symbol: str,
        quantity: int,
        price: float = 0.0,
        transaction_type: str = "BUY",
        product: str = "CNC",
        order_type: str = "MARKET",
        validity: str = "DAY",
        variety: str = "AMO",
        exchange: str = "NSE",
        remarks: str = "",
        trigger_price: float = 0.0,
    ) -> dict | None:
        rest = self._rest()

        exchange_segment_map = {
            "NSE": "nse_cm",
            "BSE": "bse_cm",
            "NFO": "nse_fo",
            "BFO": "bse_fo",
            "CDS": "cde_fo",
            "MCX": "mcx_fo",
        }
        es = exchange_segment_map.get(exchange.upper(), exchange.lower())

        am = "YES" if variety.upper() == "AMO" else "NO"
        tt = "B" if transaction_type.upper() == "BUY" else "S"
        pt = (
            "MKT"
            if order_type.upper() == "MARKET"
            else ("L" if order_type.upper() == "LIMIT" else order_type.upper())
        )
        pr = "0" if pt == "MKT" else str(float(price))
        tp = "0" if not trigger_price else str(float(trigger_price))

        jdata = {
            "am": am,
            "dq": "0",
            "es": es,
            "mp": "0",
            "pc": product.upper(),
            "pf": "N",
            "pr": pr,
            "pt": pt,
            "qt": str(int(quantity)),
            "rt": validity.upper(),
            "tp": tp,
            "ts": symbol,
            "tt": tt,
        }

        try:
            try:
                resp = rest.place_order(jdata)
            except TypeError:
                resp = rest.place_order(
                    exchange_segment=es,
                    product=product.upper(),
                    price=pr,
                    order_type=pt,
                    quantity=str(int(quantity)),
                    validity=validity.upper(),
                    trading_symbol=symbol,
                    transaction_type=tt,
                    amo=am,
                    disclosed_quantity="0",
                )
            if isinstance(resp, dict) and resp.get("stat") == "Not_Ok":
                logger.error(f"Order rejected: {resp}")
                return None
            if remarks:
                logger.debug(f"Order remarks (not sent to API): {remarks}")
            return resp if isinstance(resp, dict) else {"raw": str(resp)}
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error placing order for {symbol}: {e}")
            return None

    def place_market_buy(
        self,
        symbol: str,
        quantity: int,
        variety: str = "AMO",
        exchange: str = "NSE",
        product: str = "CNC",
    ) -> dict | None:
        return self.place_equity_order(
            symbol=symbol,
            quantity=quantity,
            transaction_type="BUY",
            order_type="MARKET",
            variety=variety,
            exchange=exchange,
            product=product,
        )

    def place_market_sell(
        self,
        symbol: str,
        quantity: int,
        variety: str = "AMO",
        exchange: str = "NSE",
        product: str = "CNC",
    ) -> dict | None:
        return self.place_equity_order(
            symbol=symbol,
            quantity=quantity,
            transaction_type="SELL",
            order_type="MARKET",
            variety=variety,
            exchange=exchange,
            product=product,
        )

    def place_limit_buy(
        self,
        symbol: str,
        quantity: int,
        price: float,
        variety: str = "AMO",
        exchange: str = "NSE",
        product: str = "CNC",
    ) -> dict | None:
        return self.place_equity_order(
            symbol=symbol,
            quantity=quantity,
            price=price,
            transaction_type="BUY",
            order_type="LIMIT",
            variety=variety,
            exchange=exchange,
            product=product,
        )

    def place_limit_sell(
        self,
        symbol: str,
        quantity: int,
        price: float,
        variety: str = "AMO",
        exchange: str = "NSE",
        product: str = "CNC",
    ) -> dict | None:
        return self.place_equity_order(
            symbol=symbol,
            quantity=quantity,
            price=price,
            transaction_type="SELL",
            order_type="LIMIT",
            variety=variety,
            exchange=exchange,
            product=product,
        )

    # -------------------- Modify / Cancel --------------------

    @handle_reauth
    def modify_order(
        self,
        order_id: str,
        price: float = None,
        quantity: int = None,
        trigger_price: float = 0,
        validity: str = "DAY",
        order_type: str = "L",
    ) -> dict | None:
        rest = self._rest()
        try:
            ob = rest.get_order_book()
            orders = ob.get("data", []) if isinstance(ob, dict) else []
            current: dict[str, Any] | None = None
            for o in orders:
                oid = o.get("nOrdNo") or o.get("neoOrdNo") or o.get("orderId")
                if str(oid) == str(order_id):
                    current = o
                    break
            if not current:
                # Fallback path for test/mocked clients that only expose modify_order()
                # and don't provide order book fields.
                logger.warning(
                    f"Order {order_id} not found in order book; attempting minimal modify payload"
                )
                minimal = {"no": str(order_id)}
                if quantity is not None:
                    minimal["qt"] = str(int(quantity))
                if price is not None:
                    minimal["pr"] = str(float(price))
                if trigger_price:
                    minimal["tp"] = str(float(trigger_price))
                resp = rest.modify_order(minimal)
                if isinstance(resp, dict) and resp.get("stat") == "Not_Ok":
                    logger.error(f"Order modification rejected: {resp}")
                    return None
                return resp if isinstance(resp, dict) else {"raw": str(resp)}

            tk = current.get("tk") or current.get("tok") or current.get("token") or current.get("instrumentToken")
            es = current.get("exSeg") or current.get("es")
            ts = current.get("trdSym") or current.get("ts")
            tt = current.get("trnsTp") or current.get("tt")
            pc = current.get("prod") or current.get("pc") or "CNC"
            pt = current.get("prcTp") or current.get("pt") or order_type
            vd = current.get("vldt") or current.get("ordDur") or validity

            # `tk` is often NOT present in Order Book; derive from scrip master when missing.
            if not tk and ts:
                try:
                    from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster

                    sm = KotakNeoScripMaster(auth_client=rest, exchanges=["NSE"])
                    sm.load_scrip_master(force_download=False)
                    tk = sm.get_token(str(ts), exchange="NSE")
                except Exception as e:
                    logger.debug(f"Failed to derive token for modify_order ({ts}): {e}")

            if not (tk and es and ts and tt):
                logger.error(f"Missing fields for modify API from order book: {current}")
                return None

            qt = str(int(quantity)) if quantity is not None else str(current.get("qty") or "0")
            pr = str(float(price)) if price is not None else str(current.get("prc") or "0")
            tp = str(float(trigger_price)) if trigger_price else str(current.get("trgPrc") or "0")

            jdata = {
                "tk": str(tk),
                "mp": str(current.get("mp") or "0"),
                "pc": str(pc),
                "dd": "NA",
                "dq": str(current.get("dq") or "0"),
                "vd": str(vd).upper(),
                "ts": str(ts),
                "tt": str(tt),
                "pr": str(pr),
                "tp": str(tp),
                "qt": str(qt),
                "no": str(order_id),
                "es": str(es),
                "pt": str(pt),
            }

            resp = rest.modify_order(jdata)
            if isinstance(resp, dict) and resp.get("stat") == "Not_Ok":
                logger.error(f"Order modification rejected: {resp}")
                return None
            return resp if isinstance(resp, dict) else {"raw": str(resp)}
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error modifying order {order_id}: {e}")
            return None

    @handle_reauth
    def cancel_order(self, order_id: str) -> dict | None:
        rest = self._rest()
        try:
            try:
                resp = rest.cancel_order(order_no=order_id, amo="NO")
            except TypeError:
                resp = rest.cancel_order(order_id)
            if isinstance(resp, dict) and resp.get("stat") == "Not_Ok":
                logger.error(f"Cancel rejected: {resp}")
                return None
            return resp if isinstance(resp, dict) else {"raw": str(resp)}
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error cancelling order {order_id}: {e}")
            return None

    # -------------------- Fetch --------------------

    @handle_reauth
    def get_orders(self) -> dict | None:
        rest = self._rest()
        try:
            if hasattr(rest, "get_order_book"):
                return rest.get_order_book()
            if hasattr(rest, "order_report"):
                return rest.order_report()
            return None
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error getting orders: {e}")
            return None

    def get_order_book(self) -> dict | None:
        return self.get_orders()

    def get_order_history(self, order_id: str) -> dict | None:
        rest = self._rest()
        try:
            if hasattr(rest, "get_order_history"):
                return rest.get_order_history(order_id)
            if hasattr(rest, "order_history"):
                return rest.order_history(order_id)
            return None
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error getting order history: {e}")
            return None

    def get_pending_orders(self) -> list[dict] | None:
        orders = self.get_orders()
        if not orders or "data" not in orders:
            return None
        data = orders.get("data") or []
        if not isinstance(data, list):
            return None

        pending: list[dict] = []
        for o in data:
            if not isinstance(o, dict):
                continue
            st = str(o.get("ordSt") or "").lower()
            if any(x in st for x in ("open", "pending", "req received", "trigger")):
                pending.append(o)
        return pending

    def get_executed_orders(self) -> list[dict] | None:
        """
        Compatibility helper used by legacy sell/manual-reconciliation paths.
        Returns executed/filled orders from current order book payload.
        """
        orders = self.get_orders()
        if not orders or "data" not in orders:
            return None
        data = orders.get("data") or []
        if not isinstance(data, list):
            return None

        executed: list[dict] = []
        for o in data:
            if not isinstance(o, dict):
                continue
            st = str(
                o.get("ordSt") or o.get("orderStatus") or o.get("status") or o.get("stat") or ""
            ).lower()
            if any(x in st for x in ("executed", "complete", "completed", "filled")):
                executed.append(o)
        return executed

    def cancel_pending_buys_for_symbol(self, symbol_variants: list[str] | str) -> int:
        variants = symbol_variants if isinstance(symbol_variants, list) else [symbol_variants]
        variants_upper = {v.upper() for v in variants}

        pending = self.get_pending_orders() or []
        cancelled = 0
        for o in pending:
            trd = str(o.get("trdSym") or o.get("tradingSymbol") or "").upper()
            if trd not in variants_upper:
                continue
            if str(o.get("trnsTp") or "").upper() != "B":
                continue
            oid = o.get("nOrdNo") or o.get("neoOrdNo") or o.get("orderId")
            if not oid:
                continue
            if self.cancel_order(str(oid)):
                cancelled += 1
        return cancelled

