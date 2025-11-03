#!/usr/bin/env python3
"""
Centralized Re-Authentication Handler for Kotak Neo API

Provides a unified mechanism for handling JWT expiry and re-authentication
across all API services (orders, market_data, portfolio, etc.)
"""

import functools
import threading
from typing import Callable, Optional, Dict, Any
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger

try:
    from .auth import KotakNeoAuth
except ImportError:
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth

# Thread-safe re-authentication locks per auth object
_reauth_locks: Dict[int, threading.Lock] = {}
_reauth_locks_lock = threading.Lock()
_reauth_in_progress: Dict[int, threading.Event] = {}


def is_auth_error(response: Any) -> bool:
    """
    Check if a response indicates JWT expiry or authentication failure
    
    Args:
        response: API response (dict, exception, or other)
        
    Returns:
        True if response indicates auth failure, False otherwise
    """
    # Check dict responses
    if isinstance(response, dict):
        code = response.get('code', '')
        message = str(response.get('message', '')).lower()
        description = str(response.get('description', '')).lower()
        error = response.get('error', '')
        
        # Detect JWT expiry patterns
        if (code == '900901' or 
            'invalid jwt token' in description or 
            'invalid credentials' in message or
            'invalid jwt token' in str(error).lower() or
            'invalid credentials' in str(error).lower()):
            return True
    
    # Check exception messages
    if isinstance(response, Exception):
        error_str = str(response).lower()
        if ('jwt' in error_str and ('invalid' in error_str or 'expired' in error_str)) or \
           'unauthorized' in error_str or \
           'invalid credentials' in error_str:
            return True
    
    # Check string responses
    if isinstance(response, str):
        error_str = response.lower()
        if ('jwt' in error_str and ('invalid' in error_str or 'expired' in error_str)) or \
           'unauthorized' in error_str or \
           'invalid credentials' in error_str:
            return True
    
    return False


def _get_reauth_lock(auth: KotakNeoAuth) -> threading.Lock:
    """
    Get thread-safe lock for a specific auth object
    
    Args:
        auth: KotakNeoAuth instance
        
    Returns:
        threading.Lock for this auth object
    """
    # Use id() to uniquely identify auth object
    auth_id = id(auth)
    
    with _reauth_locks_lock:
        if auth_id not in _reauth_locks:
            _reauth_locks[auth_id] = threading.Lock()
        return _reauth_locks[auth_id]


def _get_reauth_event(auth: KotakNeoAuth) -> threading.Event:
    """
    Get event to signal re-authentication in progress
    
    Args:
        auth: KotakNeoAuth instance
        
    Returns:
        threading.Event for this auth object
    """
    auth_id = id(auth)
    
    with _reauth_locks_lock:
        if auth_id not in _reauth_in_progress:
            _reauth_in_progress[auth_id] = threading.Event()
        return _reauth_in_progress[auth_id]


def _attempt_reauth_thread_safe(auth: KotakNeoAuth, method_name: str) -> bool:
    """
    Thread-safe re-authentication attempt
    
    Only one thread will perform re-auth, others will wait for it to complete
    
    Args:
        auth: KotakNeoAuth instance
        method_name: Name of method that triggered re-auth (for logging)
        
    Returns:
        True if re-auth successful, False otherwise
    """
    auth_id = id(auth)
    lock = _get_reauth_lock(auth)
    reauth_event = _get_reauth_event(auth)
    
    # Try to acquire lock (non-blocking check first)
    acquired = lock.acquire(blocking=False)
    
    if acquired:
        # This thread got the lock - perform re-auth
        # Clear event first (in case it was set from a previous re-auth that expired again)
        reauth_event.clear()
        try:
            logger.warning(f"🔒 Thread-safe re-auth initiated by {method_name}")
            
            if hasattr(auth, 'force_relogin') and auth.force_relogin():
                logger.info(f"✅ Re-authentication successful (thread-safe)")
                reauth_event.set()  # Signal that re-auth is complete and successful
                return True
            else:
                logger.error(f"❌ Re-authentication failed")
                # Don't set event on failure - other threads will try
                return False
        finally:
            lock.release()
    else:
        # Another thread is already doing re-auth - wait for it
        logger.debug(f"⏳ {method_name} waiting for concurrent re-authentication...")
        
        # Wait for re-auth event to be set (with timeout to avoid deadlock)
        # This means another thread is completing re-auth
        if reauth_event.wait(timeout=30.0):
            # Re-auth completed by another thread
            logger.debug(f"✅ {method_name} detected re-authentication completed by another thread")
            return True
        else:
            # Timeout - re-auth taking too long or failed
            # Try to acquire lock and check status
            logger.debug(f"⏳ {method_name} re-auth wait timeout, checking lock...")
            
            # Try blocking acquire with shorter timeout
            if lock.acquire(blocking=True, timeout=5.0):
                try:
                    # Check if re-auth is still needed (maybe previous thread failed)
                    # If event is not set, previous re-auth failed - try again
                    if not reauth_event.is_set():
                        logger.warning(f"🔒 Previous re-auth failed, retrying from {method_name}")
                        if hasattr(auth, 'force_relogin') and auth.force_relogin():
                            reauth_event.set()
                            return True
                    else:
                        # Event is set - re-auth succeeded
                        return True
                finally:
                    lock.release()
            
            # Timeout or failure
            logger.warning(f"⚠️ {method_name} re-auth wait timeout or failed")
            return False


def handle_reauth(func: Callable) -> Callable:
    """
    Decorator to automatically handle re-authentication on JWT expiry
    
    Thread-safe: If multiple threads detect JWT expiry simultaneously,
    only one will perform re-auth, others will wait and retry.
    
    Usage:
        @handle_reauth
        def my_api_method(self, ...):
            # Your API call
            return response
    
    The decorator will:
    1. Execute the function
    2. Check if response indicates auth failure
    3. Attempt thread-safe re-authentication if needed
    4. Retry the function once after re-auth
    5. Return the result or None if re-auth fails
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Get auth object from self (assuming classes have self.auth)
        if not hasattr(self, 'auth') or not isinstance(self.auth, KotakNeoAuth):
            # If no auth object, call function directly
            return func(self, *args, **kwargs)
        
        auth = self.auth
        method_name = func.__name__
        
        # Try the function first
        try:
            result = func(self, *args, **kwargs)
            
            # Check if result indicates auth failure
            if is_auth_error(result):
                logger.warning(f"❌ JWT token expired in {method_name} - attempting re-authentication...")
                
                # Attempt thread-safe re-authentication
                if _attempt_reauth_thread_safe(auth, method_name):
                    logger.info(f"✅ Re-authentication successful - retrying {method_name}")
                    
                    # Retry once after re-auth
                    try:
                        return func(self, *args, **kwargs)
                    except Exception as e:
                        logger.error(f"❌ {method_name} still failing after re-auth: {e}")
                        return None
                else:
                    logger.error(f"❌ Re-authentication failed for {method_name}")
                    return None
            
            return result
            
        except Exception as e:
            # Check if exception indicates auth failure
            if is_auth_error(e):
                logger.warning(f"❌ JWT token expired in {method_name} (exception) - attempting re-authentication...")
                
                # Attempt thread-safe re-authentication
                if _attempt_reauth_thread_safe(auth, method_name):
                    logger.info(f"✅ Re-authentication successful - retrying {method_name}")
                    
                    # Retry once after re-auth
                    try:
                        return func(self, *args, **kwargs)
                    except Exception as retry_e:
                        logger.error(f"❌ {method_name} still failing after re-auth: {retry_e}")
                        return None
                else:
                    logger.error(f"❌ Re-authentication failed for {method_name}")
                    return None
            
            # Re-raise if not auth error
            raise
    
    return wrapper


def call_with_reauth(auth: KotakNeoAuth, api_call: Callable, *args, **kwargs) -> Any:
    """
    Helper function to call an API method with automatic thread-safe re-authentication
    
    Usage:
        result = call_with_reauth(self.auth, self._make_api_call, param1, param2)
    
    Args:
        auth: KotakNeoAuth instance
        api_call: Function to call
        *args, **kwargs: Arguments to pass to api_call
        
    Returns:
        Result from api_call or None if re-auth fails
    """
    if not isinstance(auth, KotakNeoAuth):
        logger.error("Invalid auth object provided")
        return None
    
    try:
        # Try the API call
        result = api_call(*args, **kwargs)
        
        # Check if result indicates auth failure
        if is_auth_error(result):
            logger.warning("❌ JWT token expired - attempting re-authentication...")
            
            # Attempt thread-safe re-authentication
            if _attempt_reauth_thread_safe(auth, "call_with_reauth"):
                logger.info("✅ Re-authentication successful - retrying API call")
                
                # Retry once after re-auth
                try:
                    return api_call(*args, **kwargs)
                except Exception as e:
                    logger.error(f"❌ API call still failing after re-auth: {e}")
                    return None
            else:
                logger.error("❌ Re-authentication failed")
                return None
        
        return result
        
    except Exception as e:
        # Check if exception indicates auth failure
        if is_auth_error(e):
            logger.warning("❌ JWT token expired (exception) - attempting re-authentication...")
            
            # Attempt thread-safe re-authentication
            if _attempt_reauth_thread_safe(auth, "call_with_reauth"):
                logger.info("✅ Re-authentication successful - retrying API call")
                
                # Retry once after re-auth
                try:
                    return api_call(*args, **kwargs)
                except Exception as retry_e:
                    logger.error(f"❌ API call still failing after re-auth: {retry_e}")
                    return None
            else:
                logger.error("❌ Re-authentication failed")
                return None
        
        # Re-raise if not auth error
        raise


class AuthGuard:
    """
    Context manager for API calls with automatic re-authentication
    
    Usage:
        with AuthGuard(self.auth):
            result = self.client.some_method()
            if AuthGuard.is_auth_error(result):
                # Will be handled automatically
                pass
    """
    
    def __init__(self, auth: KotakNeoAuth):
        self.auth = auth
        self.retried = False
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Handle exceptions
        if exc_type and is_auth_error(exc_val):
            if not self.retried:
                self.retried = True
                logger.warning("❌ JWT token expired (exception) - attempting re-authentication...")
                
                if hasattr(self.auth, 'force_relogin') and self.auth.force_relogin():
                    logger.info("✅ Re-authentication successful")
                    # Return False to retry (but context manager doesn't support this)
                    # So we'll need to handle in the calling code
                    return False
                else:
                    logger.error("❌ Re-authentication failed")
        
        return False
    
    @staticmethod
    def is_auth_error(response: Any) -> bool:
        """Check if response indicates auth failure"""
        return is_auth_error(response)

