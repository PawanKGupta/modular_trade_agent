# ruff: noqa: PLR0912, PLR0915, PLC0415, PLC0207, PLR2004
"""
Concrete implementation of CapitalSizingService.
"""

from math import floor
from typing import Any

from src.domain.interfaces.capital_sizing_service import ICapitalSizingService
from utils.logger import logger


class CapitalSizingService(ICapitalSizingService):
    """Concrete implementation of ICapitalSizingService."""

    def __init__(self, portfolio=None, auth=None, scrip_master=None, strategy_config=None):
        self.portfolio = portfolio
        self.auth = auth
        self.scrip_master = scrip_master
        self.strategy_config = strategy_config

    def get_affordable_qty(self, price: float) -> int:
        if not self.portfolio or not price or price <= 0:
            return 0
        lim = self.portfolio.get_limits() or {}
        avail, used_key = self._extract_available_cash_from_limits(lim)
        logger.debug(
            f"Available balance: Rs {avail:.2f} (from limits API; key={used_key or 'n/a'})"
        )
        try:
            return max(0, floor(avail / float(price)))
        except Exception:
            return 0

    def get_available_cash(self) -> float:
        if not self.portfolio:
            return 0.0
        lim = self.portfolio.get_limits() or {}
        avail, used_key = self._extract_available_cash_from_limits(lim)
        logger.debug(f"Available cash from limits API: Rs {avail:.2f} (key={used_key or 'n/a'})")
        return float(avail)

    def _extract_available_cash_from_limits(self, limits_payload: Any) -> tuple[float, str | None]:
        if not isinstance(limits_payload, dict):
            return 0.0, None

        candidates = [
            "cash",
            "availableCash",
            "available_cash",
            "availableBalance",
            "available_balance",
            "available_bal",
            "fundsAvailable",
            "funds_available",
            "fundAvailable",
            "marginAvailable",
            "margin_available",
            "availableMargin",
            "Net",
            "net",
        ]

        def _to_num(raw: Any) -> float | None:
            try:
                if raw is None:
                    return None
                if hasattr(raw, "amount"):
                    raw = raw.amount
                if isinstance(raw, str):
                    s = raw.replace(",", "").strip()
                    if s.lower().startswith("rs"):
                        s = s[2:].strip(" .:")
                    if not s:
                        return None
                    return float(s)
                return float(raw)
            except Exception:
                return None

        payloads: list[tuple[str, dict[str, Any]]] = []
        data = limits_payload.get("data")
        if isinstance(data, dict):
            payloads.append(("data.", data))
        payloads.append(("", limits_payload))

        for prefix, payload in payloads:
            for key in candidates:
                value = _to_num(payload.get(key))
                if value is not None and value > 0:
                    return value, f"{prefix}{key}"

            nums: list[float] = []
            for value in payload.values():
                num = _to_num(value)
                if num is not None:
                    nums.append(num)
            if nums:
                return max(nums), f"{prefix}max_numeric_field"

        return 0.0, None

    def check_order_margin(
        self,
        symbol: str,
        price: float,
        qty: int,
        transaction_type: str = "B",
        product: str = "CNC",
    ) -> tuple[bool, float, float, float, bool]:
        required_cash = max(0.0, float(price) * float(qty))

        try:
            if not self.auth or not hasattr(self.auth, "get_rest_client"):
                raise RuntimeError("REST client unavailable")
            rest = self.auth.get_rest_client()
            if not rest:
                raise RuntimeError("REST client unavailable")

            token = None
            if self.scrip_master:
                token = self.scrip_master.get_token(symbol, exchange="NSE")
                if not token and "-" in symbol:
                    token = self.scrip_master.get_token(symbol.split("-")[0], exchange="NSE")
            if not token:
                raise RuntimeError(f"instrument token unavailable for {symbol}")

            ex_seg = "nse_cm"
            prc_tp = "MKT" if float(price) <= 0 else "L"
            jdata = {
                "brkName": "KOTAK",
                "brnchId": "ONLINE",
                "exSeg": ex_seg,
                "prc": str(0 if prc_tp == "MKT" else float(price)),
                "prcTp": prc_tp,
                "prod": product,
                "qty": str(int(qty)),
                "tok": str(token),
                "trnsTp": "B" if str(transaction_type).upper().startswith("B") else "S",
            }

            resp = rest.check_margin(jdata) or {}
            if not isinstance(resp, dict):
                raise RuntimeError(f"invalid check-margin response type: {type(resp)}")

            def _to_num(v: Any, default: float = 0.0) -> float:
                try:
                    if v is None:
                        return default
                    return float(str(v).replace(",", "").strip())
                except Exception:
                    return default

            body: dict[str, Any] = resp
            data_node = resp.get("data")
            if isinstance(data_node, dict):
                body = data_node
            elif isinstance(data_node, list) and data_node and isinstance(data_node[0], dict):
                body = data_node[0]

            def _first(*keys: str, source: dict[str, Any]) -> Any:
                for key in keys:
                    if key in source and source.get(key) is not None:
                        return source.get(key)
                return None

            avl_raw = _first("avlCash", "availableCash", "cash", "netCash", source=body)
            if avl_raw is None:
                avl_raw = _first("avlCash", "availableCash", "cash", "netCash", source=resp)

            req_raw = _first("reqdMrgn", "requiredMargin", "reqMargin", "ordMrgn", source=body)
            if req_raw is None:
                req_raw = _first("reqdMrgn", "requiredMargin", "reqMargin", "ordMrgn", source=resp)

            insuf_raw = _first("insufFund", "insufficientFund", "shortfall", source=body)
            if insuf_raw is None:
                insuf_raw = _first("insufFund", "insufficientFund", "shortfall", source=resp)

            rms_raw = _first("rmsVldtd", "rmsValidated", source=body)
            if rms_raw is None:
                rms_raw = _first("rmsVldtd", "rmsValidated", source=resp)

            stat_raw = _first("stat", "status", source=resp)
            if stat_raw is None:
                stat_raw = _first("stat", "status", source=body)

            stcode_raw = _first("stCode", "statusCode", "code", source=resp)
            if stcode_raw is None:
                stcode_raw = _first("stCode", "statusCode", "code", source=body)

            avl_cash = _to_num(avl_raw, 0.0)
            req_margin = _to_num(req_raw, required_cash)
            insuf_fund = _to_num(insuf_raw, max(0.0, req_margin - avl_cash))
            rms_valid = str(rms_raw or "").upper().strip()
            stat_ok = str(stat_raw or "").lower().strip() in {"ok", "success", "true"}
            stcode = str(stcode_raw or "").strip()
            has_sufficient = bool(
                stat_ok
                and stcode in {"200", "0", ""}
                and (rms_valid == "OK" or insuf_fund <= 0.0 or avl_cash >= req_margin)
            )
            margin_api_ok = bool(stat_ok and stcode in {"200", "0", ""})
            shortfall = max(0.0, insuf_fund if insuf_fund > 0 else (req_margin - avl_cash))
            logger.debug(
                f"check-margin {symbol}: sufficient={has_sufficient}, avlCash={avl_cash:.2f}, "
                f"reqdMrgn={req_margin:.2f}, shortfall={shortfall:.2f}, "
                f"rmsVldtd={rms_valid or 'n/a'}"
            )
            return has_sufficient, avl_cash, req_margin, shortfall, margin_api_ok

        except Exception as e:
            logger.error(f"check-margin failed for {symbol}: {e}")
            return False, 0.0, 0.0, 0.0, False

    def calculate_execution_capital(self, ticker: str, close: float, avg_volume: float) -> float:
        if not self.strategy_config:
            return 0.0
        try:
            from services.liquidity_capital_service import LiquidityCapitalService

            liquidity_service = LiquidityCapitalService(config=self.strategy_config)
            capital_data = liquidity_service.calculate_execution_capital(
                avg_volume=avg_volume, stock_price=close
            )
            execution_capital = capital_data.get(
                "execution_capital", self.strategy_config.user_capital
            )

            if execution_capital <= 0:
                execution_capital = self.strategy_config.user_capital

            return execution_capital
        except Exception as e:
            logger.warning(
                f"Failed to calculate execution capital for {ticker}: {e}, "
                "using user_capital from config"
            )
            return self.strategy_config.user_capital
