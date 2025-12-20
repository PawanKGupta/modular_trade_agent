"""
Timeout utilities for wrapping SDK calls with timeout protection.

Uses concurrent.futures.ThreadPoolExecutor for cross-platform timeout support.
Works on both Windows and Linux.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import TypeVar

from utils.logger import logger

T = TypeVar("T")

# Default timeout for SDK calls (30 seconds - should be enough for most API calls)
DEFAULT_SDK_TIMEOUT = 30.0


def call_with_timeout(
    func: Callable[[], T],
    timeout: float = DEFAULT_SDK_TIMEOUT,
    timeout_error_message: str = "SDK call timed out",
) -> T:
    """
    Execute a function with timeout protection.

    Uses ThreadPoolExecutor to run the function in a separate thread,
    allowing us to timeout the call even if the SDK doesn't support timeouts.

    Args:
        func: Function to call (must be callable with no arguments)
        timeout: Timeout in seconds (default: 30s)
        timeout_error_message: Custom error message for timeout

    Returns:
        Function result

    Raises:
        TimeoutError: If function doesn't complete within timeout
        Exception: Any exception raised by the function

    Example:
        >>> result = call_with_timeout(lambda: client.holdings(), timeout=30.0)
    """
    if timeout <= 0:
        # No timeout - call directly
        return func()

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            try:
                result = future.result(timeout=timeout)
                return result
            except FutureTimeoutError:
                logger.error(
                    f"{timeout_error_message} after {timeout}s. "
                    f"Function: {func.__name__ if hasattr(func, '__name__') else 'unknown'}"
                )
                # Cancel the future (best effort - thread may still be running)
                future.cancel()
                raise TimeoutError(f"{timeout_error_message} after {timeout} seconds") from None
    except TimeoutError:
        # Re-raise our timeout error
        raise
    except Exception:
        # Re-raise any other exception from the function
        raise


def call_with_timeout_and_fallback(
    func: Callable[[], T],
    timeout: float = DEFAULT_SDK_TIMEOUT,
    timeout_error_message: str = "SDK call timed out",
    fallback_value: T = None,  # type: ignore
) -> T | None:
    """
    Execute a function with timeout protection, returning fallback value on timeout.

    Similar to call_with_timeout, but catches TimeoutError and returns fallback_value
    instead of raising an exception.

    Args:
        func: Function to call (must be callable with no arguments)
        timeout: Timeout in seconds (default: 30s)
        timeout_error_message: Custom error message for timeout
        fallback_value: Value to return on timeout (default: None)

    Returns:
        Function result or fallback_value on timeout

    Example:
        >>> result = call_with_timeout_and_fallback(
        ...     lambda: client.holdings(),
        ...     timeout=30.0,
        ...     fallback_value={}
        ... )
    """
    try:
        return call_with_timeout(func, timeout, timeout_error_message)
    except TimeoutError:
        logger.warning(f"Timeout occurred, returning fallback value: {fallback_value}")
        return fallback_value
