#!/usr/bin/env python3
"""
Broker API Response Normalizer Utility
Normalizes inconsistent broker API responses to consistent format
"""

from typing import Any


class BrokerResponseNormalizer:
    """
    Normalize broker API responses to consistent format.

    The Kotak Neo API uses inconsistent field names across different endpoints.
    This utility provides a consistent interface for extracting order data.
    """

    # Field mapping: normalized_field -> list of broker field names (in priority order)
    ORDER_FIELD_MAPPING = {
        "order_id": ["neoOrdNo", "nOrdNo", "orderId", "order_id"],
        "symbol": ["trdSym", "tradingSymbol", "symbol"],
        "status": ["orderStatus", "ordSt", "status"],
        "transaction_type": ["transactionType", "trnsTp", "txnType", "txn_type"],
        "quantity": ["qty", "quantity", "fldQty", "filledQty", "filled_qty"],
        "price": ["avgPrc", "prc", "price", "executedPrice", "executed_price"],
        "order_type": ["orderType", "ordTyp", "order_type"],
        "product_type": ["productType", "prdTyp", "product_type"],
        "exchange": ["exchange", "exch", "exchangeSegment"],
        "order_time": ["orderTime", "ordTm", "order_time", "timestamp"],
        "disclosed_quantity": ["disclosedQty", "disclosed_qty", "dscQty"],
        "trigger_price": ["triggerPrice", "trigger_price", "trgPrc"],
        "validity": ["validity", "validityType", "validity_type"],
    }

    @classmethod
    def normalize_order(cls, order: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize order dict to consistent format.

        Args:
            order: Raw order dict from broker API

        Returns:
            Normalized order dict with consistent field names
        """
        normalized = {}

        # Extract fields using mapping
        for normalized_field, broker_fields in cls.ORDER_FIELD_MAPPING.items():
            value = cls._extract_field(order, broker_fields)
            if value is not None:
                normalized[normalized_field] = value

        # Preserve original fields for backward compatibility
        normalized["_original"] = order.copy()

        return normalized

    @classmethod
    def normalize_order_list(cls, orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Normalize list of orders.

        Args:
            orders: List of raw order dicts

        Returns:
            List of normalized order dicts
        """
        return [cls.normalize_order(order) for order in orders]

    @classmethod
    def _extract_field(
        cls, data: dict[str, Any], field_names: list[str], default: Any = None
    ) -> Any:
        """
        Extract field from data trying multiple field names.

        Args:
            data: Data dict to extract from
            field_names: List of field names to try (in priority order)
            default: Default value if field not found

        Returns:
            Field value or default
        """
        for field_name in field_names:
            if field_name in data:
                value = data[field_name]
                if value is not None:
                    return value
        return default

    @classmethod
    def get_order_id(cls, order: dict[str, Any]) -> str:
        """Extract order ID from normalized or raw order"""
        if "order_id" in order:
            return str(order["order_id"])
        return str(cls._extract_field(order, cls.ORDER_FIELD_MAPPING["order_id"], ""))

    @classmethod
    def get_symbol(cls, order: dict[str, Any]) -> str:
        """Extract symbol from normalized or raw order"""
        if "symbol" in order and order["symbol"] not in cls.ORDER_FIELD_MAPPING["symbol"]:
            return str(order["symbol"])
        return str(cls._extract_field(order, cls.ORDER_FIELD_MAPPING["symbol"], ""))

    @classmethod
    def get_status(cls, order: dict[str, Any]) -> str:
        """Extract status from normalized or raw order"""
        if "status" in order and order["status"] not in cls.ORDER_FIELD_MAPPING["status"]:
            return str(order["status"])
        return str(cls._extract_field(order, cls.ORDER_FIELD_MAPPING["status"], ""))

    @classmethod
    def get_transaction_type(cls, order: dict[str, Any]) -> str:
        """Extract transaction type from normalized or raw order"""
        if "transaction_type" in order:
            return str(order["transaction_type"]).upper()
        return str(
            cls._extract_field(order, cls.ORDER_FIELD_MAPPING["transaction_type"], "")
        ).upper()

    @classmethod
    def get_quantity(cls, order: dict[str, Any]) -> int:
        """Extract quantity from normalized or raw order"""
        if "quantity" in order and isinstance(order["quantity"], (int, float)):
            return int(order["quantity"])
        value = cls._extract_field(order, cls.ORDER_FIELD_MAPPING["quantity"], 0)
        return int(value) if value else 0

    @classmethod
    def get_price(cls, order: dict[str, Any]) -> float:
        """Extract price from normalized or raw order"""
        if "price" in order and isinstance(order["price"], (int, float)):
            return float(order["price"])
        value = cls._extract_field(order, cls.ORDER_FIELD_MAPPING["price"], 0)
        return float(value) if value else 0.0

