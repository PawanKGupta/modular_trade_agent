"""
AnalysisResult Entity - Domain Layer

Represents the complete analysis result for a stock including technical indicators,
signals, and trading parameters.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from .signal import Signal


@dataclass
class TradingParameters:
    """Trading parameters for a stock"""
    buy_range_low: float
    buy_range_high: float
    target: float
    stop_loss: float
    potential_gain_pct: float
    potential_loss_pct: float
    risk_reward_ratio: float
    
    def __post_init__(self):
        """Validate trading parameters"""
        if self.buy_range_low <= 0 or self.buy_range_high <= 0:
            raise ValueError("Buy range must be positive")
        if self.target <= 0 or self.stop_loss <= 0:
            raise ValueError("Target and stop loss must be positive")
        if self.buy_range_low > self.buy_range_high:
            raise ValueError("Buy range low cannot be greater than high")


@dataclass
class TechnicalIndicators:
    """Technical indicator values"""
    rsi: Optional[float] = None
    ema_200: Optional[float] = None
    volume_ratio: Optional[float] = None
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    
    def is_complete(self) -> bool:
        """Check if all critical indicators are available"""
        return all([
            self.rsi is not None,
            self.ema_200 is not None,
            self.volume_ratio is not None
        ])


@dataclass
class FundamentalData:
    """Fundamental data for a stock"""
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    market_cap: Optional[float] = None
    
    def has_negative_earnings(self) -> bool:
        """Check if stock has negative earnings"""
        return self.pe_ratio is not None and self.pe_ratio < 0


@dataclass
class AnalysisResult:
    """
    Complete analysis result for a stock
    
    Attributes:
        ticker: Stock symbol
        status: Analysis status (success, error, etc.)
        signal: Generated trading signal
        timestamp: When analysis was performed
        technical_indicators: Technical indicator values
        fundamental_data: Fundamental metrics
        trading_params: Trading parameters (buy/sell levels)
        mtf_alignment_score: Multi-timeframe alignment score (0-10)
        backtest_score: Historical backtest performance score
        combined_score: Combined current + historical score
        priority_score: Trading priority score
        error_message: Error message if analysis failed
        metadata: Additional analysis metadata
    """
    ticker: str
    status: str
    timestamp: datetime
    signal: Optional[Signal] = None
    technical_indicators: Optional[TechnicalIndicators] = None
    fundamental_data: Optional[FundamentalData] = None
    trading_params: Optional[TradingParameters] = None
    mtf_alignment_score: float = 0.0
    backtest_score: float = 0.0
    combined_score: float = 0.0
    priority_score: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_success(self) -> bool:
        """Check if analysis was successful"""
        return self.status == "success" and self.signal is not None
    
    def is_buyable(self) -> bool:
        """Check if stock is buyable based on signal"""
        return self.is_success() and self.signal.is_buyable()
    
    def is_strong_buy(self) -> bool:
        """Check if stock is strong buy"""
        return self.is_success() and self.signal.is_strong()
    
    def has_error(self) -> bool:
        """Check if analysis encountered an error"""
        return self.status != "success" or self.error_message is not None
    
    def get_verdict(self) -> str:
        """Get the analysis verdict"""
        if self.signal:
            return self.signal.signal_type.value
        return "unknown"
    
    def __str__(self) -> str:
        verdict = self.get_verdict() if self.is_success() else self.status
        return f"AnalysisResult({self.ticker}, {verdict}, score={self.combined_score:.1f})"
    
    def __repr__(self) -> str:
        return self.__str__()
