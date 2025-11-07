"""
Backtest Service

Integrates historical backtesting into the trading agent workflow.
Migrated from core/backtest_scoring.py to service layer (Phase 4).

This service provides backtest scoring based on historical performance
of the trading strategy.
"""

from typing import Dict, List, Optional
import logging
import warnings
warnings.filterwarnings('ignore')

from utils.logger import logger

# Import backtest functions from core (will be migrated incrementally)
try:
    from integrated_backtest import run_integrated_backtest
    BACKTEST_MODE = 'integrated'
except ImportError as e:
    logger.warning(f"Integrated backtest not available: {e}, using simple backtest")
    run_integrated_backtest = None
    BACKTEST_MODE = 'simple'

# Import helper functions from core (temporary, will be migrated)
from core.backtest_scoring import (
    calculate_backtest_score,
    run_simple_backtest,
    run_stock_backtest
)


class BacktestService:
    """
    Service for running backtests and calculating backtest scores
    
    Provides methods to:
    - Run backtests for individual stocks
    - Calculate backtest scores from results
    - Add backtest scores to analysis results
    
    This service wraps the core backtest scoring logic,
    providing dependency injection and better testability.
    """
    
    def __init__(self, default_years_back: int = 2, dip_mode: bool = False):
        """
        Initialize backtest service
        
        Args:
            default_years_back: Default number of years for backtesting
            dip_mode: Whether to use dip mode for backtesting
        """
        self.default_years_back = default_years_back
        self.dip_mode = dip_mode
    
    def calculate_backtest_score(self, backtest_results: Dict, dip_mode: Optional[bool] = None) -> float:
        """
        Calculate a backtest score based on performance metrics.
        
        This method delegates to core.backtest_scoring.calculate_backtest_score()
        while providing a service interface.
        
        Args:
            backtest_results: Backtest results dictionary
            dip_mode: Whether to use dip mode (uses instance default if None)
            
        Returns:
            Float score between 0-100
        """
        if dip_mode is None:
            dip_mode = self.dip_mode
        
        return calculate_backtest_score(backtest_results, dip_mode)
    
    def run_stock_backtest(
        self,
        stock_symbol: str,
        years_back: Optional[int] = None,
        dip_mode: Optional[bool] = None
    ) -> Dict:
        """
        Run backtest for a stock using available method (integrated or simple).
        
        This method delegates to core.backtest_scoring.run_stock_backtest()
        while providing a service interface.
        
        Args:
            stock_symbol: Stock symbol (e.g., "RELIANCE.NS")
            years_back: Number of years to backtest (uses default if None)
            dip_mode: Whether to use dip mode (uses instance default if None)
            
        Returns:
            Dict with backtest results and score
        """
        if years_back is None:
            years_back = self.default_years_back
        if dip_mode is None:
            dip_mode = self.dip_mode
        
        return run_stock_backtest(stock_symbol, years_back, dip_mode)
    
    def add_backtest_scores_to_results(
        self,
        stock_results: List[Dict],
        years_back: Optional[int] = None,
        dip_mode: Optional[bool] = None
    ) -> List[Dict]:
        """
        Add backtest scores to existing stock analysis results.
        
        This method enhances stock results with historical performance data
        and recalculates combined scores.
        
        Args:
            stock_results: List of stock analysis results
            years_back: Years of historical data to analyze (uses default if None)
            dip_mode: Whether to use dip mode (uses instance default if None)
            
        Returns:
            Enhanced stock results with backtest scores
        """
        if years_back is None:
            years_back = self.default_years_back
        if dip_mode is None:
            dip_mode = self.dip_mode
        
        logger.info(f"Adding backtest scores for {len(stock_results)} stocks...")
        
        enhanced_results = []
        
        for i, stock_result in enumerate(stock_results, 1):
            try:
                ticker = stock_result.get('ticker', 'Unknown')
                logger.info(f"Processing {i}/{len(stock_results)}: {ticker}")
                
                # Run backtest for this stock
                backtest_data = self.run_stock_backtest(ticker, years_back, dip_mode)
                
                # Add backtest data to stock result
                stock_result['backtest'] = {
                    'score': backtest_data.get('backtest_score', 0),
                    'total_return_pct': backtest_data.get('total_return_pct', 0),
                    'win_rate': backtest_data.get('win_rate', 0),
                    'total_trades': backtest_data.get('total_trades', 0),
                    'vs_buy_hold': backtest_data.get('vs_buy_hold', 0),
                    'execution_rate': backtest_data.get('execution_rate', 0)
                }
                
                # Calculate combined score (50% current analysis + 50% backtest)
                current_score = stock_result.get('strength_score', 0)
                backtest_score = backtest_data.get('backtest_score', 0)
                
                # Use ScoringService for combined score calculation
                from services.scoring_service import ScoringService
                from config.strategy_config import StrategyConfig
                scoring_service = ScoringService(config=StrategyConfig.default())
                combined_score = scoring_service.compute_combined_score(
                    current_score=current_score,
                    backtest_score=backtest_score,
                    current_weight=0.5,
                    backtest_weight=0.5
                )
                
                stock_result['combined_score'] = combined_score
                stock_result['backtest_score'] = backtest_score
                
                # Re-classify based on combined score and key metrics
                self._reclassify_with_backtest(stock_result, backtest_score, combined_score)
                
                enhanced_results.append(stock_result)
                
            except Exception as e:
                logger.error(f"Error adding backtest score for {stock_result.get('ticker', 'Unknown')}: {e}")
                # Add stock without backtest score
                stock_result['backtest'] = {
                    'score': 0,
                    'error': str(e)
                }
                enhanced_results.append(stock_result)
        
        return enhanced_results
    
    def _reclassify_with_backtest(
        self,
        stock_result: Dict,
        backtest_score: float,
        combined_score: float
    ) -> None:
        """
        Re-classify stock verdict based on backtest results.
        
        Args:
            stock_result: Stock analysis result (modified in place)
            backtest_score: Backtest score
            combined_score: Combined current + backtest score
        """
        # Get trade count for confidence assessment
        trade_count = stock_result.get('backtest', {}).get('total_trades', 0)
        
        # Get current RSI for dynamic threshold adjustment
        current_rsi = stock_result.get('rsi', 30)  # Default to 30 if not available
        
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
            
            buy_threshold = 35 * rsi_factor
            combined_buy_threshold = 22 * rsi_factor
            combined_decent_threshold = 35 * rsi_factor
            
            if (backtest_score >= strong_buy_threshold and combined_score >= combined_strong_threshold) or combined_score >= combined_exceptional_threshold:
                stock_result['final_verdict'] = 'strong_buy'
            elif (backtest_score >= buy_threshold and combined_score >= combined_buy_threshold) or combined_score >= combined_decent_threshold:
                stock_result['final_verdict'] = 'buy'
            else:
                stock_result['final_verdict'] = 'watch'
        else:
            # Lower confidence thresholds (adjusted by RSI)
            strong_buy_threshold = 65 * rsi_factor
            combined_strong_threshold = 42 * rsi_factor
            combined_exceptional_threshold = 65 * rsi_factor
            
            buy_threshold = 40 * rsi_factor
            combined_buy_threshold = 28 * rsi_factor
            combined_decent_threshold = 45 * rsi_factor
            
            if (backtest_score >= strong_buy_threshold and combined_score >= combined_strong_threshold) or combined_score >= combined_exceptional_threshold:
                stock_result['final_verdict'] = 'strong_buy'
            elif (backtest_score >= buy_threshold and combined_score >= combined_buy_threshold) or combined_score >= combined_decent_threshold:
                stock_result['final_verdict'] = 'buy'
            else:
                stock_result['final_verdict'] = 'watch'
        
        # Log RSI adjustment if applied
        if rsi_factor < 1.0:
            logger.debug(f"{stock_result.get('ticker', 'Unknown')}: RSI={current_rsi:.1f}, applied {(1-rsi_factor)*100:.0f}% threshold reduction")
        
        # Add confidence indicator to result
        confidence_level = "High" if trade_count >= 5 else "Medium" if trade_count >= 2 else "Low"
        stock_result['backtest_confidence'] = confidence_level


# Backward compatibility functions
def calculate_backtest_score_compat(backtest_results: Dict, dip_mode: bool = False) -> float:
    """
    Backward compatibility wrapper for core.backtest_scoring.calculate_backtest_score()
    """
    service = BacktestService(dip_mode=dip_mode)
    return service.calculate_backtest_score(backtest_results, dip_mode)


def run_stock_backtest_compat(stock_symbol: str, years_back: int = 2, dip_mode: bool = False) -> Dict:
    """
    Backward compatibility wrapper for core.backtest_scoring.run_stock_backtest()
    """
    service = BacktestService(default_years_back=years_back, dip_mode=dip_mode)
    return service.run_stock_backtest(stock_symbol, years_back, dip_mode)


def add_backtest_scores_to_results_compat(
    stock_results: List[Dict],
    years_back: int = 2,
    dip_mode: bool = False
) -> List[Dict]:
    """
    Backward compatibility wrapper for core.backtest_scoring.add_backtest_scores_to_results()
    """
    service = BacktestService(default_years_back=years_back, dip_mode=dip_mode)
    return service.add_backtest_scores_to_results(stock_results, years_back, dip_mode)

