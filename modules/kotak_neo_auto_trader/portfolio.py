#!/usr/bin/env python3
"""
Portfolio Management Module for Kotak Neo (REST, SDK-free)

Used by higher-level services for holdings/positions.
"""

from __future__ import annotations

from utils.logger import logger

try:
    from .auth import KotakNeoAuth
    from .auth_handler import handle_reauth
except ImportError:  # pragma: no cover
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
    from modules.kotak_neo_auto_trader.auth_handler import handle_reauth


class KotakNeoPortfolio:
    def __init__(self, auth: KotakNeoAuth, price_manager=None):
        self.auth = auth
        self.price_manager = price_manager
        logger.info("KotakNeoPortfolio (REST) initialized")

    @handle_reauth
    def get_holdings(self) -> dict | None:
        """
        GET <baseUrl>/portfolio/v1/holdings
        """
        rest = self.auth.get_rest_client()
        try:
            return rest.get_holdings()
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error getting holdings: {e}")
            return None

    @handle_reauth
    def get_positions(self) -> dict | None:
        """
        GET <baseUrl>/quick/user/positions
        """
        rest = self.auth.get_rest_client()
        try:
            return rest.get_positions()
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error getting positions: {e}")
            return None

    @handle_reauth
    def get_limits(self) -> dict | None:
        """
        POST <baseUrl>/quick/user/limits (jData form field)
        """
        rest = self.auth.get_rest_client()
        try:
            return rest.get_limits(seg="ALL", exch="ALL", prod="ALL")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error getting limits: {e}")
            return None

