#!/usr/bin/env python3
"""
Live Price Cache Service (REST polling)

Replaces SDK WebSocket dependency with periodic polling using Kotak Quotes REST API.

Public surface area kept compatible with existing callers:
- start(), stop()
- subscribe(symbols), unsubscribe(symbols)
- get_ltp(symbol)
- wait_for_connection(), wait_for_data()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from utils.logger import logger


@dataclass
class PriceData:
    ltp: float
    timestamp: datetime
    trading_symbol: str
    instrument_token: int


class LivePriceCache:
    def __init__(
        self,
        auth_client=None,  # kept for backward compatibility (ignored)
        scrip_master=None,
        stale_threshold_seconds: int = 60,
        reconnect_delay_seconds: int = 5,
        auth=None,
        poll_interval_seconds: float = 2.0,
    ):
        self.auth = auth
        # Backward compatibility for tests/callers that inspect current client object.
        self.client = auth_client
        self.scrip_master = scrip_master
        self.stale_threshold = timedelta(seconds=stale_threshold_seconds)
        self.reconnect_delay = reconnect_delay_seconds
        self.poll_interval = poll_interval_seconds

        self._cache: dict[str, PriceData] = {}
        self._cache_lock = threading.Lock()

        self._subscribed_tokens: list[dict] = []
        self._symbol_to_token: dict[str, int] = {}
        self._symbol_to_exchange_segment: dict[str, str] = {}

        self._running = threading.Event()
        self._shutdown = threading.Event()
        self._ws_connected = threading.Event()  # compatibility: indicates polling active + auth ok
        self._first_data_received = threading.Event()

        self._thread: threading.Thread | None = None

        logger.info("LivePriceCache initialized (REST polling)")

    # -------------------- lifecycle --------------------

    def start(self):
        if self._running.is_set():
            return
        self._shutdown.clear()
        self._running.set()
        self._ws_connected.clear()
        self._first_data_received.clear()

        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._shutdown.set()
        self._running.clear()
        self._ws_connected.clear()
        if self._thread:
            self._thread.join(timeout=5)
        self._thread = None

    def wait_for_connection(self, timeout: int = 10) -> bool:
        return self._ws_connected.wait(timeout=timeout)

    def wait_for_data(self, timeout: int = 10) -> bool:
        return self._first_data_received.wait(timeout=timeout)

    # -------------------- subscription --------------------

    def subscribe(self, symbols: list[str]):
        if not symbols:
            return
        if self.auth:
            try:
                if hasattr(self.auth, "get_client"):
                    self.client = self.auth.get_client()
                elif hasattr(self.auth, "get_rest_client"):
                    self.client = self.auth.get_rest_client()
            except Exception:
                pass
        if not self.scrip_master:
            raise RuntimeError("scrip_master required for LivePriceCache subscriptions")

        tokens_to_add = []
        for symbol in symbols:
            base_symbol = symbol.replace("-EQ", "").replace("-BE", "").strip()
            info = None
            if hasattr(self.scrip_master, "get_instrument"):
                info = self.scrip_master.get_instrument(symbol, exchange="NSE")
                if not info:
                    info = self.scrip_master.get_instrument(base_symbol, exchange="NSE")
            if not info:
                logger.debug(f"Symbol not found in scrip master: {symbol}")
                continue

            token = info.get("token") or info.get("instrumentToken") or info.get("pSymbol") or info.get("instrument_token")
            ex_seg = "nse_cm"
            try:
                token_int = int(str(token))
            except Exception:
                continue

            if symbol not in self._symbol_to_token:
                self._symbol_to_token[symbol] = token_int
                self._symbol_to_exchange_segment[symbol] = str(ex_seg)
                tokens_to_add.append({"instrument_token": token_int, "exchange_segment": str(ex_seg)})

        if tokens_to_add:
            self._subscribed_tokens.extend(tokens_to_add)

    def unsubscribe(self, symbols: list[str]):
        for symbol in symbols:
            self._symbol_to_token.pop(symbol, None)
            self._symbol_to_exchange_segment.pop(symbol, None)
        # Rebuild token list
        remaining = []
        seen = set(self._symbol_to_token.values())
        for tok in seen:
            remaining.append({"instrument_token": tok, "exchange_segment": "nse_cm"})
        self._subscribed_tokens = remaining

    # -------------------- access --------------------

    def get_ltp(self, symbol: str) -> float | None:
        with self._cache_lock:
            entry = self._cache.get(symbol)
            if not entry:
                return None
            if datetime.now() - entry.timestamp > self.stale_threshold:
                return None
            return entry.ltp

    # -------------------- polling loop --------------------

    def _poll_loop(self):
        while not self._shutdown.is_set():
            try:
                if not self.auth:
                    time.sleep(self.reconnect_delay)
                    continue

                # Mark "connected" once we can build a REST client
                rest = self.auth.get_rest_client()
                self.client = rest
                self._ws_connected.set()

                queries = []
                symbol_by_query = {}
                for sym, tok in list(self._symbol_to_token.items()):
                    ex_seg = self._symbol_to_exchange_segment.get(sym, "nse_cm")
                    q = f"{ex_seg}|{tok}"
                    queries.append(q)
                    symbol_by_query[q] = sym

                if not queries:
                    time.sleep(self.poll_interval)
                    continue

                # Fetch ltp for all subscribed instruments (batched)
                query_str = ",".join(queries)
                data = rest.get_quotes_neosymbol(query=query_str, filter_name="ltp")

                if isinstance(data, list):
                    now = datetime.now()
                    with self._cache_lock:
                        for item in data:
                            if not isinstance(item, dict):
                                continue
                            ex = item.get("exchange") or ""
                            tok = item.get("exchange_token") or ""
                            ltp = item.get("ltp")
                            try:
                                ltp_f = float(str(ltp))
                            except Exception:
                                continue
                            q = f"{ex}|{tok}"
                            sym = symbol_by_query.get(q)
                            if not sym:
                                # fallback: match by token only
                                for s, t in self._symbol_to_token.items():
                                    if str(t) == str(tok):
                                        sym = s
                                        break
                            if sym:
                                self._cache[sym] = PriceData(
                                    ltp=ltp_f,
                                    timestamp=now,
                                    trading_symbol=sym,
                                    instrument_token=int(str(tok)) if str(tok).isdigit() else 0,
                                )
                        if data:
                            self._first_data_received.set()

                time.sleep(self.poll_interval)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"LivePriceCache poll error: {e}")
                self._ws_connected.clear()
                time.sleep(self.reconnect_delay)

