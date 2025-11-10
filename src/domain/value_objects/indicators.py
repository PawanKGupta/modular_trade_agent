"""
Indicators Value Object - Domain Layer

Immutable value object containing technical indicator calculations.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RSIIndicator:
    """RSI indicator result"""
    value: float
    period: int = 10
    
    def __post_init__(self):
        """Validate RSI"""
        if not 0 <= self.value <= 100:
            raise ValueError("RSI must be between 0 and 100")
        if self.period <= 0:
            raise ValueError("RSI period must be positive")
    
    def is_oversold(self, threshold: float = 30) -> bool:
        """Check if RSI indicates oversold condition"""
        return self.value < threshold
    
    def is_overbought(self, threshold: float = 70) -> bool:
        """Check if RSI indicates overbought condition"""
        return self.value > threshold
    
    def is_extremely_oversold(self) -> bool:
        """Check if RSI is extremely oversold (< 20)"""
        return self.value < 20
    
    def get_severity(self) -> str:
        """Get oversold severity level"""
        if self.value < 10:
            return "extreme"
        elif self.value < 20:
            return "high"
        elif self.value < 30:
            return "moderate"
        else:
            return "none"
    
    def __str__(self) -> str:
        return f"RSI({self.period})={self.value:.2f}"


@dataclass(frozen=True)
class EMAIndicator:
    """EMA indicator result"""
    value: float
    period: int = 200
    
    def __post_init__(self):
        """Validate EMA"""
        if self.value < 0:
            raise ValueError("EMA cannot be negative")
        if self.period <= 0:
            raise ValueError("EMA period must be positive")
    
    def is_price_above(self, price: float) -> bool:
        """Check if price is above EMA"""
        return price > self.value
    
    def get_distance_percentage(self, price: float) -> float:
        """Get percentage distance from price to EMA"""
        if self.value == 0:
            return 0.0
        return ((price - self.value) / self.value) * 100
    
    def __str__(self) -> str:
        return f"EMA({self.period})={self.value:.2f}"


@dataclass(frozen=True)
class SupportResistanceLevel:
    """Support or resistance level"""
    level: float
    strength: str = "moderate"  # weak, moderate, strong
    distance_pct: float = 0.0
    
    def __post_init__(self):
        """Validate support/resistance level"""
        if self.level < 0:
            raise ValueError("Level cannot be negative")
        if self.strength not in ["weak", "moderate", "strong"]:
            raise ValueError("Strength must be weak, moderate, or strong")
    
    def is_near(self, price: float, threshold_pct: float = 2.0) -> bool:
        """Check if price is near this level"""
        if self.level == 0:
            return False
        distance = abs((price - self.level) / self.level) * 100
        return distance <= threshold_pct
    
    def is_strong(self) -> bool:
        """Check if this is a strong level"""
        return self.strength == "strong"
    
    def __str__(self) -> str:
        return f"{self.level:.2f} ({self.strength})"


@dataclass(frozen=True)
class IndicatorSet:
    """
    Complete set of technical indicators
    
    Attributes:
        rsi: RSI indicator
        ema: EMA indicator
        support: Support level
        resistance: Resistance level
        volume_ratio: Current volume / average volume
    """
    rsi: Optional[RSIIndicator] = None
    ema: Optional[EMAIndicator] = None
    support: Optional[SupportResistanceLevel] = None
    resistance: Optional[SupportResistanceLevel] = None
    volume_ratio: float = 1.0
    
    def is_complete(self) -> bool:
        """Check if all critical indicators are available"""
        return self.rsi is not None and self.ema is not None
    
    def meets_reversal_criteria(self) -> bool:
        """Check if indicators meet reversal setup criteria"""
        if not self.is_complete():
            return False
        
        # RSI < 30 and price > EMA200
        return (self.rsi.is_oversold() and 
                self.volume_ratio >= 0.8)
    
    def get_signal_strength(self) -> int:
        """Calculate signal strength score (0-10)"""
        score = 0
        
        if self.rsi and self.rsi.is_extremely_oversold():
            score += 3
        elif self.rsi and self.rsi.is_oversold():
            score += 2
        
        if self.volume_ratio >= 1.5:
            score += 2
        elif self.volume_ratio >= 1.0:
            score += 1
        
        if self.support and self.support.is_strong():
            score += 2
        elif self.support:
            score += 1
        
        return min(score, 10)
    
    def __str__(self) -> str:
        parts = []
        if self.rsi:
            parts.append(str(self.rsi))
        if self.ema:
            parts.append(str(self.ema))
        if self.support:
            parts.append(f"Support: {self.support}")
        return ", ".join(parts) if parts else "No indicators"
