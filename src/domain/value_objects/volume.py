"""
Volume Value Object - Domain Layer

Immutable value object representing trading volume with quality assessment.
"""

from dataclasses import dataclass
from enum import Enum


class VolumeQuality(Enum):
    """Volume quality levels"""
    EXCELLENT = "excellent"  # >= 1.5x average
    GOOD = "good"            # >= 1.0x average
    FAIR = "fair"            # >= 0.6x average
    LOW = "low"              # < 0.6x average
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Volume:
    """
    Immutable volume value object
    
    Attributes:
        value: The volume value (number of shares)
        average: Average volume for comparison (optional)
    """
    value: int
    average: int = 0
    
    def __post_init__(self):
        """Validate volume"""
        if self.value < 0:
            raise ValueError("Volume cannot be negative")
        if self.average < 0:
            raise ValueError("Average volume cannot be negative")
    
    def get_ratio(self) -> float:
        """Get volume ratio compared to average"""
        if self.average == 0:
            return 1.0
        return self.value / self.average
    
    def get_quality(self) -> VolumeQuality:
        """Assess volume quality based on ratio to average"""
        if self.average == 0:
            return VolumeQuality.UNKNOWN
        
        ratio = self.get_ratio()
        
        if ratio >= 1.5:
            return VolumeQuality.EXCELLENT
        elif ratio >= 1.0:
            return VolumeQuality.GOOD
        elif ratio >= 0.6:
            return VolumeQuality.FAIR
        else:
            return VolumeQuality.LOW
    
    def is_sufficient(self, threshold: float = 0.8) -> bool:
        """Check if volume meets minimum threshold"""
        return self.get_ratio() >= threshold
    
    def is_strong(self) -> bool:
        """Check if volume is strong (above average)"""
        return self.get_ratio() >= 1.2
    
    def is_weak(self) -> bool:
        """Check if volume is weak (below threshold)"""
        return self.get_ratio() < 0.6
    
    def __eq__(self, other) -> bool:
        """Compare volumes"""
        if isinstance(other, Volume):
            return self.value == other.value
        elif isinstance(other, int):
            return self.value == other
        return False
    
    def __lt__(self, other) -> bool:
        """Less than comparison"""
        if isinstance(other, Volume):
            return self.value < other.value
        elif isinstance(other, int):
            return self.value < other
        return NotImplemented
    
    def __gt__(self, other) -> bool:
        """Greater than comparison"""
        if isinstance(other, Volume):
            return self.value > other.value
        elif isinstance(other, int):
            return self.value > other
        return NotImplemented
    
    def format_with_suffix(self) -> str:
        """Format volume with K/M/B suffix"""
        value = self.value
        if value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        elif value >= 1_000:
            return f"{value / 1_000:.2f}K"
        else:
            return str(value)
    
    def __str__(self) -> str:
        return f"{self.format_with_suffix()}"
    
    def __repr__(self) -> str:
        return f"Volume({self.value}, avg={self.average})"
