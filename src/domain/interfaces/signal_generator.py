"""
SignalGenerator Interface - Domain Layer

Abstract interface for generating trading signals from analysis data.
"""

from abc import ABC, abstractmethod
from typing import List
from ..entities.signal import Signal
from ..entities.analysis_result import AnalysisResult
from ..value_objects.indicators import IndicatorSet


class SignalGenerator(ABC):
    """
    Interface for generating trading signals
    
    This abstraction allows implementing different signal generation strategies
    without changing the core analysis logic.
    """
    
    @abstractmethod
    def generate_signal(
        self,
        ticker: str,
        indicators: IndicatorSet,
        current_price: float,
        **kwargs
    ) -> Signal:
        """
        Generate a trading signal based on indicators
        
        Args:
            ticker: Stock symbol
            indicators: Calculated technical indicators
            current_price: Current stock price
            **kwargs: Additional context (fundamentals, patterns, etc.)
            
        Returns:
            Generated Signal object
        """
        pass
    
    @abstractmethod
    def evaluate_signal_strength(self, signal: Signal) -> float:
        """
        Evaluate the strength/quality of a signal
        
        Args:
            signal: Signal to evaluate
            
        Returns:
            Strength score (0-100)
        """
        pass
    
    @abstractmethod
    def should_generate_alert(self, signal: Signal) -> bool:
        """
        Determine if signal warrants an alert
        
        Args:
            signal: Signal to check
            
        Returns:
            True if alert should be sent
        """
        pass
    
    @abstractmethod
    def get_signal_justifications(self, signal: Signal) -> List[str]:
        """
        Get human-readable justifications for the signal
        
        Args:
            signal: Signal to explain
            
        Returns:
            List of justification strings
        """
        pass
