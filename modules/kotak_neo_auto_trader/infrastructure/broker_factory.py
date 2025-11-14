"""
Broker Factory
Creates appropriate broker adapter based on configuration
"""

from typing import Optional, Literal
from enum import Enum

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger

from ..domain import IBrokerGateway
from ..config.paper_trading_config import PaperTradingConfig
from .broker_adapters import KotakNeoBrokerAdapter, PaperTradingBrokerAdapter


class BrokerType(Enum):
    """Supported broker types"""
    KOTAK_NEO = "kotak_neo"
    PAPER_TRADING = "paper_trading"


class BrokerFactory:
    """
    Factory for creating broker adapters

    Simplifies broker creation and switching between
    paper trading and live trading.
    """

    @staticmethod
    def create_broker(
        broker_type: str,
        auth_handler=None,
        paper_config: Optional[PaperTradingConfig] = None
    ) -> IBrokerGateway:
        """
        Create a broker adapter

        Args:
            broker_type: Type of broker ("kotak_neo" or "paper_trading")
            auth_handler: Authentication handler (for Kotak Neo)
            paper_config: Configuration (for paper trading)

        Returns:
            Broker adapter implementing IBrokerGateway

        Raises:
            ValueError: If broker_type is invalid or required params missing

        Examples:
            # Paper trading
            broker = BrokerFactory.create_broker(
                "paper_trading",
                paper_config=PaperTradingConfig(initial_capital=100000.0)
            )

            # Real trading
            broker = BrokerFactory.create_broker(
                "kotak_neo",
                auth_handler=auth_handler
            )
        """
        broker_type = broker_type.lower()

        if broker_type == "paper_trading":
            return BrokerFactory._create_paper_trading_broker(paper_config)

        elif broker_type == "kotak_neo":
            return BrokerFactory._create_kotak_neo_broker(auth_handler)

        else:
            raise ValueError(
                f"Unknown broker type: {broker_type}. "
                f"Supported: 'paper_trading', 'kotak_neo'"
            )

    @staticmethod
    def _create_paper_trading_broker(
        config: Optional[PaperTradingConfig] = None
    ) -> PaperTradingBrokerAdapter:
        """Create paper trading broker"""
        if config is None:
            config = PaperTradingConfig.default()
            logger.info("📋 Using default paper trading configuration")

        logger.info(
            f"🎯 Creating paper trading broker "
            f"(Capital: ₹{config.initial_capital:,.2f})"
        )

        return PaperTradingBrokerAdapter(config)

    @staticmethod
    def _create_kotak_neo_broker(auth_handler) -> KotakNeoBrokerAdapter:
        """Create Kotak Neo broker"""
        if auth_handler is None:
            raise ValueError("auth_handler is required for Kotak Neo broker")

        logger.info("🎯 Creating Kotak Neo broker")
        return KotakNeoBrokerAdapter(auth_handler)

    @staticmethod
    def create_from_env(env_key: str = "BROKER_TYPE") -> IBrokerGateway:
        """
        Create broker from environment variable

        Args:
            env_key: Environment variable name (default: BROKER_TYPE)

        Returns:
            Broker adapter

        Environment Variables:
            BROKER_TYPE: "paper_trading" or "kotak_neo"
            PAPER_TRADING_CAPITAL: Initial capital (optional)
            PAPER_TRADING_PATH: Storage path (optional)
        """
        import os

        broker_type = os.getenv(env_key, "paper_trading")

        if broker_type == "paper_trading":
            # Load config from environment
            initial_capital = float(
                os.getenv("PAPER_TRADING_CAPITAL", "100000.0")
            )
            storage_path = os.getenv(
                "PAPER_TRADING_PATH",
                "paper_trading/data"
            )

            config = PaperTradingConfig(
                initial_capital=initial_capital,
                storage_path=storage_path
            )

            return BrokerFactory.create_broker("paper_trading", paper_config=config)

        else:
            # For real broker, need to initialize auth_handler
            # This is application-specific
            raise NotImplementedError(
                "Real broker creation from env requires custom implementation"
            )


def create_paper_broker(
    initial_capital: float = 100000.0,
    **kwargs
) -> PaperTradingBrokerAdapter:
    """
    Convenience function to create paper trading broker

    Args:
        initial_capital: Starting capital
        **kwargs: Additional config parameters

    Returns:
        Paper trading broker

    Example:
        broker = create_paper_broker(
            initial_capital=50000.0,
            enable_slippage=True,
            enable_fees=True
        )
    """
    config = PaperTradingConfig(initial_capital=initial_capital, **kwargs)
    return PaperTradingBrokerAdapter(config)


def create_live_broker(auth_handler) -> KotakNeoBrokerAdapter:
    """
    Convenience function to create live trading broker

    Args:
        auth_handler: Authentication handler

    Returns:
        Kotak Neo broker

    Example:
        from modules.kotak_neo_auto_trader.infrastructure.session import AuthHandler

        auth = AuthHandler(...)
        broker = create_live_broker(auth)
    """
    return KotakNeoBrokerAdapter(auth_handler)

