"""
Paper Trading Configuration
Settings for paper trading simulation
"""

from dataclasses import dataclass, field
from typing import Dict, Any
import json
from pathlib import Path


@dataclass
class PaperTradingConfig:
    """
    Configuration for paper trading simulation

    Controls capital, fees, execution behavior, and storage settings
    """

    # ===== CAPITAL SETTINGS =====
    initial_capital: float = 100000.0  # Starting cash in INR

    # ===== EXECUTION SETTINGS =====
    enable_slippage: bool = True  # Simulate realistic slippage
    slippage_percentage: float = 0.2  # Default slippage ±0.2%
    slippage_range: tuple = (0.1, 0.3)  # Random range for slippage

    execution_delay_ms: int = 100  # Simulate network latency (ms)
    enable_partial_fills: bool = False  # Allow partial order fills

    # ===== MARKET HOURS =====
    enforce_market_hours: bool = True  # Block orders outside market hours
    market_open_time: str = "09:15"  # Market opening time
    market_close_time: str = "15:30"  # Market closing time
    allow_amo_orders: bool = True  # Allow After Market Orders
    amo_execution_time: str = "09:15"  # When AMO orders execute

    # ===== FEES & CHARGES (in percentage) =====
    enable_fees: bool = True  # Simulate brokerage and taxes
    brokerage_percentage: float = 0.03  # 0.03% brokerage
    stt_percentage: float = 0.1  # 0.1% STT on sell side
    transaction_charges_percentage: float = 0.00325  # 0.00325% transaction charges
    gst_percentage: float = 18.0  # 18% GST on brokerage
    sebi_charges_percentage: float = 0.0001  # SEBI charges
    stamp_duty_percentage: float = 0.003  # Stamp duty on buy side

    # ===== RISK MANAGEMENT =====
    max_position_size: float = 50000.0  # Max value per position
    max_portfolio_value: float = 200000.0  # Max total portfolio value (including leverage)
    check_sufficient_funds: bool = True  # Reject orders if insufficient funds

    # ===== PERSISTENCE =====
    storage_path: str = "paper_trading/data"  # Where to store data files
    auto_save: bool = True  # Auto-save after each transaction
    backup_enabled: bool = True  # Create backups
    max_backups: int = 10  # Max number of backups to keep

    # ===== PRICE FEED =====
    price_source: str = "live"  # "live", "historical", or "mock"
    price_cache_duration_seconds: int = 5  # Cache price for N seconds

    # ===== LOGGING =====
    log_all_operations: bool = True  # Log all operations
    verbose_logging: bool = False  # Extra detailed logs

    # ===== SIMULATION MODE =====
    simulation_speed: float = 1.0  # Speed multiplier (1.0 = real-time)
    instant_execution: bool = False  # Execute orders instantly (no delay)

    def __post_init__(self):
        """Validate configuration"""
        if self.initial_capital <= 0:
            raise ValueError("Initial capital must be positive")

        if self.slippage_percentage < 0:
            raise ValueError("Slippage percentage cannot be negative")

        if self.max_position_size > self.initial_capital * 2:
            raise ValueError("Max position size too large relative to capital")

    def get_total_charges_percentage(self, is_buy: bool = True) -> float:
        """
        Calculate total charges percentage

        Args:
            is_buy: True for buy orders, False for sell orders

        Returns:
            Total charges as percentage
        """
        if not self.enable_fees:
            return 0.0

        total = 0.0

        # Brokerage (both sides)
        brokerage = self.brokerage_percentage
        total += brokerage

        # GST on brokerage
        gst = (brokerage * self.gst_percentage) / 100
        total += gst

        # Transaction charges (both sides)
        total += self.transaction_charges_percentage

        # SEBI charges (both sides)
        total += self.sebi_charges_percentage

        if is_buy:
            # Stamp duty on buy side only
            total += self.stamp_duty_percentage
        else:
            # STT on sell side only
            total += self.stt_percentage

        return total

    def calculate_charges(self, order_value: float, is_buy: bool = True) -> float:
        """
        Calculate total charges for an order

        Args:
            order_value: Total order value in INR
            is_buy: True for buy orders, False for sell orders

        Returns:
            Total charges in INR
        """
        charge_percentage = self.get_total_charges_percentage(is_buy)
        return (order_value * charge_percentage) / 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "initial_capital": self.initial_capital,
            "enable_slippage": self.enable_slippage,
            "slippage_percentage": self.slippage_percentage,
            "execution_delay_ms": self.execution_delay_ms,
            "enable_fees": self.enable_fees,
            "enforce_market_hours": self.enforce_market_hours,
            "storage_path": self.storage_path,
            "price_source": self.price_source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PaperTradingConfig':
        """Create configuration from dictionary"""
        return cls(**data)

    def save_to_file(self, filepath: Path) -> None:
        """Save configuration to JSON file"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, filepath: Path) -> 'PaperTradingConfig':
        """Load configuration from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def default(cls) -> 'PaperTradingConfig':
        """Get default configuration"""
        return cls()

    @classmethod
    def minimal_fees(cls) -> 'PaperTradingConfig':
        """Configuration with minimal fees for testing"""
        return cls(enable_fees=False, enable_slippage=False)

    @classmethod
    def realistic(cls) -> 'PaperTradingConfig':
        """Configuration with realistic market conditions"""
        return cls(
            enable_fees=True,
            enable_slippage=True,
            enforce_market_hours=True,
            check_sufficient_funds=True,
        )

