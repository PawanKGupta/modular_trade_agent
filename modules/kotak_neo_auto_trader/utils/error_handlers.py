#!/usr/bin/env python3
"""
Standardized Error Handling Utilities
Provides consistent error handling patterns across the codebase
"""

import logging
from typing import Optional, Callable, TypeVar, Any, Union
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


def handle_broker_error(
    operation: str,
    default_return: Optional[T] = None,
    log_level: str = 'warning',
    reraise: bool = False
) -> Callable:
    """
    Decorator for consistent broker error handling.
    
    Args:
        operation: Description of the operation (e.g., "order placement")
        default_return: Value to return on error (default: None)
        log_level: Logging level ('debug', 'info', 'warning', 'error')
        reraise: If True, re-raise exception after logging
        
    Returns:
        Decorator function
        
    Example:
        @handle_broker_error("order placement", default_return=None)
        def place_order(self, ...):
            # Implementation
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Optional[T]:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_func = getattr(logger, log_level.lower(), logger.warning)
                log_func(f"Error in {operation}: {e}")
                
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator


def safe_execute(
    operation: Callable[[], T],
    operation_name: str,
    default_return: Optional[T] = None,
    log_level: str = 'warning',
    reraise: bool = False
) -> Optional[T]:
    """
    Execute a broker operation with consistent error handling.
    
    Args:
        operation: Callable to execute (no-arg function or lambda)
        operation_name: Description of the operation
        default_return: Value to return on error
        log_level: Logging level
        reraise: If True, re-raise exception after logging
        
    Returns:
        Result of operation or default_return on error
        
    Example:
        result = safe_execute(
            lambda: orders.place_order(...),
            "order placement",
            default_return=None
        )
    """
    try:
        return operation()
    except Exception as e:
        log_func = getattr(logger, log_level.lower(), logger.warning)
        log_func(f"Error in {operation_name}: {e}")
        
        if reraise:
            raise
        return default_return


class BrokerErrorHandler:
    """
    Context manager for consistent broker error handling.
    
    Example:
        with BrokerErrorHandler("order placement", default_return=None) as handler:
            result = orders.place_order(...)
            handler.check_result(result)
    """
    
    def __init__(
        self,
        operation_name: str,
        default_return: Optional[T] = None,
        log_level: str = 'warning'
    ):
        self.operation_name = operation_name
        self.default_return = default_return
        self.log_level = log_level
        self.error_occurred = False
        self.exception: Optional[Exception] = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.error_occurred = True
            self.exception = exc_val
            log_func = getattr(logger, self.log_level.lower(), logger.warning)
            log_func(f"Error in {self.operation_name}: {exc_val}")
            
            # Suppress exception if reraise is False
            return True  # Suppress exception
        
        return False
    
    def check_result(self, result: Any) -> Optional[T]:
        """
        Check if result indicates an error and return default if needed.
        
        Args:
            result: Result to check
            
        Returns:
            Result or default_return if error detected
        """
        if result is None:
            return self.default_return
        return result

