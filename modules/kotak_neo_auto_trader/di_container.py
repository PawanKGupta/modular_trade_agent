"""
Dependency Injection Container
Wires together all layers of the Clean Architecture
"""

from dataclasses import dataclass
from decimal import Decimal

# Application
from .application import GetHoldingsUseCase, OrderSizingService, PlaceOrderUseCase, TradingConfig

# Domain
from .domain import IBrokerGateway, Money

# Infrastructure
from .infrastructure import KotakNeoAuth, KotakNeoBrokerAdapter, MockBrokerAdapter, config


@dataclass
class KotakNeoContainer:
    """
    Dependency Injection Container for Kotak Neo module

    Provides factory methods for all dependencies, ensuring
    single instances (singleton pattern) where appropriate.
    """

    def __init__(
        self, env_file: str = "kotak_neo.env", use_mock: bool = False, strategy_config=None
    ):
        """
        Initialize container

        Args:
            env_file: Path to environment file with credentials
            use_mock: If True, uses MockBrokerAdapter instead of real broker
            strategy_config: Optional user StrategyConfig instance
        """
        self.env_file = env_file
        self.use_mock = use_mock
        self.strategy_config = strategy_config

        # Cached instances (singletons)
        self._broker_gateway: IBrokerGateway | None = None
        self._auth_handler: KotakNeoAuth | None = None
        self._trading_config: TradingConfig | None = None
        self._order_sizing_service: OrderSizingService | None = None

    # Configuration

    def get_trading_config(self) -> TradingConfig:
        """Get trading configuration"""
        if not self._trading_config:
            max_order_val = config.MAX_ORDER_VALUE
            if self.strategy_config and hasattr(self.strategy_config, "max_order_value"):
                val = self.strategy_config.max_order_value

                if isinstance(val, (int, float, Decimal)):
                    max_order_val = val

            self._trading_config = TradingConfig(
                capital_per_trade=Money.from_int(config.CAPITAL_PER_TRADE),
                min_quantity=1,
                max_quantity=100000,
                max_order_value=Money.from_float(max_order_val),
            )
        return self._trading_config

    # Infrastructure

    def get_auth_handler(self) -> KotakNeoAuth:
        """Get authentication handler"""
        if not self._auth_handler:
            self._auth_handler = KotakNeoAuth(self.env_file)
        return self._auth_handler

    def get_broker_gateway(self) -> IBrokerGateway:
        """
        Get broker gateway

        Returns MockBrokerAdapter if use_mock=True, otherwise KotakNeoBrokerAdapter
        """
        if not self._broker_gateway:
            if self.use_mock:
                self._broker_gateway = MockBrokerAdapter()
            else:
                auth = self.get_auth_handler()
                self._broker_gateway = KotakNeoBrokerAdapter(auth)
        return self._broker_gateway

    # Application Services

    def get_order_sizing_service(self) -> OrderSizingService:
        """Get order sizing service"""
        if not self._order_sizing_service:
            self._order_sizing_service = OrderSizingService(config=self.get_trading_config())
        return self._order_sizing_service

    # Use Cases

    def get_place_order_use_case(self) -> PlaceOrderUseCase:
        """Get place order use case"""
        return PlaceOrderUseCase(broker_gateway=self.get_broker_gateway())

    def get_get_holdings_use_case(self) -> GetHoldingsUseCase:
        """Get holdings use case"""
        return GetHoldingsUseCase(broker_gateway=self.get_broker_gateway())

    # Convenience Methods

    def connect(self) -> bool:
        """Connect to broker"""
        return self.get_broker_gateway().connect()

    def disconnect(self) -> bool:
        """Disconnect from broker"""
        return self.get_broker_gateway().disconnect()

    def is_connected(self) -> bool:
        """Check if connected to broker"""
        return self.get_broker_gateway().is_connected()


# Factory function for easy instantiation
def create_container(
    env_file: str = "kotak_neo.env", use_mock: bool = False, strategy_config=None
) -> KotakNeoContainer:
    """
    Factory function to create a configured container

    Args:
        env_file: Path to environment file
        use_mock: If True, uses mock broker for testing
        strategy_config: Optional user StrategyConfig instance

    Returns:
        Configured KotakNeoContainer
    """
    return KotakNeoContainer(env_file=env_file, use_mock=use_mock, strategy_config=strategy_config)
