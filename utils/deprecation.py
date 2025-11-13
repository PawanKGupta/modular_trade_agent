"""
Deprecation Utilities

Provides deprecation warnings and migration guidance for legacy code.

Phase 4: Deprecation utilities to help migrate from core.* to services/infrastructure.
"""

import warnings
import functools
from typing import Callable, Optional
from datetime import datetime

from utils.logger import logger


def deprecated(
    reason: str,
    replacement: Optional[str] = None,
    version: str = "Phase 4",
    removal_date: Optional[str] = None
):
    """
    Decorator to mark functions as deprecated.
    
    Args:
        reason: Reason for deprecation
        replacement: Suggested replacement (e.g., "services.AnalysisService.analyze_ticker()")
        version: Version when deprecated
        removal_date: Expected removal date (optional)
    
    Example:
        @deprecated(
            reason="This function is deprecated. Use AnalysisService instead.",
            replacement="services.AnalysisService.analyze_ticker()",
            version="Phase 4"
        )
        def analyze_ticker(ticker):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Build deprecation message
            message_parts = [
                f"DEPRECATED: {func.__name__}() is deprecated.",
                f"Reason: {reason}"
            ]
            
            if replacement:
                message_parts.append(f"Replacement: {replacement}")
            
            if removal_date:
                message_parts.append(f"Scheduled for removal: {removal_date}")
            else:
                message_parts.append("Will be removed in a future version.")
            
            message = " ".join(message_parts)
            
            # Issue warning
            warnings.warn(
                message,
                DeprecationWarning,
                stacklevel=2
            )
            
            # Log for debugging
            logger.warning(f"Deprecated function called: {func.__name__}() - {reason}")
            
            # Call original function
            return func(*args, **kwargs)
        
        # Add deprecation metadata
        wrapper.__deprecated__ = True
        wrapper.__deprecation_reason__ = reason
        wrapper.__deprecation_replacement__ = replacement
        wrapper.__deprecation_version__ = version
        
        return wrapper
    return decorator


def deprecation_notice(
    module: str,
    function: str,
    replacement: str,
    version: str = "Phase 4"
):
    """
    Issue a deprecation notice for a module/function.
    
    Args:
        module: Module name (e.g., "core.analysis")
        function: Function name (e.g., "analyze_ticker")
        replacement: Suggested replacement (e.g., "services.AnalysisService.analyze_ticker()")
        version: Version when deprecated
    """
    message = (
        f"DEPRECATED: {module}.{function}() is deprecated in {version}. "
        f"Use {replacement} instead. "
        f"This will be removed in a future version."
    )
    
    warnings.warn(message, DeprecationWarning, stacklevel=3)
    logger.warning(message)


def get_migration_guide(function_name: str) -> str:
    """
    Get migration guide for a deprecated function.
    
    Args:
        function_name: Name of deprecated function
        
    Returns:
        Migration guide text
    """
    guides = {
        "analyze_ticker": """
Migration Guide: analyze_ticker()

OLD (deprecated):
    from core.analysis import analyze_ticker
    result = analyze_ticker("RELIANCE.NS")

NEW (recommended):
    from services import AnalysisService
    service = AnalysisService()
    result = service.analyze_ticker("RELIANCE.NS")

Benefits:
    - Better testability
    - Dependency injection
    - Async support available
    - Type safety with typed models
        """,
        
        "analyze_multiple_tickers": """
Migration Guide: analyze_multiple_tickers()

OLD (deprecated):
    from core.analysis import analyze_multiple_tickers
    results = analyze_multiple_tickers(["RELIANCE.NS", "TCS.NS"])

NEW (recommended):
    from services import AsyncAnalysisService
    import asyncio
    
    async def analyze():
        service = AsyncAnalysisService(max_concurrent=10)
        results = await service.analyze_batch_async(
            tickers=["RELIANCE.NS", "TCS.NS"],
            enable_multi_timeframe=True
        )
        return results
    
    results = asyncio.run(analyze())

Benefits:
    - 80% faster batch analysis
    - Better error handling
    - Async/await support
        """,
        
        "compute_strength_score": """
Migration Guide: compute_strength_score()

OLD (deprecated):
    from core.scoring import compute_strength_score
    score = compute_strength_score(result)

NEW (recommended):
    from services import ScoringService
    service = ScoringService()
    score = service.compute_strength_score(result)

Benefits:
    - Service layer benefits
    - Dependency injection
    - Better testability
        """,
        
        "add_backtest_scores_to_results": """
Migration Guide: add_backtest_scores_to_results()

OLD (deprecated):
    from core.backtest_scoring import add_backtest_scores_to_results
    results = add_backtest_scores_to_results(results)

NEW (recommended):
    from services import BacktestService
    service = BacktestService(default_years_back=2, dip_mode=False)
    results = service.add_backtest_scores_to_results(results)

Benefits:
    - Service layer benefits
    - Configurable defaults
    - Better error handling
        """,
    }
    
    return guides.get(function_name, f"No migration guide available for {function_name}")

