#!/usr/bin/env python3
"""
Market Data Module for Kotak Neo (REST, SDK-free)

Quotes endpoint uses access token only:
GET <baseUrl>/script-details/1.0/quotes/neosymbol/<query>/<filter>
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from utils.logger import logger

try:
    from .auth import KotakNeoAuth
    from .auth_handler import handle_reauth
except ImportError:  # pragma: no cover
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
    from modules.kotak_neo_auto_trader.auth_handler import handle_reauth


class KotakNeoMarketData:
    def __init__(self, auth: KotakNeoAuth):
        self.auth = auth
        logger.info("KotakNeoMarketData (REST) initialized")

    @handle_reauth
    def get_quote(self, query: str, filter_name: str = "all") -> Optional[Any]:
        """
        query examples:
        - "nse_cm|Nifty 50"
        - "nse_cm|11536"
        - "nse_cm|Nifty 50,nse_cm|Nifty Bank"
        """
        rest = self.auth.get_rest_client()
        try:
            return rest.get_quotes_neosymbol(query=query, filter_name=filter_name)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error fetching quotes for {query}: {e}")
            return None

    def get_ltp(self, exchange_segment: str, instrument: str) -> Optional[float]:
        """
        Convenience wrapper to get LTP for a single instrument.
        instrument can be:
        - pSymbol token (recommended for equities)
        - index name (case-sensitive)
        """
        q = f"{exchange_segment}|{instrument}"
        data = self.get_quote(q, filter_name="ltp")
        try:
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                return float(str(data[0].get("ltp") or 0)) or None
        except Exception:
            return None
        return None

