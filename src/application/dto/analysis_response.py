"""
Analysis Response DTOs

Data transfer objects for analysis responses.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from ...domain.entities.analysis_result import AnalysisResult


@dataclass
class AnalysisResponse:
    """
    Response from stock analysis
    
    Attributes:
        ticker: Stock symbol
        status: Analysis status (success, error)
        verdict: Trading verdict (strong_buy, buy, watch, avoid)
        timestamp: Analysis timestamp
        last_close: Last closing price
        buy_range: Buy range (low, high)
        target: Target price
        stop_loss: Stop loss price
        rsi: RSI value
        mtf_alignment_score: Multi-timeframe score
        backtest_score: Backtest performance score
        combined_score: Combined current + historical score
        priority_score: Trading priority score
        error_message: Error message if failed
        metadata: Additional data
    """
    ticker: str
    status: str
    timestamp: datetime
    verdict: str = "unknown"
    final_verdict: Optional[str] = None  # Verdict after backtest reclassification
    last_close: float = 0.0
    buy_range: Optional[tuple[float, float]] = None
    target: Optional[float] = None
    stop_loss: Optional[float] = None
    rsi: Optional[float] = None
    mtf_alignment_score: float = 0.0
    backtest_score: float = 0.0
    combined_score: float = 0.0
    priority_score: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Chart quality and capital fields
    chart_quality: Optional[Dict[str, Any]] = None
    execution_capital: float = 0.0
    max_capital: float = 0.0
    capital_adjusted: bool = False
    
    @classmethod
    def from_analysis_result(cls, result: AnalysisResult) -> 'AnalysisResponse':
        """Create response from domain entity"""
        buy_range = None
        target = None
        stop_loss = None
        
        if result.trading_params:
            buy_range = (
                result.trading_params.buy_range_low,
                result.trading_params.buy_range_high
            )
            target = result.trading_params.target
            stop_loss = result.trading_params.stop_loss
        
        rsi = None
        if result.technical_indicators and result.technical_indicators.rsi:
            rsi = result.technical_indicators.rsi
        
        return cls(
            ticker=result.ticker,
            status=result.status,
            timestamp=result.timestamp,
            verdict=result.get_verdict(),
            last_close=result.metadata.get('last_close', 0.0),
            buy_range=buy_range,
            target=target,
            stop_loss=stop_loss,
            rsi=rsi,
            mtf_alignment_score=result.mtf_alignment_score,
            backtest_score=result.backtest_score,
            combined_score=result.combined_score,
            priority_score=result.priority_score,
            error_message=result.error_message,
            metadata=result.metadata
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'ticker': self.ticker,
            'status': self.status,
            'verdict': self.verdict,
            'final_verdict': self.final_verdict,
            'timestamp': self.timestamp.isoformat(),
            'last_close': self.last_close,
            'buy_range': self.buy_range,
            'target': self.target,
            'stop_loss': self.stop_loss,
            'rsi': self.rsi,
            'mtf_alignment_score': self.mtf_alignment_score,
            'backtest_score': self.backtest_score,
            'combined_score': self.combined_score,
            'priority_score': self.priority_score,
            'error_message': self.error_message,
            'chart_quality': self.chart_quality,
            'execution_capital': self.execution_capital,
            'max_capital': self.max_capital,
            'capital_adjusted': self.capital_adjusted,
            'metadata': self.metadata
        }
    
    def is_success(self) -> bool:
        """Check if analysis was successful"""
        return self.status == "success"
    
    def is_buyable(self, use_final_verdict: bool = False) -> bool:
        """
        Check if stock is buyable
        
        Args:
            use_final_verdict: If True, use final_verdict (after backtest) instead of verdict
            
        Returns:
            True if buyable
        """
        # Use final_verdict if backtest was run, otherwise use verdict
        if use_final_verdict and self.final_verdict:
            return self.final_verdict in ['buy', 'strong_buy']
        return self.verdict in ['buy', 'strong_buy']


@dataclass
class BulkAnalysisResponse:
    """
    Response from bulk stock analysis
    
    Attributes:
        results: List of individual analysis responses
        total_analyzed: Total stocks analyzed
        successful: Number of successful analyses
        failed: Number of failed analyses
        buyable_count: Number of buyable stocks
        timestamp: Analysis timestamp
        execution_time_seconds: Time taken for analysis
    """
    results: List[AnalysisResponse]
    total_analyzed: int
    successful: int
    failed: int
    buyable_count: int
    timestamp: datetime
    execution_time_seconds: float = 0.0
    
    def get_buy_candidates(self, min_combined_score: float = 0.0, use_final_verdict: bool = False) -> List[AnalysisResponse]:
        """
        Get all buyable stocks
        
        Args:
            min_combined_score: Minimum combined score threshold (0 = no filter)
            use_final_verdict: Use final_verdict (after backtest) instead of verdict
        """
        candidates = [r for r in self.results if r.is_buyable(use_final_verdict=use_final_verdict) and r.is_success()]
        
        # Apply score filter if specified
        if min_combined_score > 0:
            candidates = [r for r in candidates if r.combined_score >= min_combined_score]
        
        return candidates
    
    def get_strong_buy_candidates(self, min_combined_score: float = 0.0, use_final_verdict: bool = False) -> List[AnalysisResponse]:
        """
        Get strong buy stocks
        
        Args:
            min_combined_score: Minimum combined score threshold (0 = no filter)
            use_final_verdict: Use final_verdict (after backtest) instead of verdict
        """
        # Use final_verdict if specified and available
        if use_final_verdict:
            candidates = [
                r for r in self.results 
                if (r.final_verdict == 'strong_buy' if r.final_verdict else r.verdict == 'strong_buy') and r.is_success()
            ]
        else:
            candidates = [
                r for r in self.results 
                if r.verdict == 'strong_buy' and r.is_success()
            ]
        
        # Apply score filter if specified
        if min_combined_score > 0:
            candidates = [r for r in candidates if r.combined_score >= min_combined_score]
        
        return candidates
    
    def get_sorted_by_priority(self) -> List[AnalysisResponse]:
        """Get results sorted by priority score"""
        return sorted(self.results, key=lambda x: x.priority_score, reverse=True)
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'total_analyzed': self.total_analyzed,
            'successful': self.successful,
            'failed': self.failed,
            'buyable_count': self.buyable_count,
            'timestamp': self.timestamp.isoformat(),
            'execution_time_seconds': self.execution_time_seconds,
            'results': [r.to_dict() for r in self.results]
        }
