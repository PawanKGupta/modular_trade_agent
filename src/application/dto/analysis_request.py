"""
Analysis Request DTOs

Data transfer objects for analysis requests.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class AnalysisRequest:
    """
    Request for stock analysis
    
    Attributes:
        ticker: Stock symbol to analyze
        enable_multi_timeframe: Enable MTF analysis
        enable_backtest: Enable backtest scoring
        export_to_csv: Export results to CSV
        dip_mode: Enable dip-buying mode
        end_date: Analysis end date (None = today)
    """
    ticker: str
    enable_multi_timeframe: bool = True
    enable_backtest: bool = False
    export_to_csv: bool = True
    dip_mode: bool = False
    end_date: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate request"""
        if not self.ticker:
            raise ValueError("Ticker is required")
        self.ticker = self.ticker.strip().upper()


@dataclass
class BulkAnalysisRequest:
    """
    Request for bulk stock analysis
    
    Attributes:
        tickers: List of stock symbols
        enable_multi_timeframe: Enable MTF analysis
        enable_backtest: Enable backtest scoring
        export_to_csv: Export results to CSV
        dip_mode: Enable dip-buying mode
        min_combined_score: Minimum combined score filter
    """
    tickers: list[str]
    enable_multi_timeframe: bool = True
    enable_backtest: bool = False
    export_to_csv: bool = True
    dip_mode: bool = False
    min_combined_score: float = 25.0
    
    def __post_init__(self):
        """Validate and clean tickers"""
        if not self.tickers:
            raise ValueError("At least one ticker is required")
        self.tickers = [t.strip().upper() for t in self.tickers if t.strip()]


@dataclass
class BacktestRequest:
    """
    Request for strategy backtesting
    
    Attributes:
        ticker: Stock symbol
        start_date: Backtest start date
        end_date: Backtest end date
        capital_per_position: Capital per position
        rsi_period: RSI calculation period
        ema_period: EMA calculation period
        max_positions: Maximum positions allowed
        enable_pyramiding: Enable pyramiding
    """
    ticker: str
    start_date: datetime
    end_date: datetime
    capital_per_position: float = 100000.0
    rsi_period: int = 10
    ema_period: int = 200
    max_positions: int = 10
    enable_pyramiding: bool = True
    
    def __post_init__(self):
        """Validate request"""
        if not self.ticker:
            raise ValueError("Ticker is required")
        if self.start_date >= self.end_date:
            raise ValueError("Start date must be before end date")
        if self.capital_per_position <= 0:
            raise ValueError("Capital must be positive")
