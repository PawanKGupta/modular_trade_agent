#!/usr/bin/env python3
"""
Market Data Module for Kotak Neo (REST, SDK-free)

Quotes endpoint uses access token only:
GET <baseUrl>/script-details/1.0/quotes/neosymbol/<query>/<filter>
"""

from __future__ import annotations

from typing import Any, Optional

from utils.logger import logger

from modules.kotak_neo_auto_trader.utils.market_depth_utils import (
    DepthLevel,
    MarketDepthSnapshot,
    extract_best_ask_from_quote_payload,
    extract_market_depth_from_quote_payload,
)

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

    def get_market_depth(
        self, instrument_token: str, *, exchange_segment: str = "nse_cm"
    ) -> MarketDepthSnapshot:
        """
        Fetch up to five bid and ask levels (``filter=all`` → ``depth.buy`` / ``depth.sell``).

        Log-only helper for 9:05 observability.
        """
        query = f"{exchange_segment}|{instrument_token}"
        data = self.get_quote(query, filter_name="all")
        return extract_market_depth_from_quote_payload(data)

    def get_sell_depth(
        self, instrument_token: str, *, exchange_segment: str = "nse_cm"
    ) -> tuple[DepthLevel | None, ...]:
        """Ask levels from :meth:`get_market_depth`."""
        return self.get_market_depth(
            instrument_token, exchange_segment=exchange_segment
        ).ask_levels

    def get_buy_depth(
        self, instrument_token: str, *, exchange_segment: str = "nse_cm"
    ) -> tuple[DepthLevel | None, ...]:
        """Bid levels from :meth:`get_market_depth`."""
        return self.get_market_depth(
            instrument_token, exchange_segment=exchange_segment
        ).bid_levels

    def get_best_ask(
        self, instrument_token: str, *, exchange_segment: str = "nse_cm"
    ) -> DepthLevel | None:
        """First non-zero ask level from :meth:`get_market_depth`."""
        for level in self.get_sell_depth(
            instrument_token, exchange_segment=exchange_segment
        ):
            if level is not None:
                return level
        return None

