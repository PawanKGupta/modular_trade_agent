#!/usr/bin/env python3
"""
Order Field Extractor Utility
Centralized order field extraction with fallback logic for broker API inconsistencies
"""

from typing import Any

EOD_DAY_BUY_CANCEL_REASON = (
    "Unexecuted DAY/REGULAR buy cancelled at session close (EOD cleanup)"
)


class OrderFieldExtractor:
    """
    Centralized order field extraction with fallback logic.

    Handles inconsistent broker API field names by trying multiple
    field name variations and returning the first match.
    """

    @staticmethod
    def get_order_id(order: dict[str, Any]) -> str:
        """
        Extract order ID with fallbacks.

        Args:
            order: Order dict from broker API

        Returns:
            Order ID as string, empty string if not found
        """
        return str(
            order.get("neoOrdNo")
            or order.get("nOrdNo")
            or order.get("orderId")
            or order.get("order_id")
            or ""
        )

    @staticmethod
    def get_symbol(order: dict[str, Any]) -> str:
        """
        Extract trading symbol with fallbacks.

        Args:
            order: Order dict from broker API

        Returns:
            Trading symbol (e.g., 'DALBHARAT-EQ'), empty string if not found
        """
        return order.get("trdSym") or order.get("tradingSymbol") or order.get("symbol") or ""

    @staticmethod
    def get_transaction_type(order: dict[str, Any]) -> str:
        """
        Extract transaction type (BUY/SELL) with fallbacks.

        Args:
            order: Order dict from broker API

        Returns:
            Transaction type uppercase ('BUY' or 'SELL'), empty string if not found
        """
        return (
            order.get("transactionType") or order.get("trnsTp") or order.get("txnType") or ""
        ).upper()

    @staticmethod
    def get_status(order: dict[str, Any]) -> str:
        """
        Extract order status with fallbacks.

        Args:
            order: Order dict from broker API

        Returns:
            Order status lowercase, empty string if not found
        """
        # Check multiple field names, including 'stat' from order_report API
        return (
            order.get("orderStatus")
            or order.get("ordSt")
            or order.get("stat")  # Add 'stat' field from order_report API
            or order.get("status")
            or ""
        ).lower()

    @staticmethod
    def get_quantity(order: dict[str, Any]) -> int:
        """
        Extract order quantity (not filled quantity) with fallbacks.

        Args:
            order: Order dict from broker API

        Returns:
            Order quantity as integer, 0 if not found
        """
        return int(order.get("qty") or order.get("quantity") or order.get("orderQty") or 0)

    @staticmethod
    def get_filled_quantity(order: dict[str, Any]) -> int:
        """
        Extract filled quantity (actual executed quantity) with fallbacks.

        Args:
            order: Order dict from broker API

        Returns:
            Filled quantity as integer, 0 if not found
        """
        return int(
            order.get("fldQty")
            or order.get("filledQty")
            or order.get("filled_quantity")
            or order.get("executedQty")
            or order.get("executed_qty")
            or 0
        )

    @staticmethod
    def get_price(order: dict[str, Any]) -> float:
        """
        Extract price with fallbacks.

        Args:
            order: Order dict from broker API

        Returns:
            Price as float, 0.0 if not found
        """
        return float(
            order.get("avgPrc")
            or order.get("prc")
            or order.get("price")
            or order.get("executedPrice")
            or order.get("executed_price")
            or 0.0
        )

    @staticmethod
    def get_rejection_reason(order: dict[str, Any]) -> str:
        """
        Extract rejection reason with fallbacks.

        Args:
            order: Order dict from broker API

        Returns:
            Rejection reason, empty string if not found
        """
        return order.get("rejRsn") or order.get("rejectionReason") or order.get("rmk") or ""

    @staticmethod
    def get_order_time(order: dict[str, Any]) -> str | None:
        """
        Extract order time/date with fallbacks.

        Args:
            order: Order dict from broker API

        Returns:
            Order time string, None if not found
        """
        return (
            order.get("ordDtTm")
            or order.get("orderTime")
            or order.get("order_time")
            or order.get("timestamp")
            or order.get("executionTime")
            or None
        )

    @staticmethod
    def is_buy_order(order: dict[str, Any]) -> bool:
        """
        Check if order is a BUY order.

        Args:
            order: Order dict from broker API

        Returns:
            True if BUY order, False otherwise
        """
        txn_type = OrderFieldExtractor.get_transaction_type(order)
        return txn_type in ["B", "BUY"]

    @staticmethod
    def is_sell_order(order: dict[str, Any]) -> bool:
        """
        Check if order is a SELL order.

        Args:
            order: Order dict from broker API

        Returns:
            True if SELL order, False otherwise
        """
        txn_type = OrderFieldExtractor.get_transaction_type(order)
        return txn_type in ["S", "SELL"]

    @staticmethod
    def is_pending_open_buy_order(order: dict[str, Any]) -> bool:
        """
        True if broker order is an open/pending BUY eligible for pre-market adjustment.

        Includes AMO and REGULAR pending buys (DAY validity). Excludes IOC and sells.
        """
        if not OrderFieldExtractor.is_buy_order(order):
            return False

        status = OrderFieldExtractor.get_status(order)
        if not any(
            token in status
            for token in ("open", "pending", "trigger", "req received", "reqreceived")
        ):
            return False

        validity = str(
            order.get("orderValidity")
            or order.get("ordValidity")
            or order.get("validity")
            or order.get("rt")
            or "DAY"
        ).upper()
        if validity == "IOC":
            return False

        return True

    @staticmethod
    def is_amo_broker_order(order: dict[str, Any]) -> bool:
        """
        Return True when a broker order dict represents an AMO (after-market) order.

        AMO pending buys are intentionally carried overnight for 9:05 adjustment.
        """
        amo_val = str(
            order.get("am") or order.get("amo") or order.get("AM") or ""
        ).upper()
        if amo_val in ("YES", "Y", "TRUE", "1"):
            return True
        variety = str(
            order.get("variety")
            or order.get("ordVariety")
            or order.get("ordSrc")
            or order.get("orderSource")
            or ""
        ).upper()
        return variety in ("AMO", "AFTER_MARKET", "AFTER MARKET")

    @staticmethod
    def is_eod_cancellable_day_buy_broker_order(order: dict[str, Any]) -> bool:
        """
        Return True for open/pending REGULAR/DAY buys that must not carry overnight.

        Excludes AMO (carried for pre-market adjustment) and IOC intraday orders.
        """
        if not OrderFieldExtractor.is_pending_open_buy_order(order):
            return False
        return not OrderFieldExtractor.is_amo_broker_order(order)

    @staticmethod
    def is_amo_db_order(db_order: Any) -> bool:
        """Return True when a persisted order row represents an AMO buy."""
        if db_order is None:
            return False
        reason = getattr(db_order, "reason", None) or ""
        if "AMO" in str(reason).upper():
            return True
        metadata = getattr(db_order, "order_metadata", None)
        if isinstance(metadata, dict):
            variety = str(metadata.get("variety") or metadata.get("order_variety") or "").upper()
            if variety == "AMO":
                return True
        return False

    @staticmethod
    def is_eod_cancellable_day_buy_db_order(db_order: Any) -> bool:
        """Return True for PENDING non-AMO buy rows that should be cleared at EOD."""
        if db_order is None or getattr(db_order, "side", None) != "buy":
            return False
        status = getattr(db_order, "status", None)
        status_val = getattr(status, "value", status)
        if str(status_val).upper() != "PENDING":
            return False
        return not OrderFieldExtractor.is_amo_db_order(db_order)
