"""
Kotak Neo Broker Adapter
Adapts Kotak Neo SDK to IBrokerGateway interface
"""

import inspect

# Import from existing legacy modules
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger  # noqa: E402

# Import timeout utilities for SDK call protection
try:
    from modules.kotak_neo_auto_trader.utils.timeout_utils import (  # noqa: E402, PLC0415
        DEFAULT_SDK_TIMEOUT,
        call_with_timeout,
    )
except ImportError:
    # Fallback if timeout_utils not available
    def call_with_timeout(func, timeout=30.0, timeout_error_message="SDK call timed out"):
        # No timeout protection - call directly
        return func()

    DEFAULT_SDK_TIMEOUT = 30.0

from ...domain import (  # noqa: E402
    Exchange,
    Holding,
    IBrokerGateway,
    Money,
    Order,
    OrderStatus,
    OrderType,
    OrderVariety,
    TransactionType,
)

# Import auth handler utilities for re-authentication
try:
    from modules.kotak_neo_auto_trader.auth_handler import (  # noqa: E402, PLC0415
        _attempt_reauth_thread_safe,
        _check_reauth_failure_rate,
        _record_reauth_failure,
        is_auth_error,
        is_auth_exception,
    )
except ImportError:
    # Fallback if auth_handler not available (shouldn't happen in normal usage)
    def is_auth_error(response):  # noqa: ARG001
        return False

    def is_auth_exception(exception):  # noqa: ARG001
        return False

    def _attempt_reauth_thread_safe(auth, method_name):  # noqa: ARG001
        return False

    def _check_reauth_failure_rate(auth):  # noqa: ARG001
        return False  # Don't block if import fails

    def _record_reauth_failure(auth):  # noqa: ARG001
        pass  # No-op if import fails


class BrokerServiceUnavailableError(Exception):
    """
    Exception raised when broker API is unavailable (maintenance, downtime, etc.)
    This should be caught by API endpoints and returned as 503 Service Unavailable
    """

    def __init__(
        self,
        message: str = "Broker service is temporarily unavailable",
        original_error: Exception | None = None,
    ):
        self.message = message
        self.original_error = original_error
        # Note: The message passed here is already the extracted API error message
        # (if available) or the default message, as extracted by _get_service_unavailable_message()
        super().__init__(self.message)


def _get_service_unavailable_message(error: Exception, default_message: str) -> str:
    """
    Get error message for service unavailable, preferring actual API error message.

    Args:
        error: The original exception from the API
        default_message: Default message to use if API error cannot be extracted

    Returns:
        Error message to display (API error if available, otherwise default)
    """
    api_error_msg = _extract_api_error_message(error)
    return api_error_msg if api_error_msg else default_message


def _extract_api_error_message(error: Exception) -> str | None:
    """
    Extract error message from API response if available.

    Args:
        error: The original exception from the API

    Returns:
        Extracted error message from API response, or None if not available
    """
    try:
        error_str = str(error)

        # Check if error has response attribute (HTTP errors from requests/urllib3)
        if hasattr(error, "response"):
            response = getattr(error, "response", None)
            if response:
                # Try to get response data
                if hasattr(response, "json"):
                    try:
                        data = response.json()
                        if isinstance(data, dict):
                            # Try error array first (before checking simple error field)
                            # This handles cases like {"error": [{"message": "..."}]}
                            if (
                                "error" in data
                                and isinstance(data["error"], list)
                                and len(data["error"]) > 0
                            ):
                                err_item = data["error"][0]
                                if isinstance(err_item, dict):
                                    return err_item.get("message", str(err_item))
                                return str(err_item)
                            # Try common error message fields (excluding "error" if it's not a list)
                            for field in ["message", "description", "detail", "msg"]:
                                if field in data and data[field]:
                                    return str(data[field])
                            # Try "error" field only if it's not a list (already handled above)
                            if (
                                "error" in data
                                and not isinstance(data["error"], list)
                                and data["error"]
                            ):
                                return str(data["error"])
                    except Exception:
                        pass
                # Try response text
                if hasattr(response, "text"):
                    try:
                        text = response.text
                        if text and len(text) < 500:  # Reasonable length
                            return text
                    except Exception:
                        pass

        # Check if error message contains structured data
        # Look for JSON-like patterns in error string
        if "{" in error_str and "}" in error_str:
            try:
                import json

                # Try to find JSON in error string
                start = error_str.find("{")
                end = error_str.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = error_str[start:end]
                    data = json.loads(json_str)
                    if isinstance(data, dict):
                        for field in ["message", "error", "description", "detail", "msg"]:
                            if field in data and data[field]:
                                return str(data[field])
            except Exception:
                pass

        # Return the error string itself if it looks like an API message
        # (not just a generic connection error)
        if (
            error_str
            and len(error_str) < 200
            and not any(
                generic in error_str.lower()
                for generic in [
                    "connection refused",
                    "network is unreachable",
                    "failed to establish",
                ]
            )
        ):
            return error_str

    except Exception:
        pass

    return None


def _is_network_connectivity_error(error: Exception) -> bool:
    """
    Check if an error indicates local network connectivity issues (not broker service issue).

    Args:
        error: Exception to check

    Returns:
        True if error indicates local network connectivity issue, False otherwise
    """
    error_str = str(error).lower()

    # Local network connectivity issues (Docker/container network problems)
    network_connectivity_indicators = [
        "network is unreachable",  # Errno 101 - local network issue
        "name resolution failed",  # DNS issue
        "dns",  # DNS resolution failure
        "errno 101",  # Network unreachable error code
    ]

    for indicator in network_connectivity_indicators:
        if indicator in error_str:
            return True

    return False


def _is_service_unavailable_error(error: Exception) -> bool:
    """
    Check if an error indicates broker service is unavailable (maintenance, downtime, etc.)

    Args:
        error: Exception to check

    Returns:
        True if error indicates service unavailable, False otherwise
    """
    # First check if it's a local network connectivity issue (not a broker service issue)
    if _is_network_connectivity_error(error):
        return False  # Don't treat local network issues as service unavailable

    error_str = str(error).lower()
    error_type = type(error).__name__.lower()

    # Check for service unavailable indicators (actual broker service issues)
    service_unavailable_indicators = [
        "service unavailable",
        "503",
        "502",
        "504",
        "gateway timeout",
        "bad gateway",
        "maintenance",
        "downtime",
        "server error",
        "internal server error",
        "connection refused",  # Server actively refusing (different from network unreachable)
    ]

    # Check error message
    for indicator in service_unavailable_indicators:
        if indicator in error_str:
            return True

    # Check error type
    if "httperror" in error_type or "connectionerror" in error_type:
        # Check if it's a 5xx error (actual HTTP server error)
        if "50" in error_str:
            return True

    return False


class KotakNeoBrokerAdapter(IBrokerGateway):
    """
    Adapter for Kotak Neo API

    Implements IBrokerGateway interface using existing auth and SDK
    Adapts between domain entities and raw SDK responses
    """

    def __init__(self, auth_handler):
        """
        Initialize adapter with auth handler

        Args:
            auth_handler: Authentication handler (from infrastructure.session)
        """
        self.auth_handler = auth_handler
        self._client = None
        self._connected = False

    # Connection Management

    def connect(self) -> bool:
        """Establish connection to broker"""
        try:
            if self.auth_handler.login():
                client = self.auth_handler.get_client()
                if client and self.auth_handler.is_authenticated():
                    self._client = client
                    self._connected = True
                    logger.info("? Connected to Kotak Neo broker")
                    return True
                else:
                    logger.error("? Connection failed: Client not authenticated after login")
                    return False
            return False
        except Exception as e:
            logger.error(f"? Connection failed: {e}")
            return False

    def disconnect(self) -> bool:
        """Disconnect from broker"""
        try:
            if self.auth_handler.logout():
                self._client = None
                self._connected = False
                logger.info("? Disconnected from Kotak Neo broker")
                return True
            return False
        except Exception as e:
            logger.error(f"? Disconnect failed: {e}")
            return False

    def is_connected(self) -> bool:
        """Check if currently connected"""
        return self._connected and self._client is not None

    def _ensure_fresh_client(self):
        """
        Phase -1: Always get fresh client before API calls.

        Ensures we always use the latest client instance, even if re-auth
        happened in another thread. This prevents client reference staleness.

        Raises:
            ConnectionError: If not authenticated or no client available
        """
        if not self.auth_handler or not self.auth_handler.is_authenticated():
            raise ConnectionError("Not authenticated")

        # Always get fresh client (don't rely on cache)
        fresh_client = self.auth_handler.get_client()
        if not fresh_client:
            raise ConnectionError("No authenticated client available")

        self._client = fresh_client  # Update cache
        return fresh_client

    # Order Management

    def place_order(self, order: Order) -> str:
        """
        Place an order and return order ID with automatic re-authentication on session expiry.

        Returns:
            Order ID string

        Raises:
            RuntimeError: If order placement fails after all retries
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to broker")

        # Phase -1: Always ensure fresh client before API calls
        self._ensure_fresh_client()

        # Build payload from domain order
        payload = self._build_order_payload(order)

        max_retries = 1  # Retry once after re-auth
        for attempt in range(max_retries + 1):
            # Try multiple SDK method names (resilience pattern from legacy code)
            for method_name in ["place_order", "order_place", "placeorder"]:
                try:
                    if not hasattr(self._client, method_name):
                        continue

                    method = getattr(self._client, method_name)
                    params = self._adapt_payload_to_method(method, payload)

                    logger.info(
                        f"? Placing {order.transaction_type.value} order: "
                        f"{order.symbol} x{order.quantity}"
                    )

                    # Call with timeout protection (SDK might hang)
                    try:
                        response = call_with_timeout(
                            lambda: method(**params),
                            timeout=DEFAULT_SDK_TIMEOUT,
                            timeout_error_message=f"place_order() call to {method_name}() timed out",
                        )
                    except TimeoutError as timeout_error:
                        logger.error(
                            f"SDK call timed out in place_order: {timeout_error}. "
                            "This may indicate broker API is slow or unreachable."
                        )
                        # Check if this is a service unavailable scenario (timeout after retries)
                        if attempt >= max_retries:
                            # After all retries, timeout likely means service is unavailable
                            error_message = _get_service_unavailable_message(
                                timeout_error,
                                "Broker service is temporarily unavailable. "
                                "The API did not respond within the expected time. "
                                "This may be due to maintenance or high load. Please try again later.",
                            )
                            raise BrokerServiceUnavailableError(
                                error_message, original_error=timeout_error
                            ) from timeout_error
                        # If timeout occurs, try refreshing client from auth handler
                        # The client might be stale even if auth handler reports authenticated
                        if self.auth_handler and self.auth_handler.is_authenticated():
                            fresh_client = self.auth_handler.get_client()
                            if fresh_client:
                                self._client = fresh_client
                                logger.info("Refreshed client after timeout in place_order")
                                if attempt < max_retries:
                                    break  # Retry outer loop with fresh client
                        # Try next method or retry after re-auth
                        if attempt < max_retries:
                            break  # Retry outer loop
                        continue  # Try next method
                    except Exception as call_error:
                        # Check if it's a service unavailable error (maintenance, downtime, etc.)
                        if _is_service_unavailable_error(call_error):
                            logger.error(
                                f"Broker service unavailable detected in place_order: {call_error}"
                            )
                            # Extract actual API error message if available
                            error_message = _get_service_unavailable_message(
                                call_error,
                                "Broker service is temporarily unavailable. "
                                "This may be due to scheduled maintenance or service issues. "
                                "Please try again later.",
                            )
                            raise BrokerServiceUnavailableError(
                                error_message, original_error=call_error
                            ) from call_error

                        # Check if it's a connection error (might indicate missing session)
                        error_str = str(call_error).lower()
                        is_connection_error = (
                            "connection refused" in error_str
                            or "connection error" in error_str
                            or "newconnectionerror" in error_str
                            or "failed to establish" in error_str
                        )

                        # If connection error, try refreshing client from auth handler
                        # The client might be missing the session (empty sId in URL)
                        if (
                            is_connection_error
                            and self.auth_handler
                            and self.auth_handler.is_authenticated()
                        ):
                            fresh_client = self.auth_handler.get_client()
                            if fresh_client:
                                self._client = fresh_client
                                logger.warning(
                                    f"Connection error detected in place_order: {call_error}. "
                                    "Refreshed client from auth handler to ensure session is used."
                                )
                                if attempt < max_retries:
                                    break  # Retry outer loop with fresh client

                        # Check if it's an auth error
                        if is_auth_exception(call_error):
                            logger.warning(
                                f"Authentication error in place_order: {call_error}. "
                                "Checking re-authentication failure rate..."
                            )
                            # Check if re-auth should be blocked due to recent failures
                            if self.auth_handler and _check_reauth_failure_rate(self.auth_handler):
                                logger.error(
                                    "Re-authentication blocked for place_order due to recent failures. "
                                    "Please check authentication credentials or API status."
                                )
                                raise RuntimeError(
                                    "Failed to place order: re-authentication blocked"
                                )

                            # Attempt re-auth and retry
                            if (
                                attempt < max_retries
                                and self.auth_handler
                                and hasattr(self.auth_handler, "force_relogin")
                            ):
                                if _attempt_reauth_thread_safe(self.auth_handler, "place_order"):
                                    # Update client after re-auth - ensure it's authenticated
                                    new_client = self.auth_handler.get_client()
                                    if new_client and self.auth_handler.is_authenticated():
                                        self._client = new_client
                                        logger.info(
                                            "Re-authentication successful, client updated, retrying place_order..."
                                        )
                                        break  # Retry the outer loop
                                    else:
                                        logger.error(
                                            "Re-authentication reported success but client is not authenticated"
                                        )
                                        _record_reauth_failure(self.auth_handler)
                                        raise RuntimeError(
                                            "Failed to place order: re-authentication failed"
                                        )
                                else:
                                    logger.error("Re-authentication failed for place_order")
                                    _record_reauth_failure(self.auth_handler)
                                    raise RuntimeError(
                                        "Failed to place order: re-authentication failed"
                                    )
                            else:
                                logger.error(
                                    "Max retries reached or no auth handler for place_order"
                                )
                                raise RuntimeError("Failed to place order: max retries reached")

                            # After all retries, if it's still a connection error, treat as service unavailable
                            if is_connection_error and attempt >= max_retries:
                                error_message = _get_service_unavailable_message(
                                    call_error,
                                    "Broker service is temporarily unavailable. "
                                    "Unable to establish connection to the broker API. "
                                    "This may be due to maintenance or network issues. Please try again later.",
                                )
                                raise BrokerServiceUnavailableError(
                                    error_message, original_error=call_error
                                ) from call_error

                            # Re-raise non-auth exceptions
                            raise

                    # Check response for auth errors
                    if isinstance(response, dict) and is_auth_error(response):
                        logger.warning(
                            "Authentication error detected in place_order response. "
                            "Checking re-authentication failure rate..."
                        )
                        # Check if re-auth should be blocked due to recent failures
                        if self.auth_handler and _check_reauth_failure_rate(self.auth_handler):
                            logger.error(
                                "Re-authentication blocked for place_order due to recent failures. "
                                "Please check authentication credentials or API status."
                            )
                            raise RuntimeError("Failed to place order: re-authentication blocked")

                        # Attempt re-auth and retry
                        if (
                            attempt < max_retries
                            and self.auth_handler
                            and hasattr(self.auth_handler, "force_relogin")
                        ):
                            if _attempt_reauth_thread_safe(self.auth_handler, "place_order"):
                                # Update client after re-auth
                                self._client = self.auth_handler.get_client()
                                logger.info("Re-authentication successful, retrying place_order...")
                                break  # Retry the outer loop
                            else:
                                logger.error("Re-authentication failed for place_order")
                                _record_reauth_failure(self.auth_handler)
                                raise RuntimeError(
                                    "Failed to place order: re-authentication failed"
                                )
                        else:
                            logger.error("Max retries reached or no auth handler for place_order")
                            raise RuntimeError("Failed to place order: max retries reached")

                    # Check for errors
                    if self._is_error_response(response):
                        logger.error(f"? Order rejected: {response}")
                        continue  # Try next method

                    # Extract order ID
                    order_id = self._extract_order_id(response)
                    if order_id:
                        logger.info(f"? Order placed: {order_id}")
                        return order_id

                except RuntimeError:
                    # Re-raise RuntimeError (from re-auth failures)
                    raise
                except Exception as e:
                    logger.warning(f"[WARN]? Method {method_name} failed: {e}")
                    continue  # Try next method

        raise RuntimeError("Failed to place order with all available methods")

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order with automatic re-authentication on session expiry.

        Returns:
            True if order was cancelled successfully, False otherwise
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to broker")

        # Refresh client from auth handler before API calls to ensure latest session is used
        # The session (sId) is embedded in the SDK client when created during login
        # Since session is valid for ~1 hour, we reuse it but always get fresh client to ensure session is present
        # After re-auth, auth.client becomes a NEW object, so we need to refresh to get the new session
        # Strategy: Always refresh if client changed (re-auth) or if no client exists
        # In production: auth.get_client() returns auth.client (same object until re-auth, then new object)
        # In tests: Tests should configure auth_handler.get_client() to return the same mock_client
        if self.auth_handler and self.auth_handler.is_authenticated():
            fresh_client = self.auth_handler.get_client()
            if fresh_client:
                # Always refresh if: (1) no client, OR (2) client changed (re-auth happened)
                # Same client object = no-op refresh (ensures we have latest session)
                if self._client is None or fresh_client is not self._client:
                    self._client = fresh_client
                    logger.debug(
                        "Refreshed client from auth handler for cancel_order to ensure session is used"
                    )

        max_retries = 1  # Retry once after re-auth
        for attempt in range(max_retries + 1):
            for method_name in ["cancel_order", "order_cancel", "cancelOrder"]:
                try:
                    if not hasattr(self._client, method_name):
                        continue

                    method = getattr(self._client, method_name)

                    # Try to determine parameter name
                    try:
                        params = set(inspect.signature(method).parameters.keys())
                        payload = {}
                        for key in ["order_id", "orderId", "neoOrdNo", "ordId", "id"]:
                            if key in params:
                                payload[key] = order_id
                                break

                        # Call with timeout protection (SDK might hang)
                        try:
                            if not payload:
                                # Try positional
                                call_with_timeout(
                                    lambda: method(order_id),
                                    timeout=DEFAULT_SDK_TIMEOUT,
                                    timeout_error_message=f"cancel_order() call to {method_name}() timed out",
                                )
                            else:
                                call_with_timeout(
                                    lambda: method(**payload),
                                    timeout=DEFAULT_SDK_TIMEOUT,
                                    timeout_error_message=f"cancel_order() call to {method_name}() timed out",
                                )
                        except TimeoutError as timeout_error:
                            logger.error(
                                f"SDK call timed out in cancel_order: {timeout_error}. "
                                "This may indicate broker API is slow or unreachable."
                            )
                            # Check if this is a service unavailable scenario (timeout after retries)
                            if attempt >= max_retries:
                                # After all retries, timeout likely means service is unavailable
                                raise BrokerServiceUnavailableError(
                                    "Broker service is temporarily unavailable. "
                                    "The API did not respond within the expected time. "
                                    "This may be due to maintenance or high load. Please try again later."
                                ) from timeout_error
                            # If timeout occurs, try refreshing client from auth handler
                            # The client might be stale even if auth handler reports authenticated
                            if self.auth_handler and self.auth_handler.is_authenticated():
                                fresh_client = self.auth_handler.get_client()
                                if fresh_client:
                                    self._client = fresh_client
                                    logger.info("Refreshed client after timeout in cancel_order")
                                    if attempt < max_retries:
                                        break  # Retry outer loop with fresh client
                            # Try next method or retry after re-auth
                            if attempt < max_retries:
                                break  # Retry outer loop
                            continue  # Try next method
                        except Exception as call_error:
                            # Check if it's a service unavailable error (maintenance, downtime, etc.)
                            if _is_service_unavailable_error(call_error):
                                logger.error(
                                    f"Broker service unavailable detected in cancel_order: {call_error}"
                                )
                                raise BrokerServiceUnavailableError(
                                    "Broker service is temporarily unavailable. "
                                    "This may be due to scheduled maintenance or service issues. "
                                    "Please try again later."
                                ) from call_error

                            # Check if it's a connection error (might indicate missing session)
                            error_str = str(call_error).lower()
                            is_connection_error = (
                                "connection refused" in error_str
                                or "connection error" in error_str
                                or "newconnectionerror" in error_str
                                or "failed to establish" in error_str
                            )

                            # If connection error, try refreshing client from auth handler
                            # The client might be missing the session (empty sId in URL)
                            if (
                                is_connection_error
                                and self.auth_handler
                                and self.auth_handler.is_authenticated()
                            ):
                                fresh_client = self.auth_handler.get_client()
                                if fresh_client:
                                    self._client = fresh_client
                                    logger.warning(
                                        f"Connection error detected in cancel_order: {call_error}. "
                                        "Refreshed client from auth handler to ensure session is used."
                                    )
                                    if attempt < max_retries:
                                        break  # Retry outer loop with fresh client

                            # Check if it's an auth error
                            if is_auth_exception(call_error):
                                logger.warning(
                                    f"Authentication error in cancel_order: {call_error}. "
                                    "Checking re-authentication failure rate..."
                                )
                                # Check if re-auth should be blocked due to recent failures
                                if self.auth_handler and _check_reauth_failure_rate(
                                    self.auth_handler
                                ):
                                    logger.error(
                                        "Re-authentication blocked for cancel_order due to recent failures. "
                                        "Please check authentication credentials or API status."
                                    )
                                    return False

                                # Attempt re-auth and retry
                                if (
                                    attempt < max_retries
                                    and self.auth_handler
                                    and hasattr(self.auth_handler, "force_relogin")
                                ):
                                    if _attempt_reauth_thread_safe(
                                        self.auth_handler, "cancel_order"
                                    ):
                                        # Update client after re-auth - ensure it's authenticated
                                        new_client = self.auth_handler.get_client()
                                        if new_client and self.auth_handler.is_authenticated():
                                            self._client = new_client
                                            logger.info(
                                                "Re-authentication successful, client updated, retrying cancel_order..."
                                            )
                                            break  # Retry the outer loop
                                        else:
                                            logger.error(
                                                "Re-authentication reported success but client is not authenticated"
                                            )
                                            _record_reauth_failure(self.auth_handler)
                                            return False
                                    else:
                                        logger.error("Re-authentication failed for cancel_order")
                                        _record_reauth_failure(self.auth_handler)
                                        return False
                                else:
                                    logger.error(
                                        "Max retries reached or no auth handler for cancel_order"
                                    )
                                    return False

                            # After all retries, if it's still a connection error, treat as service unavailable
                            if is_connection_error and attempt >= max_retries:
                                error_message = _get_service_unavailable_message(
                                    call_error,
                                    "Broker service is temporarily unavailable. "
                                    "Unable to establish connection to the broker API. "
                                    "This may be due to maintenance or network issues. Please try again later.",
                                )
                                raise BrokerServiceUnavailableError(
                                    error_message, original_error=call_error
                                ) from call_error

                            # Re-raise non-auth exceptions
                            raise

                        logger.info(f"? Cancelled order: {order_id}")
                        return True
                    except Exception as e:
                        logger.debug(f"Cancel order method failed: {e}")
                        continue

                except Exception as e:
                    logger.warning(f"[WARN]? Cancel via {method_name} failed: {e}")
                    continue

        return False

    def get_order(self, order_id: str) -> Order | None:
        """Get order details by ID"""
        orders = self.get_all_orders()
        for order in orders:
            if order.order_id == order_id:
                return order
        return None

    def get_all_orders(self) -> list[Order]:
        """
        Get all orders with automatic re-authentication on session expiry.

        Returns:
            List of Order objects, or empty list on error
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to broker")

        # Phase -1: Always ensure fresh client before API calls
        self._ensure_fresh_client()

        max_retries = 1  # Retry once after re-auth
        for attempt in range(max_retries + 1):
            try:
                # Try multiple method names
                for method_name in ["order_report", "get_order_report", "orderBook", "orders"]:
                    if hasattr(self._client, method_name):
                        method = getattr(self._client, method_name)

                        # Call with timeout protection (SDK might hang)
                        try:
                            response = call_with_timeout(
                                method,
                                timeout=DEFAULT_SDK_TIMEOUT,
                                timeout_error_message=f"get_all_orders() call to {method_name}() timed out",
                            )
                        except TimeoutError as timeout_error:
                            logger.warning(
                                f"SDK call timed out in get_all_orders: {timeout_error}. "
                                "This may indicate broker API is slow or network connectivity issue."
                            )
                            # Check if this is a service unavailable scenario (timeout after retries)
                            if attempt >= max_retries:
                                # After all retries, timeout could be network issue or service unavailable
                                # For read operations like get_all_orders, return empty list instead of raising error
                                # This prevents false "service unavailable" errors when it's actually a network issue
                                logger.warning(
                                    "Timeout after all retries in get_all_orders. "
                                    "This could be a network connectivity issue or broker service problem. "
                                    "Returning empty list to avoid false service unavailable errors."
                                )
                                return []
                            # If timeout occurs, try refreshing client from auth handler
                            # The client might be stale even if auth handler reports authenticated
                            if self.auth_handler and self.auth_handler.is_authenticated():
                                fresh_client = self.auth_handler.get_client()
                                if fresh_client:
                                    self._client = fresh_client
                                    logger.info("Refreshed client after timeout in get_all_orders")
                                    if attempt < max_retries:
                                        break  # Retry outer loop with fresh client
                            # Try next method or retry after re-auth
                            if attempt < max_retries:
                                break  # Retry outer loop
                            continue  # Try next method
                        except Exception as call_error:
                            # Check if it's a local network connectivity issue (not broker service issue)
                            if _is_network_connectivity_error(call_error):
                                logger.warning(
                                    f"Network connectivity issue detected in get_all_orders: {call_error}. "
                                    "This appears to be a local network/Docker connectivity problem, "
                                    "not a broker service issue. Returning empty list."
                                )
                                # Return empty list instead of raising error for network connectivity issues
                                # This prevents false "service unavailable" errors when broker is actually available
                                return []

                            # Check if it's a service unavailable error (maintenance, downtime, etc.)
                            if _is_service_unavailable_error(call_error):
                                logger.error(
                                    f"Broker service unavailable detected in get_all_orders: {call_error}"
                                )
                                raise BrokerServiceUnavailableError(
                                    "Broker service is temporarily unavailable. "
                                    "This may be due to scheduled maintenance or service issues. "
                                    "Please try again later."
                                ) from call_error

                            # Check if it's a connection error (might indicate missing session)
                            error_str = str(call_error).lower()
                            is_connection_error = (
                                "connection refused" in error_str
                                or "connection error" in error_str
                                or "newconnectionerror" in error_str
                                or "failed to establish" in error_str
                            )

                            # If connection error, try refreshing client from auth handler
                            # The client might be missing the session (empty sId in URL)
                            if (
                                is_connection_error
                                and self.auth_handler
                                and self.auth_handler.is_authenticated()
                            ):
                                fresh_client = self.auth_handler.get_client()
                                if fresh_client:
                                    self._client = fresh_client
                                    logger.warning(
                                        f"Connection error detected in get_all_orders: {call_error}. "
                                        "Refreshed client from auth handler to ensure session is used."
                                    )
                                    if attempt < max_retries:
                                        break  # Retry outer loop with fresh client

                            # Check if it's an auth error
                            if is_auth_exception(call_error):
                                logger.warning(
                                    f"Authentication error in get_all_orders: {call_error}. "
                                    "Checking re-authentication failure rate..."
                                )
                                # Check if re-auth should be blocked due to recent failures
                                if self.auth_handler and _check_reauth_failure_rate(
                                    self.auth_handler
                                ):
                                    logger.error(
                                        "Re-authentication blocked for get_all_orders due to recent failures. "
                                        "Please check authentication credentials or API status."
                                    )
                                    return []

                                # Attempt re-auth and retry
                                if (
                                    attempt < max_retries
                                    and self.auth_handler
                                    and hasattr(self.auth_handler, "force_relogin")
                                ):
                                    if _attempt_reauth_thread_safe(
                                        self.auth_handler, "get_all_orders"
                                    ):
                                        # Update client after re-auth - ensure it's authenticated
                                        new_client = self.auth_handler.get_client()
                                        if new_client and self.auth_handler.is_authenticated():
                                            self._client = new_client
                                            logger.info(
                                                "Re-authentication successful, client updated, retrying get_all_orders..."
                                            )
                                            break  # Retry the outer loop
                                        else:
                                            logger.error(
                                                "Re-authentication reported success but client is not authenticated"
                                            )
                                            _record_reauth_failure(self.auth_handler)
                                            return []
                                    else:
                                        logger.error("Re-authentication failed for get_all_orders")
                                        _record_reauth_failure(self.auth_handler)
                                        return []
                                else:
                                    logger.error(
                                        "Max retries reached or no auth handler for get_all_orders"
                                    )
                                    return []
                            # After all retries, if it's still a connection error, treat as service unavailable
                            if is_connection_error and attempt >= max_retries:
                                error_message = _get_service_unavailable_message(
                                    call_error,
                                    "Broker service is temporarily unavailable. "
                                    "Unable to establish connection to the broker API. "
                                    "This may be due to maintenance or network issues. Please try again later.",
                                )
                                raise BrokerServiceUnavailableError(
                                    error_message, original_error=call_error
                                ) from call_error

                            # Re-raise non-auth exceptions
                            raise

                        # Check response for auth errors
                        if isinstance(response, dict) and is_auth_error(response):
                            logger.warning(
                                f"Authentication error detected in get_all_orders response: {response}. "
                                "Checking re-authentication failure rate..."
                            )
                            # Check if re-auth should be blocked due to recent failures
                            if self.auth_handler and _check_reauth_failure_rate(self.auth_handler):
                                logger.error(
                                    "Re-authentication blocked for get_all_orders due to recent failures. "
                                    "Please check authentication credentials or API status."
                                )
                                return []

                            # Attempt re-auth and retry
                            if (
                                attempt < max_retries
                                and self.auth_handler
                                and hasattr(self.auth_handler, "force_relogin")
                            ):
                                if _attempt_reauth_thread_safe(self.auth_handler, "get_all_orders"):
                                    # Update client after re-auth - ensure it's authenticated
                                    new_client = self.auth_handler.get_client()
                                    if new_client and self.auth_handler.is_authenticated():
                                        self._client = new_client
                                        logger.info(
                                            "Re-authentication successful, client updated, retrying get_all_orders..."
                                        )
                                    else:
                                        logger.error(
                                            "Re-authentication reported success but client is not authenticated"
                                        )
                                        _record_reauth_failure(self.auth_handler)
                                        return []
                                    break  # Retry the outer loop
                                else:
                                    logger.error("Re-authentication failed for get_all_orders")
                                    _record_reauth_failure(self.auth_handler)
                                    return []
                            else:
                                logger.error(
                                    "Max retries reached or no auth handler for get_all_orders"
                                )
                                return []

                        # Handle different response formats
                        data = None
                        if isinstance(response, dict):
                            # Try "data" key first
                            if "data" in response:
                                data = response["data"]
                            # Try other common keys
                            elif "orders" in response:
                                data = response["orders"]
                            elif "orderList" in response:
                                data = response["orderList"]
                        elif isinstance(response, list):
                            data = response

                        if data is not None and isinstance(data, list):
                            return self._parse_orders_response(data)

                # If we get here, no method worked
                if attempt < max_retries:
                    continue
                return []

            except Exception as e:
                # Check if it's a connection error (might indicate missing session)
                error_str = str(e).lower()
                is_connection_error = (
                    "connection refused" in error_str
                    or "connection error" in error_str
                    or "newconnectionerror" in error_str
                    or "failed to establish" in error_str
                )

                # If connection error, try refreshing client from auth handler
                # The client might be missing the session (empty sId in URL)
                if (
                    is_connection_error
                    and self.auth_handler
                    and self.auth_handler.is_authenticated()
                ):
                    fresh_client = self.auth_handler.get_client()
                    if fresh_client:
                        self._client = fresh_client
                        logger.warning(
                            f"Connection error detected in get_all_orders: {e}. "
                            "Refreshed client from auth handler to ensure session is used."
                        )
                        if attempt < max_retries:
                            continue  # Retry with fresh client

                # Check if it's an auth error
                if is_auth_exception(e):
                    logger.warning(
                        f"Authentication error in get_all_orders: {e}. "
                        "Checking re-authentication failure rate..."
                    )
                    # Check if re-auth should be blocked due to recent failures
                    if self.auth_handler and _check_reauth_failure_rate(self.auth_handler):
                        logger.error(
                            "Re-authentication blocked for get_all_orders due to recent failures. "
                            "Please check authentication credentials or API status."
                        )
                        return []

                    # Attempt re-auth and retry
                    if (
                        attempt < max_retries
                        and self.auth_handler
                        and hasattr(self.auth_handler, "force_relogin")
                    ):
                        if _attempt_reauth_thread_safe(self.auth_handler, "get_all_orders"):
                            # Update client after re-auth - ensure it's authenticated
                            new_client = self.auth_handler.get_client()
                            if new_client and self.auth_handler.is_authenticated():
                                self._client = new_client
                                logger.info(
                                    "Re-authentication successful, client updated, retrying get_all_orders..."
                                )
                                continue  # Retry
                            else:
                                logger.error(
                                    "Re-authentication reported success but client is not authenticated"
                                )
                                _record_reauth_failure(self.auth_handler)
                                return []
                        else:
                            logger.error("Re-authentication failed for get_all_orders")
                            _record_reauth_failure(self.auth_handler)
                            return []
                    else:
                        logger.error("Max retries reached or no auth handler for get_all_orders")
                        return []

                # Non-auth errors - log and return empty
                logger.error(f"? Failed to get orders: {e}", exc_info=True)
                return []

        return []

    def get_pending_orders(self) -> list[Order]:
        """Get pending/open orders"""
        all_orders = self.get_all_orders()
        return [order for order in all_orders if order.is_active()]

    # Portfolio Management

    def get_holdings(self) -> list[Holding]:
        """
        Get portfolio holdings with automatic re-authentication on session expiry.

        Returns:
            List of Holding objects, or empty list on error
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to broker")

        # Phase -1: Always ensure fresh client before API calls
        self._ensure_fresh_client()

        max_retries = 1  # Retry once after re-auth
        for attempt in range(max_retries + 1):
            try:
                # Ensure client is available before making API calls
                if not self._client:
                    # Try to get fresh client from auth handler if available
                    if self.auth_handler and self.auth_handler.is_authenticated():
                        self._client = self.auth_handler.get_client()
                    if not self._client:
                        logger.error("No client available for get_holdings")
                        if attempt < max_retries:
                            continue
                        return []

                # Try multiple method names
                for method_name in ["holdings", "get_holdings", "portfolio_holdings"]:
                    if hasattr(self._client, method_name):
                        method = getattr(self._client, method_name)

                        # Call with timeout protection (SDK might hang)
                        try:
                            # Wrap SDK call with timeout to prevent hanging
                            response = call_with_timeout(
                                method,
                                timeout=DEFAULT_SDK_TIMEOUT,
                                timeout_error_message=f"get_holdings() call to {method_name}() timed out",
                            )
                        except TimeoutError as timeout_error:
                            logger.error(
                                f"SDK call timed out in get_holdings: {timeout_error}. "
                                "This may indicate broker API is slow or unreachable."
                            )
                            # Check if this is a service unavailable scenario (timeout after retries)
                            if attempt >= max_retries:
                                # After all retries, timeout likely means service is unavailable
                                raise BrokerServiceUnavailableError(
                                    "Broker service is temporarily unavailable. "
                                    "The API did not respond within the expected time. "
                                    "This may be due to maintenance or high load. Please try again later."
                                ) from timeout_error
                            # If timeout occurs, try refreshing client from auth handler
                            # The client might be stale even if auth handler reports authenticated
                            if self.auth_handler and self.auth_handler.is_authenticated():
                                fresh_client = self.auth_handler.get_client()
                                if fresh_client:
                                    self._client = fresh_client
                                    logger.info("Refreshed client after timeout in get_holdings")
                                    if attempt < max_retries:
                                        continue  # Retry with fresh client
                            # Try next method or retry after re-auth
                            if attempt < max_retries:
                                continue  # Retry outer loop
                            continue  # Try next method
                        except Exception as call_error:
                            # Check if it's a service unavailable error (maintenance, downtime, etc.)
                            if _is_service_unavailable_error(call_error):
                                logger.error(
                                    f"Broker service unavailable detected in get_holdings: {call_error}"
                                )
                                raise BrokerServiceUnavailableError(
                                    "Broker service is temporarily unavailable. "
                                    "This may be due to scheduled maintenance or service issues. "
                                    "Please try again later."
                                ) from call_error

                            # Check if it's a connection error (might indicate missing session)
                            error_str = str(call_error).lower()
                            is_connection_error = (
                                "connection refused" in error_str
                                or "connection error" in error_str
                                or "newconnectionerror" in error_str
                                or "failed to establish" in error_str
                            )

                            # If connection error, try refreshing client from auth handler
                            # The client might be missing the session (empty sId in URL)
                            if (
                                is_connection_error
                                and self.auth_handler
                                and self.auth_handler.is_authenticated()
                            ):
                                fresh_client = self.auth_handler.get_client()
                                if fresh_client:
                                    self._client = fresh_client
                                    logger.warning(
                                        f"Connection error detected in get_holdings: {call_error}. "
                                        "Refreshed client from auth handler to ensure session is used."
                                    )
                                    if attempt < max_retries:
                                        continue  # Retry with fresh client

                            # Check if it's an auth error
                            if is_auth_exception(call_error):
                                logger.warning(
                                    f"Authentication error in get_holdings: {call_error}. "
                                    "Checking re-authentication failure rate..."
                                )
                                # Check if re-auth should be blocked due to recent failures
                                if self.auth_handler and _check_reauth_failure_rate(
                                    self.auth_handler
                                ):
                                    logger.error(
                                        "Re-authentication blocked for get_holdings due to recent failures. "
                                        "Please check authentication credentials or API status."
                                    )
                                    return []

                                # Attempt re-auth and retry
                                if (
                                    attempt < max_retries
                                    and self.auth_handler
                                    and hasattr(self.auth_handler, "force_relogin")
                                ):
                                    if _attempt_reauth_thread_safe(
                                        self.auth_handler, "get_holdings"
                                    ):
                                        # Update client after re-auth - ensure it's authenticated
                                        new_client = self.auth_handler.get_client()
                                        if new_client and self.auth_handler.is_authenticated():
                                            self._client = new_client
                                            logger.info(
                                                "Re-authentication successful, client updated, retrying get_holdings..."
                                            )
                                            break  # Retry the outer loop
                                        else:
                                            logger.error(
                                                "Re-authentication reported success but client is not authenticated"
                                            )
                                            _record_reauth_failure(self.auth_handler)
                                            return []
                                    else:
                                        logger.error("Re-authentication failed for get_holdings")
                                        _record_reauth_failure(self.auth_handler)
                                        return []
                                else:
                                    logger.error(
                                        "Max retries reached or no auth handler for get_holdings"
                                    )
                                    return []
                            # After all retries, if it's still a connection error, treat as service unavailable
                            if is_connection_error and attempt >= max_retries:
                                error_message = _get_service_unavailable_message(
                                    call_error,
                                    "Broker service is temporarily unavailable. "
                                    "Unable to establish connection to the broker API. "
                                    "This may be due to maintenance or network issues. Please try again later.",
                                )
                                raise BrokerServiceUnavailableError(
                                    error_message, original_error=call_error
                                ) from call_error

                            # Re-raise non-auth exceptions
                            raise

                        # Check response for auth errors
                        if isinstance(response, dict):
                            # Check for auth error in response
                            if is_auth_error(response):
                                logger.warning(
                                    "Authentication error detected in get_holdings response. "
                                    "Checking re-authentication failure rate..."
                                )
                                # Check if re-auth should be blocked due to recent failures
                                if self.auth_handler and _check_reauth_failure_rate(
                                    self.auth_handler
                                ):
                                    logger.error(
                                        "Re-authentication blocked for get_holdings due to recent failures. "
                                        "Please check authentication credentials or API status."
                                    )
                                    return []

                                # Attempt re-auth and retry
                                if (
                                    attempt < max_retries
                                    and self.auth_handler
                                    and hasattr(self.auth_handler, "force_relogin")
                                ):
                                    if _attempt_reauth_thread_safe(
                                        self.auth_handler, "get_holdings"
                                    ):
                                        # Update client after re-auth - ensure it's authenticated
                                        new_client = self.auth_handler.get_client()
                                        if new_client and self.auth_handler.is_authenticated():
                                            self._client = new_client
                                            logger.info(
                                                "Re-authentication successful, client updated, retrying get_holdings..."
                                            )
                                            break  # Retry the outer loop
                                        else:
                                            logger.error(
                                                "Re-authentication reported success but client is not authenticated"
                                            )
                                            _record_reauth_failure(self.auth_handler)
                                            return []
                                    else:
                                        logger.error("Re-authentication failed for get_holdings")
                                        _record_reauth_failure(self.auth_handler)
                                        return []
                                else:
                                    logger.error(
                                        "Max retries reached or no auth handler for get_holdings"
                                    )
                                    return []

                            # Success - parse and return
                            if "data" in response:
                                return self._parse_holdings_response(response["data"])

                # If we get here, no method worked
                if attempt < max_retries:
                    continue
                return []

            except Exception as e:
                # Check if it's a connection error (might indicate missing session)
                error_str = str(e).lower()
                is_connection_error = (
                    "connection refused" in error_str
                    or "connection error" in error_str
                    or "newconnectionerror" in error_str
                    or "failed to establish" in error_str
                )

                # If connection error, try refreshing client from auth handler
                # The client might be missing the session (empty sId in URL)
                if (
                    is_connection_error
                    and self.auth_handler
                    and self.auth_handler.is_authenticated()
                ):
                    fresh_client = self.auth_handler.get_client()
                    if fresh_client:
                        self._client = fresh_client
                        logger.warning(
                            f"Connection error detected in get_holdings: {e}. "
                            "Refreshed client from auth handler to ensure session is used."
                        )
                        if attempt < max_retries:
                            continue  # Retry with fresh client

                # Check if it's an auth error
                if is_auth_exception(e):
                    logger.warning(
                        f"Authentication error in get_holdings: {e}. "
                        "Checking re-authentication failure rate..."
                    )
                    # Check if re-auth should be blocked due to recent failures
                    if self.auth_handler and _check_reauth_failure_rate(self.auth_handler):
                        logger.error(
                            "Re-authentication blocked for get_holdings due to recent failures. "
                            "Please check authentication credentials or API status."
                        )
                        return []

                    # Attempt re-auth and retry
                    if (
                        attempt < max_retries
                        and self.auth_handler
                        and hasattr(self.auth_handler, "force_relogin")
                    ):
                        if _attempt_reauth_thread_safe(self.auth_handler, "get_holdings"):
                            # Update client after re-auth - ensure it's authenticated
                            new_client = self.auth_handler.get_client()
                            if new_client and self.auth_handler.is_authenticated():
                                self._client = new_client
                                logger.info(
                                    "Re-authentication successful, client updated, retrying get_holdings..."
                                )
                                continue  # Retry
                            else:
                                logger.error(
                                    "Re-authentication reported success but client is not authenticated"
                                )
                                _record_reauth_failure(self.auth_handler)
                                return []
                        else:
                            logger.error("Re-authentication failed for get_holdings")
                            _record_reauth_failure(self.auth_handler)
                            return []
                    else:
                        logger.error("Max retries reached or no auth handler for get_holdings")
                        return []

                # Non-auth errors - log and return empty
                logger.error(f"? Failed to get holdings: {e}")
                return []

        return []

    def get_holding(self, symbol: str) -> Holding | None:
        """Get holding for specific symbol"""
        holdings = self.get_holdings()
        for holding in holdings:
            if holding.symbol.upper() == symbol.upper():
                return holding
        return None

    # Account Management

    def get_account_limits(self) -> dict[str, Any]:
        """
        Get account limits and margins with automatic re-authentication on session expiry.

        Handles Kotak Neo API response format:
        {
            "Net": "19.41",  # Available cash/net balance
            "MarginUsed": "18.78",
            "CollateralValue": "38.19",
            "Collateral": "0",
            ...
        }

        Returns:
            Dictionary with account limits, or empty dict on error
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to broker")

        # Refresh client from auth handler before API calls to ensure latest session is used
        # The session (sId) is embedded in the SDK client when created during login
        # Since session is valid for ~1 hour, we reuse it but always get fresh client to ensure session is present
        # After re-auth, auth.client becomes a NEW object, so we need to refresh to get the new session
        # Strategy: Always refresh if client changed (re-auth) or if no client exists
        # In production: auth.get_client() returns auth.client (same object until re-auth, then new object)
        # In tests: Tests should configure auth_handler.get_client() to return the same mock_client
        if self.auth_handler and self.auth_handler.is_authenticated():
            fresh_client = self.auth_handler.get_client()
            if fresh_client:
                # Always refresh if: (1) no client, OR (2) client changed (re-auth happened)
                # Same client object = no-op refresh (ensures we have latest session)
                if self._client is None or fresh_client is not self._client:
                    self._client = fresh_client
                    logger.debug(
                        "Refreshed client from auth handler for get_account_limits to ensure session is used"
                    )

        max_retries = 1  # Retry once after re-auth
        for attempt in range(max_retries + 1):
            try:
                # Call limits API with timeout protection
                response = call_with_timeout(
                    lambda: self._client.limits(segment="ALL", exchange="ALL", product="ALL"),
                    timeout=DEFAULT_SDK_TIMEOUT,
                    timeout_error_message="get_account_limits() call to limits() timed out",
                )

                # Check response for auth errors
                if isinstance(response, dict):
                    # Check for auth error in response
                    if is_auth_error(response):
                        logger.warning(
                            "Authentication error detected in get_account_limits response. "
                            "Checking re-authentication failure rate..."
                        )
                        # Check if re-auth should be blocked due to recent failures
                        if self.auth_handler and _check_reauth_failure_rate(self.auth_handler):
                            logger.error(
                                "Re-authentication blocked for get_account_limits due to recent failures. "
                                "Please check authentication credentials or API status."
                            )
                            return {}

                        # Attempt re-auth and retry
                        if (
                            attempt < max_retries
                            and self.auth_handler
                            and hasattr(self.auth_handler, "force_relogin")
                        ):
                            if _attempt_reauth_thread_safe(self.auth_handler, "get_account_limits"):
                                # Update client after re-auth - ensure it's authenticated
                                new_client = self.auth_handler.get_client()
                                if new_client and self.auth_handler.is_authenticated():
                                    self._client = new_client
                                    logger.info(
                                        "Re-authentication successful, client updated, retrying get_account_limits..."
                                    )
                                    continue  # Retry
                                else:
                                    logger.error(
                                        "Re-authentication reported success but client is not authenticated"
                                    )
                                    _record_reauth_failure(self.auth_handler)
                                    return {}
                            else:
                                logger.error("Re-authentication failed for get_account_limits")
                                _record_reauth_failure(self.auth_handler)
                                return {}
                        else:
                            logger.error(
                                "Max retries reached or no auth handler for get_account_limits"
                            )
                            return {}

                    # Success - parse response
                    # Response is a flat dict, not wrapped in {"data": {...}}
                    # Extract available cash from "Net" field (net balance)
                    # Fallback to other cash-like fields if Net is not available
                    net_balance = response.get("Net") or response.get("net") or "0"
                    margin_used = response.get("MarginUsed") or response.get("marginUsed") or "0"
                    collateral_value = (
                        response.get("CollateralValue")
                        or response.get("collateralValue")
                        or response.get("Collateral")
                        or response.get("collateral")
                        or "0"
                    )

                    # Try to parse as float, default to 0 if parsing fails
                    try:
                        available_cash = float(str(net_balance))
                    except (ValueError, TypeError):
                        available_cash = 0.0

                    try:
                        margin_used_val = float(str(margin_used))
                    except (ValueError, TypeError):
                        margin_used_val = 0.0

                    try:
                        collateral_val = float(str(collateral_value))
                    except (ValueError, TypeError):
                        collateral_val = 0.0

                    return {
                        "available_cash": Money.from_float(available_cash),
                        "margin_used": Money.from_float(margin_used_val),
                        "margin_available": Money.from_float(
                            max(0.0, available_cash - margin_used_val)
                        ),  # Calculate available margin
                        "collateral": Money.from_float(collateral_val),
                        "net": Money.from_float(available_cash),  # Alias for available_cash
                    }

                # Non-dict response
                return {}

            except TimeoutError as timeout_error:
                logger.error(
                    f"SDK call timed out in get_account_limits: {timeout_error}. "
                    "This may indicate broker API is slow or unreachable."
                )
                # If timeout occurs, try refreshing client from auth handler
                # The client might be stale even if auth handler reports authenticated
                if self.auth_handler and self.auth_handler.is_authenticated():
                    fresh_client = self.auth_handler.get_client()
                    if fresh_client:
                        self._client = fresh_client
                        logger.info("Refreshed client after timeout in get_account_limits")
                        if attempt < max_retries:
                            continue  # Retry with fresh client
                # Try next retry
                if attempt < max_retries:
                    continue
                # After all retries, return empty dict for backward compatibility
                # (Read operations return empty collections on timeout, unlike write operations)
                logger.warning(
                    "get_account_limits timed out after all retries. Returning empty dict."
                )
                return {}
            except Exception as e:
                # Check if it's a service unavailable error (maintenance, downtime, etc.)
                if _is_service_unavailable_error(e):
                    logger.error(f"Broker service unavailable detected in get_account_limits: {e}")
                    error_message = _get_service_unavailable_message(
                        e,
                        "Broker service is temporarily unavailable. "
                        "This may be due to scheduled maintenance or service issues. "
                        "Please try again later.",
                    )
                    raise BrokerServiceUnavailableError(error_message, original_error=e) from e

                # Check if it's a connection error (might indicate missing session)
                error_str = str(e).lower()
                is_connection_error = (
                    "connection refused" in error_str
                    or "connection error" in error_str
                    or "newconnectionerror" in error_str
                    or "failed to establish" in error_str
                )

                # If connection error, try refreshing client from auth handler
                # The client might be missing the session (empty sId in URL)
                if (
                    is_connection_error
                    and self.auth_handler
                    and self.auth_handler.is_authenticated()
                ):
                    fresh_client = self.auth_handler.get_client()
                    if fresh_client:
                        self._client = fresh_client
                        logger.warning(
                            f"Connection error detected in get_account_limits: {e}. "
                            "Refreshed client from auth handler to ensure session is used."
                        )
                        if attempt < max_retries:
                            continue  # Retry with fresh client

                # Check if it's an auth error
                if is_auth_exception(e):
                    logger.warning(
                        f"Authentication error in get_account_limits: {e}. "
                        "Checking re-authentication failure rate..."
                    )
                    # Check if re-auth should be blocked due to recent failures
                    if self.auth_handler and _check_reauth_failure_rate(self.auth_handler):
                        logger.error(
                            "Re-authentication blocked for get_account_limits due to recent failures. "
                            "Please check authentication credentials or API status."
                        )
                        return {}

                    # Attempt re-auth and retry
                    if (
                        attempt < max_retries
                        and self.auth_handler
                        and hasattr(self.auth_handler, "force_relogin")
                    ):
                        if _attempt_reauth_thread_safe(self.auth_handler, "get_account_limits"):
                            # Update client after re-auth
                            self._client = self.auth_handler.get_client()
                            logger.info(
                                "Re-authentication successful, retrying get_account_limits..."
                            )
                            continue  # Retry
                        else:
                            logger.error("Re-authentication failed for get_account_limits")
                            _record_reauth_failure(self.auth_handler)
                            return {}
                    else:
                        logger.error(
                            "Max retries reached or no auth handler for get_account_limits"
                        )
                        return {}

                # Non-auth errors - log and return empty
                logger.error(f"? Failed to get account limits: {e}")
                return {}

        return {}

    def get_available_balance(self) -> Money:
        """Get available cash balance"""
        limits = self.get_account_limits()
        return limits.get("available_cash", Money.zero())

    # Utility Methods

    def search_orders_by_symbol(self, symbol: str) -> list[Order]:
        """Search orders by symbol"""
        all_orders = self.get_all_orders()
        return [order for order in all_orders if order.symbol.upper() == symbol.upper()]

    def cancel_pending_buys_for_symbol(self, symbol: str) -> int:
        """Cancel all pending BUY orders for a symbol"""
        pending = self.get_pending_orders()
        cancelled = 0

        for order in pending:
            if order.symbol.upper() == symbol.upper() and order.is_buy_order():
                if self.cancel_order(order.order_id):
                    cancelled += 1

        return cancelled

    # Helper Methods (Private)

    def _build_order_payload(self, order: Order) -> dict:
        """Build API payload from domain order"""
        exchange_segment_map = {
            Exchange.NSE.value: "nse_cm",
            Exchange.BSE.value: "bse_cm",
            "NFO": "nse_fo",
            "BFO": "bse_fo",
            "CDS": "cde_fo",
            "MCX": "mcx_fo",
        }
        exchange_segment = exchange_segment_map.get(
            order.exchange.value, order.exchange.value.lower()
        )
        amo_value = "YES" if order.variety == OrderVariety.AMO else "NO"
        price_str = str(order.price.amount) if order.price else "0"
        return {
            "exchange_segment": exchange_segment,
            "product": order.product_type.value,
            "price": price_str,
            "order_type": self._map_order_type(order.order_type),
            "quantity": str(order.quantity),
            "validity": order.validity,
            "trading_symbol": order.symbol,
            "transaction_type": "B" if order.transaction_type == TransactionType.BUY else "S",
            "amo": amo_value,
            "disclosed_quantity": "0",
        }

    def _map_order_type(self, order_type: OrderType) -> str:
        """Map domain OrderType to SDK order type"""
        mapping = {
            OrderType.MARKET: "MKT",
            OrderType.LIMIT: "L",
            OrderType.STOP_LOSS: "SL",
            OrderType.STOP_LOSS_MARKET: "SL-M",
        }
        return mapping.get(order_type, "MKT")

    def _adapt_payload_to_method(self, method, payload: dict) -> dict:
        """Adapt payload to method signature"""
        try:
            params = set(inspect.signature(method).parameters.keys())
        except (ValueError, TypeError):
            return payload

        alt_keys = {
            "exchange_segment": ["exchange"],
            "product": ["product_type"],
            "price": ["priceValue"],
            "order_type": ["orderType", "type"],
            "quantity": ["qty"],
            "validity": ["order_validity"],
            "trading_symbol": ["tradingSymbol", "symbol"],
            "transaction_type": ["transactionType", "txnType"],
            "amo": ["variety"],
            "disclosed_quantity": ["disclosedQuantity", "discQty"],
        }

        adapted = {}
        for key, value in payload.items():
            if key in params:
                adapted[key] = value
            elif key in alt_keys:
                for alt in alt_keys[key]:
                    if alt in params:
                        adapted[alt] = value
                        break

        return adapted

    def _is_error_response(self, response) -> bool:
        """Check if response contains error"""
        if isinstance(response, dict):
            keys_lower = {str(k).lower() for k in response.keys()}
            return any(k in keys_lower for k in ("error", "errors"))
        resp_text = str(response).lower()
        return "error" in resp_text or "invalid" in resp_text

    def _extract_order_id(self, response) -> str | None:
        """Extract order ID from response"""
        if isinstance(response, dict):
            for key in ["neoOrdNo", "orderId", "order_id", "ordId", "id"]:
                if key in response:
                    return str(response[key])
                if "data" in response and isinstance(response["data"], dict):
                    if key in response["data"]:
                        return str(response["data"][key])
        return None

    def _parse_orders_response(self, data: list) -> list[Order]:  # noqa: PLR0912, PLR0915
        """Parse orders from API response"""
        if not isinstance(data, list):
            return []

        orders = []
        for item in data:
            try:
                # Try multiple field name variations for symbol
                # Priority: trdSym (actual Kotak API field) > sym (short symbol)
                # > tradingSymbol > others
                symbol = (
                    item.get("trdSym")  # Primary: Kotak API uses "trdSym" (e.g., "IDEA-EQ")
                    or item.get("sym")  # Fallback: Short symbol (e.g., "IDEA")
                    or item.get("tradingSymbol")  # Legacy/compatibility
                    or item.get("symbol")  # Generic fallback
                    or item.get("instrumentName")  # Alternative field
                    or item.get("securitySymbol")  # Alternative field
                    or ""
                )
                symbol = str(symbol).strip()

                # Only skip if symbol is still empty after trying all variations
                # This could be invalid/corrupted data from broker API
                if not symbol:
                    order_id = (
                        item.get("nOrdNo")  # Primary: Kotak API uses "nOrdNo"
                        or item.get("neoOrdNo")  # Legacy/compatibility
                        or item.get("orderId")  # Generic fallback
                        or "N/A"
                    )
                    status = item.get("stat") or item.get("ordSt") or item.get("orderStatus", "N/A")
                    logger.warning(
                        f"Skipping order with empty symbol after trying all field variations "
                        f"(order_id: {order_id}, status: {status})"
                    )
                    continue

                # Extract order ID - prioritize nOrdNo (actual Kotak API field)
                order_id = (
                    item.get("nOrdNo")  # Primary: Kotak API uses "nOrdNo"
                    or item.get("neoOrdNo")  # Legacy/compatibility
                    or item.get("orderId")  # Generic fallback
                    or ""
                )

                # Extract order status - try multiple field names
                order_status = (
                    item.get("stat")  # Primary: Kotak API uses "stat"
                    or item.get("ordSt")  # Alternative
                    or item.get("orderStatus")  # Legacy/compatibility
                    or "PENDING"
                )

                # Extract transaction type - try multiple field names
                transaction_type = (
                    item.get("trnsTp")  # Primary: Kotak API uses "trnsTp" (B/S)
                    or item.get("transactionType")  # Legacy/compatibility
                    or "B"
                )

                # Extract order type - try multiple field names
                order_type = (
                    item.get("prcTp")  # Primary: Kotak API uses "prcTp" (L/M)
                    or item.get("orderType")  # Legacy/compatibility
                    or "MKT"
                )

                # Parse datetime fields - Kotak API uses "22-Jan-2025 14:28:01" format
                placed_at = None
                created_at = None
                for dt_field in ["ordDtTm", "ordEntTm", "ordDt", "ordEnt"]:
                    dt_str = item.get(dt_field)
                    if dt_str:
                        try:
                            # Try Kotak format: "22-Jan-2025 14:28:01"
                            parsed_dt = datetime.strptime(str(dt_str), "%d-%b-%Y %H:%M:%S")
                            placed_at = parsed_dt
                            created_at = parsed_dt
                            break
                        except (ValueError, TypeError):
                            try:
                                # Try ISO format as fallback
                                parsed_dt = datetime.fromisoformat(
                                    str(dt_str).replace("Z", "+00:00")
                                )
                                placed_at = parsed_dt
                                created_at = parsed_dt
                                break
                            except (ValueError, TypeError):
                                continue

                # Parse execution price from avgPrc
                executed_price = None
                avg_prc_str = item.get("avgPrc") or item.get("avgPrice") or item.get("averagePrice")
                if avg_prc_str:
                    try:
                        avg_prc = float(str(avg_prc_str))
                        if avg_prc > 0:
                            executed_price = Money.from_float(avg_prc)
                    except (ValueError, TypeError):
                        pass

                # Parse executed quantity from fldQty (filled quantity)
                executed_quantity = 0
                fld_qty = item.get("fldQty") or item.get("filledQty") or item.get("executedQty")
                if fld_qty:
                    try:
                        executed_quantity = int(float(str(fld_qty)))
                    except (ValueError, TypeError):
                        pass

                order = Order(
                    symbol=symbol,
                    quantity=int(item.get("qty") or item.get("quantity", 0)),
                    order_type=self._parse_order_type(order_type),
                    transaction_type=self._parse_transaction_type(transaction_type),
                    price=(
                        Money.from_float(float(item.get("prc") or item.get("price", 0)))
                        if (item.get("prc") or item.get("price"))
                        else None
                    ),
                    order_id=str(order_id),
                    status=self._parse_order_status(order_status),
                    placed_at=placed_at,
                    executed_price=executed_price,
                    executed_quantity=executed_quantity,
                )
                # Set created_at explicitly if we parsed it
                if created_at:
                    order.created_at = created_at
                orders.append(order)
            except Exception as e:
                logger.warning(f"Failed to parse order: {e}")
                continue

        return orders
        return orders

    def _parse_holdings_response(self, data: list) -> list[Holding]:
        """
        Parse holdings from API response

        Handles Kotak Neo API response format:
        {
            "data": [
                {
                    "displaySymbol": "IDEA",
                    "symbol": "IDEA",
                    "averagePrice": 9.5699,
                    "quantity": 35,
                    "closingPrice": 9.36,
                    "mktValue": 327.6,
                    "holdingCost": 334.9475,
                    ...
                }
            ]
        }
        """
        holdings = []
        for item in data:
            try:
                # Symbol: prioritize displaySymbol (Kotak API format) then symbol
                symbol = self._extract_field(
                    item,
                    [
                        "displaySymbol",  # Primary: Kotak API uses "displaySymbol"
                        "symbol",  # Fallback: Generic symbol field
                        "tradingSymbol",  # Legacy/compatibility
                        "instrumentName",  # Alternative field
                        "securitySymbol",  # Alternative field
                    ],
                )
                if not symbol:
                    logger.warning(f"Skipping holding with empty symbol: {item}")
                    continue

                # Quantity: prioritize quantity (Kotak API format)
                quantity = int(
                    self._extract_field(
                        item,
                        [
                            "quantity",  # Primary: Kotak API uses "quantity"
                            "qty",  # Fallback: Short form
                            "netQuantity",  # Alternative
                            "holdingsQuantity",  # Alternative
                        ],
                        0,
                    )
                )

                # Average price: prioritize averagePrice (Kotak API format)
                avg_price = float(
                    self._extract_field(
                        item,
                        [
                            "averagePrice",  # Primary: Kotak API uses "averagePrice"
                            "avgPrice",  # Fallback: Short form
                            "buyAvg",  # Alternative
                            "buyAvgPrice",  # Alternative
                        ],
                        0,
                    )
                )

                # Current price: prioritize closingPrice (Kotak API format) then ltp
                current_price = float(
                    self._extract_field(
                        item,
                        [
                            "closingPrice",  # Primary: Kotak API uses "closingPrice"
                            "ltp",  # Fallback: Last traded price
                            "lastPrice",  # Alternative
                            "lastTradedPrice",  # Alternative
                            "ltpPrice",  # Alternative
                        ],
                        0,
                    )
                )

                # If current_price is 0, try to calculate from mktValue / quantity
                if current_price == 0 and quantity > 0:
                    mkt_value = float(
                        self._extract_field(
                            item,
                            ["mktValue", "marketValue", "market_value"],
                            0,
                        )
                    )
                    if mkt_value > 0:
                        current_price = mkt_value / quantity
                        logger.debug(
                            f"{symbol}: Calculated current_price from mktValue: {current_price:.2f}"
                        )

                holding = Holding(
                    symbol=str(symbol).strip(),
                    quantity=quantity,
                    average_price=Money.from_float(avg_price),
                    current_price=Money.from_float(current_price),
                    last_updated=datetime.now(),
                )
                holdings.append(holding)
            except Exception as e:
                logger.warning(f"[WARN]? Failed to parse holding: {e}, item: {item}")
                continue
        return holdings

    def _extract_field(self, data: dict, keys: list, default=None):
        """Extract field from data trying multiple keys"""
        for key in keys:
            if key in data:
                return data[key]
        return default

    def _parse_order_type(self, value: str) -> OrderType:
        """Parse order type from string"""
        return OrderType.from_string(value)

    def _parse_transaction_type(self, value: str) -> TransactionType:
        """Parse transaction type from string"""
        return TransactionType.from_string(value)

    def _parse_order_status(self, value: str) -> OrderStatus:
        """Parse order status from string"""
        return OrderStatus.from_string(value)
