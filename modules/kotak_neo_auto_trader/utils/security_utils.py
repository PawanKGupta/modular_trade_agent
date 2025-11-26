"""
Security utilities for masking sensitive data in logs and outputs.
"""

import re
from typing import Any


def mask_sensitive_value(value: str, visible_chars: int = 4) -> str:
    """
    Mask a sensitive value, showing only first/last few characters.

    Args:
        value: The sensitive string to mask
        visible_chars: Number of characters to show at start and end

    Returns:
        Masked string like "abc...xyz"

    Example:
        >>> mask_sensitive_value("my_secret_token_12345", 3)
        "my_...345"
    """
    if not value or not isinstance(value, str):
        return "***"

    if len(value) <= visible_chars * 2:
        return "*" * len(value)

    return f"{value[:visible_chars]}...{value[-visible_chars:]}"


def mask_token_in_dict(data: dict[str, Any], sensitive_keys: set = None) -> dict[str, Any]:
    """
    Recursively mask sensitive keys in a dictionary.

    Args:
        data: Dictionary potentially containing sensitive data
        sensitive_keys: Set of key names to mask (case-insensitive)

    Returns:
        New dictionary with sensitive values masked

    Example:
        >>> mask_token_in_dict({"user": "john", "token": "secret123"})
        {"user": "john", "token": "sec...123"}
    """
    if sensitive_keys is None:
        sensitive_keys = {
            "token",
            "access_token",
            "session_token",
            "auth_token",
            "bearer_token",
            "jwt",
            "sid",
            "hsservid",
            "jwttoken",
            "password",
            "mpin",
            "secret",
            "api_key",
            "consumer_secret",
            "authorization",
            "api_secret",
        }

    if not isinstance(data, dict):
        return data

    masked = {}
    for key, value in data.items():
        key_lower = key.lower()

        # Check if this key is sensitive
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            if isinstance(value, str):
                masked[key] = mask_sensitive_value(value)
            else:
                masked[key] = "***"
        elif isinstance(value, dict):
            # Recursively mask nested dictionaries
            masked[key] = mask_token_in_dict(value, sensitive_keys)
        elif isinstance(value, list):
            # Handle lists of dictionaries
            masked[key] = [
                mask_token_in_dict(item, sensitive_keys) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            masked[key] = value

    return masked


def sanitize_log_message(message: str) -> str:
    """
    Remove potential tokens/secrets from log messages using pattern matching.

    Args:
        message: Log message that might contain sensitive data

    Returns:
        Sanitized message with tokens masked

    Example:
        >>> sanitize_log_message("Got token: Bearer eyJ0eXAiOiJK...")
        "Got token: Bearer eyJ...***"
    """
    # Pattern for JWT tokens
    message = re.sub(
        r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", "eyJ...***", message
    )

    # Pattern for long alphanumeric tokens (40+ chars)
    message = re.sub(r"[A-Za-z0-9_-]{40,}", lambda m: f"{m.group(0)[:8]}...***", message)

    return message


def safe_log_dict(data: dict[str, Any], sensitive_keys: set = None) -> str:
    """
    Convert dictionary to safe string for logging (with sensitive data masked).

    Args:
        data: Dictionary to convert to log-safe string
        sensitive_keys: Set of key names to mask

    Returns:
        String representation with sensitive data masked

    Example:
        >>> safe_log_dict({"user": "john", "token": "secret123"})
        "{'user': 'john', 'token': 'sec...123'}"
    """
    masked = mask_token_in_dict(data, sensitive_keys)
    return str(masked)
