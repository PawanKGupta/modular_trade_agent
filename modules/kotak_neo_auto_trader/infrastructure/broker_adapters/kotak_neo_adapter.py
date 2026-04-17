"""
Kotak Neo Broker Adapter (REST-only).

Implements `IBrokerGateway` using Kotak Neo REST APIs only, while keeping
non-SDK compatibility helpers used by existing runtime paths/tests
(client refresh, re-auth gating, timeout wrapper, and flexible response mapping).
"""

from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime
from typing import Any, Callable

from utils.logger import logger

from ...domain import (
    Exchange,
    Holding,
    IBrokerGateway,
    Money,
    Order,
    OrderStatus,
    OrderType,
    OrderVariety,
    TransactionType,
)
from ..clients.kotak_rest_client import KotakRestClient

_REAUTH_BLOCKED = object()


class BrokerServiceUnavailableError(RuntimeError):
    def __init__(
        self,
        message: str | None = None,
        *,
        original_error: Exception | None = None,
    ) -> None:
        self.message = message or "Broker service is temporarily unavailable. Please try again later."
        self.original_error = original_error
        super().__init__(self.message)


def call_with_timeout(func: Callable[..., Any], *args: Any, timeout: float = 30.0, **kwargs: Any) -> Any:
    """
    Timeout wrapper hook.

    We keep this as an overridable module function so tests can monkeypatch it.
    The default implementation calls the function directly.
    """
    _ = timeout
    return func(*args, **kwargs)


def _is_network_connectivity_error(error: Exception) -> bool:
    s = str(error).lower()
    patterns = [
        "errno 101",
        "network is unreachable",
        "no route to host",
        "name or service not known",
        "temporary failure in name resolution",
        "dns",
        "connection refused",
        "failed to establish a new connection",
        "newconnectionerror",
        "max retries exceeded",
    ]
    return any(p in s for p in patterns)


def _extract_api_error_message(error: Exception) -> str | None:
    if _is_network_connectivity_error(error):
        return None

    resp = getattr(error, "response", None)
    if resp is not None:
        try:
            body = resp.json()
            if isinstance(body, dict):
                if isinstance(body.get("message"), str):
                    return body["message"]
                if isinstance(body.get("error"), str):
                    return body["error"]
                if isinstance(body.get("description"), str):
                    return body["description"]
                err_val = body.get("error")
                if isinstance(err_val, list) and err_val and isinstance(err_val[0], dict):
                    msg = err_val[0].get("message")
                    if isinstance(msg, str):
                        return msg
        except Exception:
            pass

        text = getattr(resp, "text", None)
        if isinstance(text, str) and text and len(text) < 500:
            return text

    s = str(error)
    m = re.search(r"(\{.*\})", s)
    if m:
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict):
                if isinstance(obj.get("message"), str):
                    return obj["message"]
                if isinstance(obj.get("emsg"), str):
                    return obj["emsg"]
        except Exception:
            pass

    if s and s.strip() and not _is_network_connectivity_error(Exception(s)):
        return s if len(s) < 500 else None
    return None


def _get_service_unavailable_message(error: Exception, default_message: str) -> str:
    extracted = _extract_api_error_message(error)
    return extracted or default_message


def _is_service_unavailable_error(error: Exception) -> bool:
    if _is_network_connectivity_error(error):
        return False
    s = str(error).lower()
    return any(
        p in s
        for p in (
            "http 503",
            "503 service unavailable",
            "service unavailable",
            "maintenance",
            "dependency error",
            "424",
            "adapter is down",
        )
    )


def is_auth_error(response: Any) -> bool:
    if not isinstance(response, dict):
        return False
    code = str(response.get("code") or response.get("stCode") or response.get("statusCode") or "").strip()
    msg = str(response.get("message") or response.get("emsg") or response.get("error") or "").lower()
    if code in {"401", "900901", "1003"}:
        return True
    return any(
        token in msg
        for token in ("jwt", "token expired", "invalid session", "session expired", "not authenticated", "auth")
    )


def is_auth_exception(error: Exception) -> bool:
    s = str(error).lower()
    return any(token in s for token in ("jwt", "token expired", "invalid session", "session expired", "unauthorized"))


def _check_reauth_failure_rate(auth_handler: Any, window_seconds: int = 60, max_failures: int = 3) -> bool:
    now = time.time()
    failures = list(getattr(auth_handler, "_reauth_failures", []))
    failures = [ts for ts in failures if now - ts <= window_seconds]
    setattr(auth_handler, "_reauth_failures", failures)
    return len(failures) >= max_failures


def _record_reauth_failure(auth_handler: Any) -> None:
    failures = list(getattr(auth_handler, "_reauth_failures", []))
    failures.append(time.time())
    setattr(auth_handler, "_reauth_failures", failures)


def _attempt_reauth_thread_safe(auth_handler: Any) -> bool:
    if auth_handler is None:
        return False
    lock = getattr(auth_handler, "_reauth_lock", None)
    if lock is None:
        lock = threading.Lock()
        setattr(auth_handler, "_reauth_lock", lock)

    with lock:
        relogin = getattr(auth_handler, "force_relogin", None)
        if callable(relogin):
            try:
                return bool(relogin())
            except Exception:
                return False
        return False


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value))
    except Exception:
        return default


def _normalize_symbol(symbol: str) -> str:
    s = (symbol or "").upper().strip()
    for suffix in ("-EQ", "-BE", "-BL", "-BZ", "-NSE"):
        if s.endswith(suffix):
            return s[: -len(suffix)]
    return s


class KotakNeoBrokerAdapter(IBrokerGateway):
    def __init__(self, auth_handler):
        self.auth_handler = auth_handler
        self._client: Any | None = None
        self._rest_client: KotakRestClient | None = None
        self._connected = False

    def connect(self) -> bool:
        try:
            if not self.auth_handler or not self.auth_handler.login():
                return False
            if hasattr(self.auth_handler, "is_authenticated") and not self.auth_handler.is_authenticated():
                return False
            self._ensure_fresh_client()
            self._connected = True
            return True
        except Exception as e:  # noqa: BLE001
            logger.error(f"Connection failed: {e}")
            return False

    def disconnect(self) -> bool:
        try:
            ok = True
            if self.auth_handler and hasattr(self.auth_handler, "logout"):
                ok = bool(self.auth_handler.logout())
            self._client = None
            self._rest_client = None
            self._connected = False
            return ok
        except Exception as e:  # noqa: BLE001
            logger.error(f"Disconnect failed: {e}")
            return False

    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    def _ensure_fresh_client(self, require_connected: bool = False):
        if require_connected and not self._connected:
            raise ConnectionError("Not connected to broker")
        if self.auth_handler and hasattr(self.auth_handler, "is_authenticated"):
            if not self.auth_handler.is_authenticated():
                raise ConnectionError("Not authenticated")

        candidate = None
        if self.auth_handler is not None:
            if hasattr(self.auth_handler, "get_client"):
                candidate = self.auth_handler.get_client()
            elif hasattr(self.auth_handler, "get_rest_client"):
                candidate = self.auth_handler.get_rest_client()
            else:
                candidate = getattr(self.auth_handler, "client", None)

        if candidate is None:
            if self._client is not None:
                return self._client
            raise ConnectionError("REST client not available")

        if candidate is not self._client:
            self._client = candidate
            self._rest_client = candidate if isinstance(candidate, KotakRestClient) else None
        return self._client

    def _invoke_first(self, client: Any, method_names: list[str], *args: Any, **kwargs: Any) -> Any:
        last_err: Exception | None = None
        for name in method_names:
            method = getattr(client, name, None)
            if not callable(method):
                continue
            try:
                return call_with_timeout(method, *args, **kwargs)
            except TypeError:
                # Support clients with different parameter styles
                try:
                    if kwargs and not args:
                        return call_with_timeout(method, *kwargs.values())
                except Exception as te:  # noqa: BLE001
                    last_err = te
                    raise
            except Exception as e:  # noqa: BLE001
                last_err = e
                raise
        if last_err:
            raise last_err
        raise AttributeError(f"No supported method found in client: {method_names}")

    def _extract_orders_data(self, resp: Any) -> list[dict[str, Any]]:
        if isinstance(resp, list):
            return [x for x in resp if isinstance(x, dict)]
        if not isinstance(resp, dict):
            return []
        for key in ("data", "orders", "orderList"):
            val = resp.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
        return []

    def _with_auth_retry(self, fn: Callable[[], Any], default_result: Any, operation_name: str):
        attempts = 0
        while attempts < 2:
            attempts += 1
            try:
                result = fn()
                if is_auth_error(result):
                    if attempts >= 2:
                        return default_result
                    if self.auth_handler is None or _check_reauth_failure_rate(self.auth_handler):
                        return _REAUTH_BLOCKED
                    if not _attempt_reauth_thread_safe(self.auth_handler):
                        _record_reauth_failure(self.auth_handler)
                        return default_result
                    continue
                return result
            except TimeoutError:
                if self.auth_handler is None:
                    return default_result
                if attempts >= 2:
                    return default_result
                continue
            except Exception as e:  # noqa: BLE001
                if is_auth_exception(e):
                    if attempts >= 2:
                        return default_result
                    if self.auth_handler is None or _check_reauth_failure_rate(self.auth_handler):
                        return _REAUTH_BLOCKED
                    if not _attempt_reauth_thread_safe(self.auth_handler):
                        _record_reauth_failure(self.auth_handler)
                        return default_result
                    continue
                if _is_service_unavailable_error(e):
                    raise BrokerServiceUnavailableError(
                        _get_service_unavailable_message(e, f"{operation_name} unavailable"),
                        original_error=e,
                    ) from e
                logger.debug(f"{operation_name} failed: {e}")
                return default_result
        return default_result

    def place_order(self, order: Order) -> str:
        if not self.is_connected():
            raise ConnectionError("Not connected to broker")

        jdata = self._build_place_order_jdata(order)

        def _call_place():
            client = self._ensure_fresh_client(require_connected=True)
            try:
                return self._invoke_first(client, ["place_order"], jdata)
            except TypeError:
                sdk_payload = {
                    "exchange_segment": jdata["es"],
                    "product": jdata["pc"],
                    "price": jdata["pr"],
                    "order_type": jdata["pt"],
                    "quantity": jdata["qt"],
                    "validity": jdata["rt"],
                    "trading_symbol": jdata["ts"],
                    "transaction_type": jdata["tt"],
                    "amo": jdata["am"],
                    "disclosed_quantity": jdata["dq"],
                }
                return self._invoke_first(client, ["place_order", "order_place", "placeorder"], **sdk_payload)

        resp = self._with_auth_retry(_call_place, default_result=None, operation_name="place_order")
        if resp is _REAUTH_BLOCKED:
            raise RuntimeError("place_order failed: re-authentication blocked by failure rate")
        if resp is None:
            raise RuntimeError("Failed to place order: no response")

        if isinstance(resp, dict):
            if resp.get("stat") == "Ok" and int(resp.get("stCode", 200) or 200) == 200:
                n_ord_no = resp.get("nOrdNo") or resp.get("neoOrdNo")
                if n_ord_no:
                    return str(n_ord_no)
            if str(resp.get("status", "")).lower() == "success":
                n_ord_no = resp.get("neoOrdNo") or resp.get("nOrdNo")
                if n_ord_no:
                    return str(n_ord_no)
        raise RuntimeError(f"Failed to place order: {resp}")

    def cancel_order(self, order_id: str) -> bool:
        def _call_cancel():
            client = self._ensure_fresh_client()
            # REST shape first
            try:
                return self._invoke_first(client, ["cancel_order", "order_cancel", "cancelOrder"], order_id)
            except TypeError:
                return self._invoke_first(client, ["cancel_order"], order_no=order_id, amo="NO")

        try:
            resp = self._with_auth_retry(_call_cancel, default_result=False, operation_name="cancel_order")
        except BrokerServiceUnavailableError:
            return False
        if resp is _REAUTH_BLOCKED:
            return False

        if isinstance(resp, bool):
            return resp
        if isinstance(resp, dict):
            if resp.get("stat") == "Ok" and int(resp.get("stCode", 200) or 200) == 200:
                return True
            return str(resp.get("status", "")).lower() in {"ok", "success"}
        return False

    def get_order(self, order_id: str) -> Order | None:
        for o in self.get_all_orders():
            if o.order_id == order_id:
                return o
        return None

    def get_all_orders(self) -> list[Order]:
        def _call_orders():
            client = self._ensure_fresh_client()
            return self._invoke_first(
                client,
                ["order_report", "get_order_report", "orderBook", "orders", "get_order_book"],
            )

        try:
            resp = self._with_auth_retry(_call_orders, default_result=[], operation_name="get_all_orders")
        except BrokerServiceUnavailableError:
            return []
        if resp is _REAUTH_BLOCKED:
            return []
        data = self._extract_orders_data(resp)
        return self._parse_orders_response(data)

    def get_pending_orders(self) -> list[Order]:
        return [o for o in self.get_all_orders() if o.is_active()]

    def get_holdings(self) -> list[Holding]:
        def _call_holdings():
            client = self._ensure_fresh_client()
            return self._invoke_first(client, ["holdings", "get_holdings"])

        try:
            resp = self._with_auth_retry(_call_holdings, default_result=[], operation_name="get_holdings")
        except BrokerServiceUnavailableError:
            return []
        if resp is _REAUTH_BLOCKED:
            return []
        if isinstance(resp, dict):
            data = resp.get("data")
            if isinstance(data, list):
                return self._parse_holdings_response(data)
            return []
        return []

    def get_holding(self, symbol: str) -> Holding | None:
        needle = _normalize_symbol(symbol)
        for h in self.get_holdings():
            if _normalize_symbol(h.symbol) == needle:
                return h
        return None

    def get_account_limits(self) -> dict[str, Any]:
        def _call_limits():
            client = self._ensure_fresh_client()
            try:
                return self._invoke_first(client, ["limits"], segment="ALL", exchange="ALL", product="ALL")
            except Exception:
                try:
                    return self._invoke_first(client, ["limits", "get_limits"], seg="ALL", exch="ALL", prod="ALL")
                except Exception:
                    return self._invoke_first(client, ["limits", "get_limits"])

        try:
            resp = self._with_auth_retry(_call_limits, default_result={}, operation_name="get_account_limits")
        except BrokerServiceUnavailableError:
            return {}
        if resp is _REAUTH_BLOCKED:
            return {}
        if not isinstance(resp, dict):
            return {}
        if not resp:
            return {}

        available_cash = _to_float(resp.get("Net") or resp.get("net") or 0)
        margin_used = _to_float(resp.get("MarginUsed") or resp.get("marginUsed") or 0)
        collateral = _to_float(
            resp.get("CollateralValue")
            or resp.get("collateralValue")
            or resp.get("Collateral")
            or resp.get("collateral")
            or 0
        )

        return {
            "available_cash": Money.from_float(available_cash),
            "margin_used": Money.from_float(margin_used),
            "margin_available": Money.from_float(max(0.0, available_cash - margin_used)),
            "collateral": Money.from_float(collateral),
            "net": Money.from_float(available_cash),
        }

    def get_available_balance(self) -> Money:
        return self.get_account_limits().get("available_cash", Money.zero())

    def search_orders_by_symbol(self, symbol: str) -> list[Order]:
        needle = _normalize_symbol(symbol)
        return [o for o in self.get_all_orders() if _normalize_symbol(o.symbol) == needle]

    def cancel_pending_buys_for_symbol(self, symbol: str) -> int:
        cancelled = 0
        needle = _normalize_symbol(symbol)
        for o in self.get_pending_orders():
            if _normalize_symbol(o.symbol) == needle and o.is_buy_order() and o.order_id:
                if self.cancel_order(o.order_id):
                    cancelled += 1
        return cancelled

    def _build_place_order_jdata(self, order: Order) -> dict[str, str]:
        exchange_segment_map = {
            Exchange.NSE.value: "nse_cm",
            Exchange.BSE.value: "bse_cm",
            "NFO": "nse_fo",
            "BFO": "bse_fo",
            "CDS": "cde_fo",
            "MCX": "mcx_fo",
        }
        es = exchange_segment_map.get(order.exchange.value, order.exchange.value.lower())
        am = "YES" if order.variety == OrderVariety.AMO else "NO"
        pt = self._map_order_type(order.order_type)
        tt = "B" if order.transaction_type == TransactionType.BUY else "S"

        pr = "0"
        if order.order_type == OrderType.LIMIT:
            if not order.price:
                raise ValueError("Price required for LIMIT order")
            pr = str(order.price.amount)

        return {
            "am": am,
            "dq": "0",
            "es": es,
            "mp": "0",
            "pc": order.product_type.value,
            "pf": "N",
            "pr": pr,
            "pt": pt,
            "qt": str(int(order.quantity)),
            "rt": str(order.validity).upper(),
            "tp": "0",
            "ts": str(order.symbol).strip(),
            "tt": tt,
        }

    def _map_order_type(self, order_type: OrderType) -> str:
        mapping = {
            OrderType.MARKET: "MKT",
            OrderType.LIMIT: "L",
            OrderType.STOP_LOSS: "SL",
            OrderType.STOP_LOSS_MARKET: "SL-M",
        }
        return mapping.get(order_type, "MKT")

    def _parse_orders_response(self, data: list[dict[str, Any]]) -> list[Order]:
        orders: list[Order] = []
        for item in data:
            try:
                symbol = str(
                    item.get("trdSym")
                    or item.get("sym")
                    or item.get("tradingSymbol")
                    or item.get("symbol")
                    or ""
                ).strip()
                if not symbol:
                    continue

                raw_qty = item.get("qty") if item.get("qty") is not None else item.get("quantity")
                try:
                    qty_int = int(float(str(raw_qty)))
                except Exception:
                    # Keep parser strict on quantity rows; skip malformed rows.
                    continue
                if qty_int <= 0:
                    continue

                order_id = str(item.get("nOrdNo") or item.get("neoOrdNo") or item.get("orderId") or "")
                order_type_raw = str(item.get("prcTp") or item.get("orderType") or item.get("pt") or "MKT")
                trn_raw = str(item.get("trnsTp") or item.get("transactionType") or item.get("tt") or "B")
                status_raw = str(
                    item.get("ordSt")
                    or item.get("orderStatus")
                    or item.get("stat")
                    or item.get("status")
                    or "PENDING"
                )

                price_value = None
                prc = item.get("prc") if item.get("prc") is not None else item.get("price")
                if prc is not None:
                    prc_f = _to_float(prc, 0.0)
                    if prc_f > 0:
                        price_value = Money.from_float(prc_f)

                executed_price = None
                avg_prc = item.get("avgPrc") if item.get("avgPrc") is not None else item.get("executedPrice")
                if avg_prc is not None:
                    avg_f = _to_float(avg_prc, 0.0)
                    if avg_f > 0:
                        executed_price = Money.from_float(avg_f)

                executed_quantity = 0
                fld = item.get("fldQty") if item.get("fldQty") is not None else item.get("filledQty")
                if fld is not None:
                    try:
                        executed_quantity = int(float(str(fld)))
                    except Exception:
                        executed_quantity = 0

                created_at = None
                dt_raw = item.get("ordDtTm") or item.get("ordEntTm") or item.get("created_at")
                if dt_raw:
                    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M"):
                        try:
                            created_at = datetime.strptime(str(dt_raw), fmt)
                            break
                        except Exception:
                            continue

                order_type_obj = OrderType.from_string(order_type_raw)
                # If parsed as LIMIT but no price present, keep object valid by treating as MARKET.
                if order_type_obj == OrderType.LIMIT and price_value is None:
                    order_type_obj = OrderType.MARKET

                status = self._parse_order_status(status_raw)

                order = Order(
                    symbol=symbol,
                    quantity=qty_int,
                    order_type=order_type_obj,
                    transaction_type=TransactionType.from_string(trn_raw),
                    price=price_value,
                    order_id=order_id,
                    status=status,
                    placed_at=created_at,
                    created_at=created_at or datetime.now(),
                    executed_price=executed_price,
                    executed_quantity=executed_quantity,
                )
                orders.append(order)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Failed to parse order row: {e}")
                continue
        return orders

    def _parse_holdings_response(self, data: list[dict[str, Any]]) -> list[Holding]:
        holdings: list[Holding] = []
        for item in data:
            try:
                symbol = str(
                    item.get("displaySymbol")
                    or item.get("symbol")
                    or item.get("tradingSymbol")
                    or item.get("instrumentName")
                    or ""
                ).strip()
                if not symbol:
                    continue

                qty_raw = item.get("quantity") if item.get("quantity") is not None else item.get("qty")
                qty = int(float(str(qty_raw or 0)))
                avg = _to_float(item.get("averagePrice") if item.get("averagePrice") is not None else item.get("avgPrice"), 0.0)
                ltp = _to_float(item.get("closingPrice") if item.get("closingPrice") is not None else item.get("ltp"), 0.0)

                if ltp <= 0 and qty > 0:
                    mkt_value = _to_float(item.get("mktValue"), 0.0)
                    if mkt_value > 0:
                        ltp = mkt_value / float(qty)

                holdings.append(
                    Holding(
                        symbol=symbol,
                        quantity=qty,
                        average_price=Money.from_float(avg),
                        current_price=Money.from_float(ltp),
                        last_updated=datetime.now(),
                    )
                )
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Failed to parse holding row: {e}")
                continue
        return holdings

    def _parse_order_status(self, status: str) -> OrderStatus:
        s = (status or "").strip().lower()
        if "reject" in s:
            return OrderStatus.REJECTED
        if "cancel" in s:
            return OrderStatus.CANCELLED
        if "partial" in s:
            return OrderStatus.PARTIALLY_FILLED
        if "complete" in s or "execut" in s or "trade" in s or "fill" in s:
            return OrderStatus.EXECUTED
        if "open" in s:
            return OrderStatus.OPEN
        if "pending" in s or "trigger" in s or "received" in s:
            return OrderStatus.PENDING
        return OrderStatus.PENDING

