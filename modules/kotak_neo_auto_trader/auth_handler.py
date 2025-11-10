#!/usr/bin/env python3
"""
Authentication Handler
Centralized re-authentication handling using decorator pattern
"""

import functools
import threading
from typing import Optional, Dict, Any, Callable
from utils.logger import logger

# Thread-safe re-authentication coordination
# Per-auth-object locks to prevent concurrent re-auth attempts
_reauth_locks: Dict[int, threading.Lock] = {}
_reauth_locks_lock = threading.Lock()  # Protects the dict itself
_reauth_in_progress: Dict[int, threading.Event] = {}
_reauth_in_progress_lock = threading.Lock()  # Protects the dict itself
# Track recent re-auth failures to prevent loops
_recent_reauth_failures: Dict[int, tuple] = {}  # auth_id -> (failure_time, failure_count)
_recent_reauth_failures_lock = threading.Lock()  # Protects the dict itself
_REAUTH_FAILURE_WINDOW = 60  # seconds
_MAX_REAUTH_FAILURES = 3  # max failures in window before blocking


def is_auth_error(response: Any) -> bool:
    """
    Check if response indicates authentication failure (JWT expiry).
    
    Args:
        response: API response (dict, exception, or other)
        
    Returns:
        True if response indicates auth failure, False otherwise
    """
    if not isinstance(response, dict):
        return False
    
    code = str(response.get('code', '')).strip()
    message = str(response.get('message', '')).lower()
    description = str(response.get('description', '')).lower()
    error = str(response.get('error', '')).lower()
    
    # Check for JWT expiry error code
    if code == '900901':
        return True
    
    # Check for JWT token errors in description or message
    if 'invalid jwt token' in description or 'jwt token expired' in description:
        return True
    if 'invalid jwt token' in message or 'jwt token expired' in message:
        return True
    
    # Check for credential errors in message
    if 'invalid credentials' in message or 'unauthorized' in message:
        return True
    
    # Check for auth errors in error field
    if 'invalid credentials' in error or 'unauthorized' in error:
        return True
    
    return False


def is_auth_exception(exception: Exception) -> bool:
    """
    Check if exception indicates authentication failure.
    
    Args:
        exception: Exception object
        
    Returns:
        True if exception indicates auth failure, False otherwise
    """
    if not isinstance(exception, Exception):
        return False
    
    error_str = str(exception).lower()
    
    # Check for JWT/auth keywords in exception message
    auth_keywords = ['jwt', 'unauthorized', 'invalid credentials', 'token expired', 'authentication']
    return any(keyword in error_str for keyword in auth_keywords)


def _get_reauth_lock(auth) -> threading.Lock:
    """
    Get or create a lock for a specific auth object.
    
    Args:
        auth: Authentication object
        
    Returns:
        Threading lock for this auth object
    """
    auth_id = id(auth)
    
    with _reauth_locks_lock:
        if auth_id not in _reauth_locks:
            _reauth_locks[auth_id] = threading.Lock()
        return _reauth_locks[auth_id]


def _check_reauth_failure_rate(auth) -> bool:
    """
    Check if re-auth has failed too many times recently.
    
    Returns:
        True if re-auth should be blocked (too many failures), False otherwise
    """
    import time
    auth_id = id(auth)
    current_time = time.time()
    
    with _recent_reauth_failures_lock:
        if auth_id not in _recent_reauth_failures:
            return False
        
        failure_time, failure_count = _recent_reauth_failures[auth_id]
        
        # Reset if window expired
        if current_time - failure_time > _REAUTH_FAILURE_WINDOW:
            del _recent_reauth_failures[auth_id]
            return False
        
        # Block if too many failures
        if failure_count >= _MAX_REAUTH_FAILURES:
            logger.warning(
                f"Re-authentication blocked: {failure_count} failures in last {_REAUTH_FAILURE_WINDOW}s. "
                f"Please check authentication credentials or API status."
            )
            return True
        
        return False


def _record_reauth_failure(auth):
    """Record a re-auth failure for rate limiting"""
    import time
    auth_id = id(auth)
    current_time = time.time()
    
    with _recent_reauth_failures_lock:
        if auth_id not in _recent_reauth_failures:
            _recent_reauth_failures[auth_id] = (current_time, 1)
        else:
            failure_time, failure_count = _recent_reauth_failures[auth_id]
            
            # Reset if window expired
            if current_time - failure_time > _REAUTH_FAILURE_WINDOW:
                _recent_reauth_failures[auth_id] = (current_time, 1)
            else:
                # Increment failure count
                _recent_reauth_failures[auth_id] = (failure_time, failure_count + 1)


def _clear_reauth_failures(auth):
    """Clear re-auth failure history after successful re-auth"""
    auth_id = id(auth)
    with _recent_reauth_failures_lock:
        if auth_id in _recent_reauth_failures:
            del _recent_reauth_failures[auth_id]


def _get_reauth_event(auth) -> threading.Event:
    """
    Get or create an event for a specific auth object.
    
    Args:
        auth: Authentication object
        
    Returns:
        Threading event for this auth object
    """
    auth_id = id(auth)
    
    with _reauth_in_progress_lock:
        if auth_id not in _reauth_in_progress:
            _reauth_in_progress[auth_id] = threading.Event()
        return _reauth_in_progress[auth_id]


def _attempt_reauth_thread_safe(auth, method_name: str) -> bool:
    """
    Attempt re-authentication with thread-safe coordination.
    
    Only one thread performs re-auth per auth object. Other threads wait
    for the first thread to complete and share the re-authenticated session.
    
    Args:
        auth: Authentication object with force_relogin() method
        method_name: Name of the method requesting re-auth (for logging)
        
    Returns:
        True if re-auth was successful (either performed here or by another thread)
    """
    if not hasattr(auth, 'force_relogin'):
        logger.error("Auth object does not have force_relogin() method")
        return False
    
    lock = _get_reauth_lock(auth)
    reauth_event = _get_reauth_event(auth)
    
    # Try non-blocking acquire - only one thread gets the lock
    if lock.acquire(blocking=False):
        # Got lock - this thread will perform re-auth
        try:
            logger.warning(f"JWT token expired - attempting re-authentication for {method_name}...")
            reauth_event.clear()  # Clear previous state
            
            try:
                if auth.force_relogin():
                    logger.info(f"Re-authentication successful for {method_name}")
                    reauth_event.set()  # Signal success to waiting threads
                    return True
                else:
                    logger.error(f"Re-authentication failed for {method_name}")
                    # Don't set event on failure - other threads can retry
                    return False
            except Exception as e:
                logger.error(f"Re-authentication exception for {method_name}: {e}")
                # Don't set event on exception - other threads can retry
                return False
        finally:
            lock.release()
    else:
        # Lock held - another thread is performing re-auth
        logger.debug(f"Waiting for re-authentication in progress for {method_name}...")
        
        # Wait for re-auth to complete (with timeout to prevent deadlock)
        if reauth_event.wait(timeout=30.0):
            logger.debug(f"Re-authentication completed by another thread for {method_name}")
            return True
        else:
            logger.warning(f"Re-authentication timeout for {method_name} - attempting own re-auth")
            # Timeout - try to acquire lock and perform re-auth
            if lock.acquire(blocking=True, timeout=5.0):
                try:
                    # Check if re-auth completed while waiting
                    if reauth_event.is_set():
                        return True
                    
                    # Perform re-auth
                    reauth_event.clear()
                    try:
                        if auth.force_relogin():
                            logger.info(f"Re-authentication successful (timeout recovery) for {method_name}")
                            reauth_event.set()
                            return True
                        else:
                            logger.error(f"Re-authentication failed (timeout recovery) for {method_name}")
                            return False
                    except Exception as e:
                        logger.error(f"Re-authentication exception (timeout recovery) for {method_name}: {e}")
                        return False
                finally:
                    lock.release()
            else:
                logger.error(f"Could not acquire lock for re-authentication (timeout) for {method_name}")
                return False
    
    return False


def handle_reauth(func: Callable) -> Callable:
    """
    Decorator to automatically handle re-authentication on auth failures.
    
    Usage:
        @handle_reauth
        def my_method(self, ...):
            response = self.client.some_api_call()
            return response
    
    The decorator will:
    1. Catch auth failures in responses
    2. Attempt re-authentication
    3. Retry the method once if re-auth succeeds
    4. Handle exceptions that indicate auth failures
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # First attempt
        try:
            result = func(self, *args, **kwargs)
            
            # Check if response indicates auth failure
            if isinstance(result, dict) and is_auth_error(result):
                # Check if re-auth should be blocked due to recent failures
                if _check_reauth_failure_rate(self.auth):
                    logger.error(f"Re-authentication blocked for {func.__name__} due to recent failures")
                    return None
                
                # Use thread-safe re-authentication
                if hasattr(self, 'auth'):
                    if _attempt_reauth_thread_safe(self.auth, func.__name__):
                        logger.info(f"Retrying {func.__name__} after re-authentication...")
                        # Retry once after successful re-auth
                        retry_result = func(self, *args, **kwargs)
                        
                        # If retry still fails with auth error, re-auth didn't actually work
                        if isinstance(retry_result, dict) and is_auth_error(retry_result):
                            logger.warning(
                                f"Re-authentication appears to have failed for {func.__name__}: "
                                f"retry still returned auth error. Recording failure."
                            )
                            _record_reauth_failure(self.auth)
                            return None
                        
                        # Clear failure history on successful retry
                        _clear_reauth_failures(self.auth)
                        return retry_result
                    else:
                        logger.error(f"Re-authentication failed for {func.__name__}")
                        _record_reauth_failure(self.auth)
                        return None
                else:
                    logger.error("Auth object not found")
                    return None
            
            # Check for error field in response (some APIs return errors this way)
            if isinstance(result, dict) and 'error' in result:
                error_data = result.get('error')
                if isinstance(error_data, dict):
                    if is_auth_error(error_data):
                        # Check if re-auth should be blocked due to recent failures
                        if _check_reauth_failure_rate(self.auth):
                            logger.error(f"Re-authentication blocked for {func.__name__} due to recent failures")
                            return None
                        
                        # Use thread-safe re-authentication
                        if hasattr(self, 'auth'):
                            if _attempt_reauth_thread_safe(self.auth, func.__name__):
                                logger.info(f"Retrying {func.__name__} after re-authentication...")
                                retry_result = func(self, *args, **kwargs)
                                
                                # If retry still fails with auth error, re-auth didn't actually work
                                if isinstance(retry_result, dict) and is_auth_error(retry_result):
                                    logger.warning(
                                        f"Re-authentication appears to have failed for {func.__name__}: "
                                        f"retry still returned auth error. Recording failure."
                                    )
                                    _record_reauth_failure(self.auth)
                                    return None
                                
                                # Clear failure history on successful retry
                                _clear_reauth_failures(self.auth)
                                return retry_result
                            else:
                                logger.error(f"Re-authentication failed for {func.__name__}")
                                _record_reauth_failure(self.auth)
                                return None
                        else:
                            logger.error("Auth object not found")
                            return None
            
            return result
            
        except Exception as e:
            # Check if exception indicates auth failure
            if is_auth_exception(e):
                # Use thread-safe re-authentication
                if hasattr(self, 'auth'):
                    if _attempt_reauth_thread_safe(self.auth, func.__name__):
                        logger.info(f"Retrying {func.__name__} after re-authentication...")
                        # Retry once after successful re-auth
                        try:
                            return func(self, *args, **kwargs)
                        except Exception as retry_error:
                            # If retry also fails, log and return None
                            logger.error(f"Method {func.__name__} failed after re-auth: {retry_error}")
                            return None
                    else:
                        logger.error(f"Re-authentication failed for {func.__name__}")
                        return None
                else:
                    logger.error("Auth object not found")
                    return None
            
            # Re-raise non-auth exceptions
            raise
    
    return wrapper


def call_with_reauth(auth, api_call: Callable, *args, **kwargs) -> Optional[Any]:
    """
    Helper function to call an API with automatic re-authentication.
    
    Useful for standalone functions or non-class methods.
    
    Args:
        auth: Authentication object with force_relogin() method
        api_call: Function to call
        *args: Positional arguments for api_call
        **kwargs: Keyword arguments for api_call
        
    Returns:
        API call result or None if failed
    """
    try:
        result = api_call(*args, **kwargs)
        
        # Check if response indicates auth failure
        if isinstance(result, dict) and is_auth_error(result):
            # Use thread-safe re-authentication
            if _attempt_reauth_thread_safe(auth, "api_call"):
                logger.info("Retrying API call after re-authentication...")
                return api_call(*args, **kwargs)
            else:
                logger.error("Re-authentication failed")
                return None
        
        return result
        
    except Exception as e:
        # Check if exception indicates auth failure
        if is_auth_exception(e):
            # Use thread-safe re-authentication
            if _attempt_reauth_thread_safe(auth, "api_call"):
                logger.info("Retrying API call after re-authentication...")
                try:
                    return api_call(*args, **kwargs)
                except Exception as retry_error:
                    logger.error(f"API call failed after re-auth: {retry_error}")
                    return None
            else:
                logger.error("Re-authentication failed")
                return None
        
        # Re-raise non-auth exceptions
        raise


class AuthGuard:
    """
    Context manager for multiple API calls with shared re-auth handling.
    
    Usage:
        with AuthGuard(auth) as guard:
            result1 = guard.call(api_method1, arg1, arg2)
            result2 = guard.call(api_method2, arg3)
    
    If any call fails with auth error, re-auth is attempted once
    and all subsequent calls use the new session.
    """
    
    def __init__(self, auth):
        self.auth = auth
        self._reauth_attempted = False
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        return False  # Don't suppress exceptions
    
    def call(self, api_call: Callable, *args, **kwargs) -> Optional[Any]:
        """Call an API method with automatic re-auth handling."""
        return call_with_reauth(self.auth, api_call, *args, **kwargs)

