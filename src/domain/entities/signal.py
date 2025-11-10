"""
Signal Entity - Domain Layer

Represents a trading signal with its verdict and justifications.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
from datetime import datetime


class SignalType(Enum):
    """Types of trading signals"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    WATCH = "watch"
    AVOID = "avoid"
    ERROR = "error"


class SignalStrength(Enum):
    """Signal strength levels"""
    EXCELLENT = "excellent"
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NONE = "none"


@dataclass
class Signal:
    """
    Trading signal entity
    
    Attributes:
        ticker: Stock symbol
        signal_type: Type of signal (buy, strong_buy, etc.)
        timestamp: When signal was generated
        justifications: List of reasons for the signal
        strength_score: Numerical strength score (0-100)
        confidence: Confidence level in the signal
        metadata: Additional signal metadata
    """
    ticker: str
    signal_type: SignalType
    timestamp: datetime
    justifications: List[str] = field(default_factory=list)
    strength_score: float = 0.0
    confidence: SignalStrength = SignalStrength.NONE
    metadata: dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate signal attributes"""
        if not self.ticker:
            raise ValueError("Ticker cannot be empty")
        if not 0 <= self.strength_score <= 100:
            raise ValueError("Strength score must be between 0 and 100")
    
    def is_buyable(self) -> bool:
        """Check if signal is a buy recommendation"""
        return self.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]
    
    def is_strong(self) -> bool:
        """Check if signal is strong buy"""
        return self.signal_type == SignalType.STRONG_BUY
    
    def add_justification(self, reason: str):
        """Add a justification for this signal"""
        if reason and reason not in self.justifications:
            self.justifications.append(reason)
    
    def get_summary(self) -> str:
        """Get human-readable signal summary"""
        return f"{self.signal_type.value.upper()}: {self.ticker} (Score: {self.strength_score:.1f})"
    
    def __str__(self) -> str:
        return f"Signal({self.ticker}, {self.signal_type.value}, {self.strength_score:.1f})"
    
    def __repr__(self) -> str:
        return self.__str__()
