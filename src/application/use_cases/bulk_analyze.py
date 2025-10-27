"""
Bulk Analyze Use Case

Orchestrates bulk stock analysis workflow.
"""

from typing import Optional, List
from datetime import datetime
import time

from ..dto.analysis_request import BulkAnalysisRequest, AnalysisRequest
from ..dto.analysis_response import BulkAnalysisResponse, AnalysisResponse
from ..services.scoring_service import ScoringService
from ..services.filtering_service import FilteringService
from .analyze_stock import AnalyzeStockUseCase
from utils.logger import logger


class BulkAnalyzeUseCase:
    """
    Use case for analyzing multiple stocks in bulk
    
    Orchestrates:
    1. Individual stock analyses
    2. Result filtering
    3. Score calculation and sorting
    4. Statistics aggregation
    """
    
    def __init__(
        self,
        analyze_stock_use_case: Optional[AnalyzeStockUseCase] = None,
        scoring_service: Optional[ScoringService] = None,
        filtering_service: Optional[FilteringService] = None
    ):
        """
        Initialize use case
        
        Args:
            analyze_stock_use_case: Single stock analysis use case
            scoring_service: Service for score calculations
            filtering_service: Service for filtering results
        """
        self.analyze_stock = analyze_stock_use_case or AnalyzeStockUseCase()
        self.scoring_service = scoring_service or ScoringService()
        self.filtering_service = filtering_service or FilteringService()
    
    def execute(self, request: BulkAnalysisRequest) -> BulkAnalysisResponse:
        """
        Execute bulk stock analysis
        
        Args:
            request: Bulk analysis request
            
        Returns:
            BulkAnalysisResponse with aggregated results
        """
        start_time = time.time()
        results: List[AnalysisResponse] = []
        
        logger.info(f"Starting bulk analysis for {len(request.tickers)} stocks")
        
        # Analyze each stock
        for ticker in request.tickers:
            try:
                # Create individual request
                stock_request = AnalysisRequest(
                    ticker=ticker,
                    enable_multi_timeframe=request.enable_multi_timeframe,
                    enable_backtest=request.enable_backtest,
                    export_to_csv=request.export_to_csv,
                    dip_mode=request.dip_mode
                )
                
                # Execute analysis
                result = self.analyze_stock.execute(stock_request)
                results.append(result)
                
                # Log progress
                if result.is_success():
                    logger.debug(f"✓ {ticker}: {result.verdict}")
                else:
                    logger.warning(f"✗ {ticker}: {result.status}")
                    
            except Exception as e:
                logger.error(f"Error analyzing {ticker}: {e}")
                results.append(AnalysisResponse(
                    ticker=ticker,
                    status="error",
                    timestamp=datetime.now(),
                    error_message=str(e)
                ))
        
        # Calculate statistics
        total_analyzed = len(results)
        successful = sum(1 for r in results if r.is_success())
        failed = total_analyzed - successful
        
        # Apply proper filtering for buyable count
        # When backtest is enabled, use final_verdict and apply combined_score filter
        if request.enable_backtest:
            buyable_count = sum(
                1 for r in results 
                if r.is_buyable(use_final_verdict=True) and 
                   r.is_success() and 
                   r.combined_score >= request.min_combined_score
            )
        else:
            buyable_count = sum(1 for r in results if r.is_buyable())
        
        # Sort by priority score (descending)
        results.sort(key=lambda x: x.priority_score, reverse=True)
        
        execution_time = time.time() - start_time
        
        logger.info(f"Bulk analysis complete: {successful}/{total_analyzed} successful, {buyable_count} buyable ({execution_time:.2f}s)")
        
        return BulkAnalysisResponse(
            results=results,
            total_analyzed=total_analyzed,
            successful=successful,
            failed=failed,
            buyable_count=buyable_count,
            timestamp=datetime.now(),
            execution_time_seconds=execution_time
        )
