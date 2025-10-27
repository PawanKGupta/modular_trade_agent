"""
Kotak Neo Auto Trader Module
Modular implementation for portfolio management and trading operations

Provides both:
1. Legacy API (KotakNeoTrader, etc.) - backward compatible
2. Clean Architecture API (via di_container) - recommended for new code
"""

# Legacy imports for backward compatibility
from .trader import KotakNeoTrader
from .auth import KotakNeoAuth
from .portfolio import KotakNeoPortfolio
from .orders import KotakNeoOrders
from .auto_trade_engine import AutoTradeEngine
from . import config

# Clean Architecture imports (NEW)
from .di_container import KotakNeoContainer, create_container
from .domain import (
    Order, Holding, Money,
    OrderType, TransactionType, OrderStatus,
    ProductType, OrderVariety, Exchange,
    IBrokerGateway
)
from .application import (
    OrderRequest, OrderResponse, HoldingsResponse,
    PlaceOrderUseCase, GetHoldingsUseCase,
    OrderSizingService, TradingConfig
)
from .infrastructure import (
    KotakNeoBrokerAdapter, MockBrokerAdapter
)

# Version info
__version__ = "2.0.0"  # Major version bump for Clean Architecture
__author__ = "Trading Agent"

# Export all classes
__all__ = [
    # Legacy API (deprecated but maintained for compatibility)
    "KotakNeoTrader",
    "KotakNeoAuth", 
    "KotakNeoPortfolio",
    "KotakNeoOrders",
    "AutoTradeEngine",
    "config",
    
    # Clean Architecture API (recommended)
    # Container
    "KotakNeoContainer",
    "create_container",
    # Domain
    "Order",
    "Holding",
    "Money",
    "OrderType",
    "TransactionType",
    "OrderStatus",
    "ProductType",
    "OrderVariety",
    "Exchange",
    "IBrokerGateway",
    # Application
    "OrderRequest",
    "OrderResponse",
    "HoldingsResponse",
    "PlaceOrderUseCase",
    "GetHoldingsUseCase",
    "OrderSizingService",
    "TradingConfig",
    # Infrastructure
    "KotakNeoBrokerAdapter",
    "MockBrokerAdapter",
]
