"""
Typed Data Classes for Analysis Results

Replaces dict-based results with type-safe dataclasses.
Provides better IDE support, type checking, and runtime validation.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from enum import Enum


class Verdict(str, Enum):
    """Trading verdict types"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    WATCH = "watch"
    AVOID = "avoid"


@dataclass
class TradingParameters:
    """Trading parameters (buy range, target, stop)"""
    buy_range: Optional[Tuple[float, float]] = None
    target: Optional[float] = None
    stop: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility"""
        return {
            'buy_range': self.buy_range,
            'target': self.target,
            'stop': self.stop
        }


@dataclass
class Indicators:
    """Technical indicators"""
    rsi: Optional[float] = None
    ema200: Optional[float] = None
    avg_vol: Optional[int] = None
    today_vol: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility"""
        return {
            'rsi': self.rsi,
            'ema200': self.ema200,
            'avg_vol': self.avg_vol,
            'today_vol': self.today_vol
        }


@dataclass
class Fundamentals:
    """Fundamental data"""
    pe: Optional[float] = None
    pb: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility"""
        return {
            'pe': self.pe,
            'pb': self.pb
        }


@dataclass
class AnalysisResult:
    """
    Type-safe analysis result
    
    Replaces dict-based results with a proper dataclass for better
    type safety, IDE autocomplete, and runtime validation.
    """
    ticker: str
    verdict: Verdict
    status: str = "success"
    
    # Signals and indicators
    signals: List[str] = field(default_factory=list)
    indicators: Optional[Indicators] = None
    fundamentals: Optional[Fundamentals] = None
    
    # Trading parameters
    trading_params: Optional[TradingParameters] = None
    
    # Analysis metadata
    last_close: float = 0.0
    justification: List[str] = field(default_factory=list)
    timeframe_analysis: Optional[Dict[str, Any]] = None
    news_sentiment: Optional[Dict[str, Any]] = None
    volume_analysis: Optional[Dict[str, Any]] = None
    volume_pattern: Optional[Dict[str, Any]] = None
    volume_description: Optional[str] = None
    candle_analysis: Optional[Dict[str, Any]] = None
    
    # Scoring (added after initial analysis)
    strength_score: Optional[float] = None
    backtest_score: Optional[float] = None
    combined_score: Optional[float] = None
    priority_score: Optional[float] = None
    
    # Timestamps
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Error handling
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for backward compatibility with existing code.
        
        This allows gradual migration - new code uses AnalysisResult,
        legacy code can use .to_dict() to get the old dict format.
        """
        result = {
            'ticker': self.ticker,
            'verdict': self.verdict.value,
            'status': self.status,
            'signals': self.signals,
            'last_close': self.last_close,
            'justification': self.justification,
            'timeframe_analysis': self.timeframe_analysis,
            'news_sentiment': self.news_sentiment,
            'volume_analysis': self.volume_analysis,
            'volume_pattern': self.volume_pattern,
            'volume_description': self.volume_description,
            'candle_analysis': self.candle_analysis,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }
        
        # Add indicators if available
        if self.indicators:
            result.update(self.indicators.to_dict())
        
        # Add fundamentals if available
        if self.fundamentals:
            result.update(self.fundamentals.to_dict())
        
        # Add trading parameters if available
        if self.trading_params:
            result.update(self.trading_params.to_dict())
        
        # Add scoring if available
        if self.strength_score is not None:
            result['strength_score'] = self.strength_score
        if self.backtest_score is not None:
            result['backtest_score'] = self.backtest_score
        if self.combined_score is not None:
            result['combined_score'] = self.combined_score
        if self.priority_score is not None:
            result['priority_score'] = self.priority_score
        
        # Add error if present
        if self.error:
            result['error'] = self.error
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalysisResult':
        """
        Create AnalysisResult from dictionary (for backward compatibility)
        
        Args:
            data: Dictionary with analysis result data
            
        Returns:
            AnalysisResult instance
        """
        # Extract indicators
        indicators = None
        if any(key in data for key in ['rsi', 'ema200', 'avg_vol', 'today_vol']):
            indicators = Indicators(
                rsi=data.get('rsi'),
                ema200=data.get('ema200'),
                avg_vol=data.get('avg_vol'),
                today_vol=data.get('today_vol')
            )
        
        # Extract fundamentals
        fundamentals = None
        if any(key in data for key in ['pe', 'pb']):
            fundamentals = Fundamentals(
                pe=data.get('pe'),
                pb=data.get('pb')
            )
        
        # Extract trading parameters
        trading_params = None
        if any(key in data for key in ['buy_range', 'target', 'stop']):
            trading_params = TradingParameters(
                buy_range=data.get('buy_range'),
                target=data.get('target'),
                stop=data.get('stop')
            )
        
        # Parse verdict
        verdict_str = data.get('verdict', 'avoid')
        try:
            verdict = Verdict(verdict_str)
        except ValueError:
            verdict = Verdict.AVOID
        
        # Parse timestamp if available
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()
        
        return cls(
            ticker=data.get('ticker', ''),
            verdict=verdict,
            status=data.get('status', 'success'),
            signals=data.get('signals', []),
            indicators=indicators,
            fundamentals=fundamentals,
            trading_params=trading_params,
            last_close=data.get('last_close', 0.0),
            justification=data.get('justification', []),
            timeframe_analysis=data.get('timeframe_analysis'),
            news_sentiment=data.get('news_sentiment'),
            volume_analysis=data.get('volume_analysis'),
            volume_pattern=data.get('volume_pattern'),
            volume_description=data.get('volume_description'),
            candle_analysis=data.get('candle_analysis'),
            strength_score=data.get('strength_score'),
            backtest_score=data.get('backtest_score'),
            combined_score=data.get('combined_score'),
            priority_score=data.get('priority_score'),
            timestamp=timestamp,
            error=data.get('error')
        )
    
    def is_buyable(self) -> bool:
        """Check if result represents a buyable stock"""
        return self.verdict in [Verdict.BUY, Verdict.STRONG_BUY]
    
    def is_success(self) -> bool:
        """Check if analysis was successful"""
        return self.status == 'success'
    
    def __repr__(self) -> str:
        return f"AnalysisResult(ticker={self.ticker}, verdict={self.verdict.value}, status={self.status})"

