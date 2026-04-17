from __future__ import annotations

"""
Kotak Neo REST client (SDK-free).

Important: Kotak uses TWO kinds of auth headers:

- **Post-login trade APIs** (orders/reports/portfolio/limits/etc.)
  - Auth: <session token from tradeApiValidate>
  - Sid:  <session sid from tradeApiValidate>
  - neo-fin-key: neotradeapi

- **Quotes + Scripmaster**
  - Authorization: <access token from dashboard> (plain, no Bearer)
  - (no neo-fin-key, no Auth/Sid)
"""

import json
from typing import Any, Dict, Optional

import requests


class KotakRestClient:
    def __init__(
        self,
        *,
        base_url: str,
        session_token: str,
        session_sid: str,
        access_token: str,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session_token = session_token.strip()
        self.session_sid = session_sid.strip()
        self.access_token = access_token.strip()
        self.timeout = timeout

    # -------------------- Headers --------------------

    def _trade_headers(self, include_form: bool = False) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "accept": "application/json",
            "Auth": self.session_token,
            "Sid": self.session_sid,
            "neo-fin-key": "neotradeapi",
        }
        if include_form:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        return headers

    def _access_headers(self) -> Dict[str, str]:
        return {
            "Authorization": self.access_token,
            "Content-Type": "application/json",
        }

    # -------------------- Helpers --------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _post_form_jdata(self, path: str, jdata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Kotak expects: Content-Type application/x-www-form-urlencoded with a single field `jData`,
        where jData is a *stringified JSON object*.
        """
        url = self._url(path)
        headers = self._trade_headers(include_form=True)
        resp = requests.post(
            url,
            headers=headers,
            data={"jData": json.dumps(jdata, separators=(",", ":"))},
            timeout=self.timeout,
        )
        return resp.json()

    # -------------------- Orders --------------------

    def place_order(self, jdata: Dict[str, Any]) -> Dict[str, Any]:
        return self._post_form_jdata("/quick/order/rule/ms/place", jdata=jdata)

    def modify_order(self, jdata: Dict[str, Any]) -> Dict[str, Any]:
        return self._post_form_jdata("/quick/order/vr/modify", jdata=jdata)

    def cancel_order(self, order_no: str, amo: str = "NO") -> Dict[str, Any]:
        return self._post_form_jdata("/quick/order/cancel", jdata={"on": order_no, "am": amo})

    def exit_cover_order(self, order_no: str, amo: str = "NO") -> Dict[str, Any]:
        return self._post_form_jdata("/quick/order/co/exit", jdata={"on": order_no, "am": amo})

    def exit_bracket_order(self, order_no: str, amo: str = "NO") -> Dict[str, Any]:
        return self._post_form_jdata("/quick/order/bo/exit", jdata={"on": order_no, "am": amo})

    # -------------------- Reports --------------------

    def get_order_book(self) -> Dict[str, Any]:
        url = self._url("/quick/user/orders")
        resp = requests.get(url, headers=self._trade_headers(include_form=False), timeout=self.timeout)
        return resp.json()

    def get_order_history(self, order_no: str) -> Dict[str, Any]:
        return self._post_form_jdata("/quick/order/history", jdata={"nOrdNo": order_no})

    def get_trade_book(self) -> Dict[str, Any]:
        url = self._url("/quick/user/trades")
        resp = requests.get(url, headers=self._trade_headers(include_form=False), timeout=self.timeout)
        return resp.json()

    # -------------------- Portfolio / Positions --------------------

    def get_positions(self) -> Dict[str, Any]:
        url = self._url("/quick/user/positions")
        resp = requests.get(url, headers=self._trade_headers(include_form=False), timeout=self.timeout)
        return resp.json()

    def get_holdings(self) -> Dict[str, Any]:
        url = self._url("/portfolio/v1/holdings")
        resp = requests.get(url, headers=self._trade_headers(include_form=False), timeout=self.timeout)
        return resp.json()

    # -------------------- Limits / Margin --------------------

    def get_limits(self, seg: str = "ALL", exch: str = "ALL", prod: str = "ALL") -> Dict[str, Any]:
        return self._post_form_jdata("/quick/user/limits", jdata={"seg": seg, "exch": exch, "prod": prod})

    def check_margin(self, jdata: Dict[str, Any]) -> Dict[str, Any]:
        return self._post_form_jdata("/quick/user/check-margin", jdata=jdata)

    # -------------------- Quotes / Scripmaster (access token only) --------------------

    def get_scripmaster_file_paths(self) -> Any:
        url = self._url("/script-details/1.0/masterscrip/file-paths")
        resp = requests.get(url, headers={"Authorization": self.access_token}, timeout=self.timeout)
        return resp.json()

    def get_quotes_neosymbol(self, query: str, filter_name: str = "all") -> Any:
        """
        query examples:
        - "nse_cm|Nifty 50"
        - "nse_cm|26000"
        - "nse_cm|Nifty 50,nse_cm|Nifty Bank"
        """
        url = self._url(f"/script-details/1.0/quotes/neosymbol/{query}/{filter_name}")
        resp = requests.get(url, headers={"Authorization": self.access_token}, timeout=self.timeout)
        return resp.json()

