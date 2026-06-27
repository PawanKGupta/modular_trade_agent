"""
Trading Services Module

Centralized services for price fetching, indicators, portfolio management, etc.
These services eliminate duplicate code across trading services.
"""

from .capital_sizing_service import CapitalSizingService
from .indicator_service import IndicatorService, get_indicator_service
from .order_placement_service import OrderPlacementService
from .order_validation_service import (
    OrderValidationService,
    ValidationResult,
    get_order_validation_service,
)
from .portfolio_service import PortfolioService, get_portfolio_service
from .position_loader import PositionLoader, get_position_loader
from .position_monitor_service import PositionMonitorService
from .price_service import PriceService, get_price_service
from .sell_target_service import (
    PreparedSellLimit,
    compute_sell_target,
    fetch_circuit_limits_for_symbol,
    parse_circuit_limits_from_quote_payload,
    parse_circuit_limits_from_rejection,
    prepare_broker_sell_limit_price,
    round_sell_price,
    round_sell_price_down,
)
from .trade_history_store import DatabaseTradeHistoryStore, TradeHistoryStore

__all__ = [
    "PriceService",
    "get_price_service",
    "IndicatorService",
    "get_indicator_service",
    "PortfolioService",
    "get_portfolio_service",
    "PositionLoader",
    "get_position_loader",
    "OrderValidationService",
    "ValidationResult",
    "get_order_validation_service",
    "PreparedSellLimit",
    "compute_sell_target",
    "fetch_circuit_limits_for_symbol",
    "parse_circuit_limits_from_quote_payload",
    "parse_circuit_limits_from_rejection",
    "prepare_broker_sell_limit_price",
    "round_sell_price",
    "round_sell_price_down",
    "TradeHistoryStore",
    "DatabaseTradeHistoryStore",
    "CapitalSizingService",
    "OrderPlacementService",
    "PositionMonitorService",
]
