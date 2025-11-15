#!/usr/bin/env python3
"""
Authentication Utility Functions
Centralized re-authentication handling for API calls
"""

from typing import Optional, Dict, Any, Callable
from utils.logger import logger


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
    
    # Check for JWT token errors in description
    if 'invalid jwt token' in description or 'jwt token expired' in description:
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


def check_and_reauth(auth, response_or_exception: Any, retry_count: int = 0) -> bool:
    """
    Check if response/exception indicates auth failure and attempt re-authentication.
    
    Args:
        auth: Authentication object with force_relogin() method
        response_or_exception: API response or exception
        retry_count: Current retry count (0 = first attempt)
        
    Returns:
        True if re-auth was attempted and successful, False otherwise
    """
    # Check if it's an auth error
    is_error = False
    if isinstance(response_or_exception, dict):
        is_error = is_auth_error(response_or_exception)
    elif isinstance(response_or_exception, Exception):
        is_error = is_auth_exception(response_or_exception)
    
    if not is_error:
        return False
    
    # Prevent infinite retry loops
    if retry_count > 0:
        logger.error("Authentication failed after re-authentication attempt")
        return False
    
    # Attempt re-authentication
    logger.warning("JWT token expired or invalid - attempting re-authentication...")
    
    if not hasattr(auth, 'force_relogin'):
        logger.error("Auth object does not have force_relogin() method")
        return False
    
    try:
        if auth.force_relogin():
            logger.info("Re-authentication successful")
            return True
        else:
            logger.error("Re-authentication failed")
            return False
    except Exception as e:
        logger.error(f"Re-authentication exception: {e}")
        return False


def with_reauth_retry(
    auth,
    api_call: Callable,
    *args,
    retry_count: int = 0,
    max_retries: int = 1,
    **kwargs
) -> Optional[Any]:
    """
    Execute API call with automatic re-authentication on auth failures.
    
    This is a decorator-like wrapper that handles re-auth automatically.
    
    Args:
        auth: Authentication object with force_relogin() method
        api_call: Function to call (should be a method that accepts _retry_count parameter)
        *args: Positional arguments for api_call
        retry_count: Current retry count (internal use)
        max_retries: Maximum retry attempts (default: 1)
        **kwargs: Keyword arguments for api_call (excluding _retry_count)
        
    Returns:
        API call result or None if failed
    """
    # Prevent infinite retry loops
    if retry_count > max_retries:
        logger.error(f"Max retries ({max_retries}) exceeded for API call")
        return None
    
    try:
        # Call API with retry count parameter
        result = api_call(*args, _retry_count=retry_count, **kwargs)
        
        # Check if response indicates auth failure
        if isinstance(result, dict) and check_and_reauth(auth, result, retry_count):
            # Retry once after successful re-auth
            logger.info("Retrying API call after re-authentication...")
            return with_reauth_retry(auth, api_call, *args, retry_count=retry_count + 1, max_retries=max_retries, **kwargs)
        
        return result
        
    except Exception as e:
        # Check if exception indicates auth failure
        if is_auth_exception(e):
            if check_and_reauth(auth, e, retry_count):
                # Retry once after successful re-auth
                logger.info("Retrying API call after re-authentication...")
                return with_reauth_retry(auth, api_call, *args, retry_count=retry_count + 1, max_retries=max_retries, **kwargs)
        
        # Re-raise non-auth exceptions
        raise
