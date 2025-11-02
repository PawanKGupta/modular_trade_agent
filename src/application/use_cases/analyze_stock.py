"""
Analyze Stock Use Case

Orchestrates the single stock analysis workflow.
"""

from typing import Optional
from datetime import datetime

# Import existing code (bridge to old architecture)
from core.analysis import analyze_ticker as legacy_analyze_ticker
from core.backtest_scoring import run_stock_backtest, calculate_backtest_score

# Import new architecture components
from ..dto.analysis_request import AnalysisRequest
from ..dto.analysis_response import AnalysisResponse
from ..services.scoring_service import ScoringService
from utils.logger import logger


class AnalyzeStockUseCase:
    """
    Use case for analyzing a single stock
    
    Orchestrates the analysis workflow:
    1. Validates the request
    2. Fetches and processes data
    3. Calculates indicators
    4. Generates signals
    5. Calculates scores
    6. Returns formatted response
    """
    
    def __init__(self, scoring_service: Optional[ScoringService] = None):
        """
        Initialize use case
        
        Args:
            scoring_service: Service for score calculations
        """
        self.scoring_service = scoring_service or ScoringService()
    
    def execute(self, request: AnalysisRequest) -> AnalysisResponse:
        """
        Execute stock analysis
        
        Args:
            request: Analysis request with parameters
            
        Returns:
            AnalysisResponse with analysis results
        """
        try:
            logger.info(f"Analyzing {request.ticker} (MTF: {request.enable_multi_timeframe})")
            
            # Use existing analysis logic (legacy bridge)
            result = legacy_analyze_ticker(
                ticker=request.ticker,
                enable_multi_timeframe=request.enable_multi_timeframe,
                export_to_csv=request.export_to_csv,
                as_of_date=request.end_date
            )
            
            # Check if analysis succeeded
            if result.get('status') != 'success':
                return AnalysisResponse(
                    ticker=request.ticker,
                    status=result.get('status', 'error'),
                    timestamp=datetime.now(),
                    error_message=result.get('error', 'Analysis failed')
                )
            
            # Calculate scores using new service
            strength_score = self.scoring_service.compute_strength_score(result)
            result['strength_score'] = strength_score
            
            # Run backtest if requested (using legacy logic)
            if request.enable_backtest:
                try:
                    # Use the exact legacy backtest logic
                    backtest_data = run_stock_backtest(request.ticker, years_back=2, dip_mode=request.dip_mode)
                    
                    # Add backtest data to result (as legacy does)
                    result['backtest'] = {
                        'score': backtest_data.get('backtest_score', 0),
                        'total_return_pct': backtest_data.get('total_return_pct', 0),
                        'win_rate': backtest_data.get('win_rate', 0),
                        'total_trades': backtest_data.get('total_trades', 0),
                        'vs_buy_hold': backtest_data.get('vs_buy_hold', 0),
                        'execution_rate': backtest_data.get('execution_rate', 0)
                    }
                    
                    backtest_score = backtest_data.get('backtest_score', 0)
                    result['backtest_score'] = backtest_score
                    
                    # Calculate combined score (50% current + 50% backtest) - exactly as legacy
                    combined_score = (strength_score * 0.5) + (backtest_score * 0.5)
                    result['combined_score'] = combined_score
                    
                    # Get trade count and RSI for verdict reclassification
                    trade_count = backtest_data.get('total_trades', 0)
                    current_rsi = result.get('rsi', 30)
                    
                    # Compute final verdict using exact legacy logic
                    final_verdict = self._compute_final_verdict(
                        original_verdict=result.get('verdict'),
                        backtest_score=backtest_score,
                        combined_score=combined_score,
                        trade_count=trade_count,
                        current_rsi=current_rsi
                    )
                    result['final_verdict'] = final_verdict
                    
                    # Add confidence indicator (as legacy does)
                    confidence_level = "High" if trade_count >= 5 else "Medium" if trade_count >= 2 else "Low"
                    result['backtest_confidence'] = confidence_level
                    
                    logger.info(f"  {request.ticker}: Current={strength_score:.1f}, Backtest={backtest_score:.1f}, Combined={combined_score:.1f}, Final={final_verdict}")
                except Exception as e:
                    logger.error(f"Error processing backtest for {request.ticker}: {e}")
                    result['backtest'] = {'score': 0, 'error': str(e)}
                    result['backtest_score'] = 0.0
                    result['combined_score'] = strength_score
            
            priority_score = self.scoring_service.compute_trading_priority_score(result)
            result['priority_score'] = priority_score
            
            # Build response
            return self._build_response(result)
            
        except Exception as e:
            logger.error(f"Error in AnalyzeStockUseCase for {request.ticker}: {e}")
            return AnalysisResponse(
                ticker=request.ticker,
                status="error",
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    def _build_response(self, result: dict) -> AnalysisResponse:
        """Build AnalysisResponse from legacy result dict"""
        buy_range = result.get('buy_range')
        if buy_range and isinstance(buy_range, list) and len(buy_range) >= 2:
            buy_range_tuple = (buy_range[0], buy_range[1])
        else:
            buy_range_tuple = None
        
        metadata = {
            'justifications': result.get('justification', []),
            'patterns': result.get('patterns', []),
            'timeframe_analysis': result.get('timeframe_analysis'),
            'news_sentiment': result.get('news_sentiment'),
            'pe': result.get('pe'),
            'pb': result.get('pb'),
            'volume_multiplier': result.get('volume_multiplier'),
            'risk_reward_ratio': result.get('risk_reward_ratio'),
            # Include candle analysis details for regression validation
            'candle_analysis': result.get('candle_analysis'),
            # ML prediction data (Phase 3/4)
            'ml_verdict': result.get('ml_verdict'),
            'ml_confidence': result.get('ml_confidence'),
            'verdict_source': result.get('verdict_source'),
            'rule_verdict': result.get('rule_verdict')
        }
        
        return AnalysisResponse(
            ticker=result.get('ticker'),
            status=result.get('status', 'success'),
            timestamp=datetime.now(),
            verdict=result.get('verdict', 'unknown'),
            final_verdict=result.get('final_verdict'),  # Verdict after backtest reclassification
            last_close=result.get('last_close', 0.0),
            buy_range=buy_range_tuple,
            target=result.get('target'),
            stop_loss=result.get('stop'),
            rsi=result.get('rsi'),
            mtf_alignment_score=self._get_mtf_score(result),
            backtest_score=result.get('backtest_score', 0.0),
            combined_score=result.get('combined_score', 0.0),
            priority_score=result.get('priority_score', 0.0),
            metadata=metadata
        )
    
    def _get_mtf_score(self, result: dict) -> float:
        """Extract MTF alignment score from result"""
        tf_analysis = result.get('timeframe_analysis')
        if tf_analysis and isinstance(tf_analysis, dict):
            return tf_analysis.get('alignment_score', 0.0)
        return 0.0
    
    def _compute_final_verdict(
        self,
        original_verdict: str,
        backtest_score: float,
        combined_score: float,
        trade_count: int,
        current_rsi: float
    ) -> str:
        """
        Compute final verdict based on backtest performance
        
        Re-classifies the verdict based on:
        - Backtest score
        - Combined score (current + backtest)
        - Trade count (confidence)
        - Current RSI (for threshold adjustment)
        
        Args:
            original_verdict: Original analysis verdict
            backtest_score: Backtest performance score
            combined_score: Combined current + backtest score
            trade_count: Number of historical trades
            current_rsi: Current RSI value
            
        Returns:
            Final verdict (strong_buy, buy, watch, avoid)
        """
        # RSI-based threshold adjustment (more oversold = lower thresholds)
        rsi_factor = 1.0
        if current_rsi < 20:  # Extremely oversold
            rsi_factor = 0.7  # 30% lower thresholds
        elif current_rsi < 25:  # Very oversold
            rsi_factor = 0.8  # 20% lower thresholds
        elif current_rsi < 30:  # Oversold
            rsi_factor = 0.9  # 10% lower thresholds
        
        # Enhanced reclassification with confidence-aware and RSI-adjusted thresholds
        if trade_count >= 5:
            # High confidence thresholds (adjusted by RSI)
            strong_buy_threshold = 60 * rsi_factor
            combined_strong_threshold = 35 * rsi_factor
            combined_exceptional_threshold = 60 * rsi_factor
            
            buy_threshold = 40 * rsi_factor
            combined_buy_threshold = 25 * rsi_factor
            combined_decent_threshold = 40 * rsi_factor
            
            if (backtest_score >= strong_buy_threshold and combined_score >= combined_strong_threshold) or combined_score >= combined_exceptional_threshold:
                return 'strong_buy'
            elif (backtest_score >= buy_threshold and combined_score >= combined_buy_threshold) or combined_score >= combined_decent_threshold:
                return 'buy'
            else:
                return 'watch'
        else:
            # Lower confidence thresholds (more conservative, adjusted by RSI)
            strong_buy_threshold = 70 * rsi_factor
            combined_strong_threshold = 45 * rsi_factor
            combined_exceptional_threshold = 70 * rsi_factor
            
            buy_threshold = 50 * rsi_factor
            combined_buy_threshold = 35 * rsi_factor
            combined_decent_threshold = 50 * rsi_factor
            
            if (backtest_score >= strong_buy_threshold and combined_score >= combined_strong_threshold) or combined_score >= combined_exceptional_threshold:
                return 'strong_buy'
            elif (backtest_score >= buy_threshold and combined_score >= combined_buy_threshold) or combined_score >= combined_decent_threshold:
                return 'buy'
            else:
                return 'watch'
