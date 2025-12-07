"""
Tests for KotakNeoBrokerAdapter re-authentication and timeout fixes

Tests cover:
1. Re-authentication on auth errors
2. Timeout handling for SDK calls
3. Failure rate limiting
4. Retry logic after re-auth
5. Infinite loop prevention
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from modules.kotak_neo_auto_trader.domain import (
    Exchange,
    Money,
    Order,
    OrderType,
    TransactionType,
)
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter import (
    KotakNeoBrokerAdapter,
)


@pytest.fixture
def mock_client():
    """Create a mock Kotak Neo client"""
    return MagicMock()


@pytest.fixture
def mock_auth_handler(mock_client):
    """Create a mock auth handler with force_relogin"""
    auth = MagicMock()
    auth.force_relogin = Mock(return_value=True)
    # Return the same mock_client by default to support client refresh logic
    # Tests can override this if they need a different client
    auth.get_client = Mock(return_value=mock_client)
    auth.is_authenticated = Mock(return_value=True)
    return auth


@pytest.fixture
def adapter(mock_client, mock_auth_handler):
    """Create a KotakNeoBrokerAdapter instance"""
    adapter = KotakNeoBrokerAdapter(auth_handler=mock_auth_handler)
    adapter._client = mock_client
    adapter._connected = True
    return adapter


class TestReAuthentication:
    """Test re-authentication on auth errors"""

    def test_get_holdings_reauth_on_auth_error_in_response(
        self, adapter, mock_client, mock_auth_handler
    ):
        """Test get_holdings() triggers re-auth on auth error in response"""
        # First call returns auth error, second call succeeds after re-auth
        mock_client.holdings.side_effect = [
            {"code": "900901", "message": "JWT token expired"},  # Auth error
        ]

        # Create a new mock client for after re-auth
        new_mock_client = MagicMock()
        new_mock_client.holdings.return_value = {
            "data": [
                {
                    "displaySymbol": "IDEA",
                    "averagePrice": 9.57,
                    "quantity": 35,
                    "closingPrice": 9.36,
                }
            ]
        }
        # get_client() should return mock_client first, then new_mock_client after re-auth
        # This simulates the real behavior where client refresh happens before each call
        mock_auth_handler.get_client.side_effect = [mock_client, new_mock_client]

        # Mock re-auth functions
        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_error"
            ) as mock_is_auth_error,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._check_reauth_failure_rate"
            ) as mock_check_rate,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._record_reauth_failure"
            ) as mock_record,
        ):
            # Setup mocks
            mock_is_auth_error.side_effect = lambda r: (
                r.get("code") == "900901" if isinstance(r, dict) else False
            )
            mock_check_rate.return_value = False  # Not blocked
            mock_reauth.return_value = True  # Re-auth succeeds

            holdings = adapter.get_holdings()

            # Should retry after re-auth and succeed
            assert len(holdings) == 1
            assert holdings[0].symbol == "IDEA"
            # Verify re-auth was attempted
            mock_reauth.assert_called_once()
            # Verify client was updated
            mock_auth_handler.get_client.assert_called()
            # Should not record failure (re-auth succeeded)
            mock_record.assert_not_called()

    def test_get_holdings_reauth_on_auth_exception(self, adapter, mock_client, mock_auth_handler):
        """Test get_holdings() triggers re-auth on auth exception"""
        # First call raises auth exception
        mock_client.holdings.side_effect = Exception("JWT token expired")

        # Create a new mock client for after re-auth
        new_mock_client = MagicMock()
        new_mock_client.holdings.return_value = {
            "data": [
                {
                    "displaySymbol": "TCS",
                    "averagePrice": 3500.0,
                    "quantity": 10,
                    "closingPrice": 3600.0,
                }
            ]
        }
        # get_client() should return mock_client first, then new_mock_client after re-auth
        # This simulates: refresh at start -> mock_client, refresh after re-auth -> new_mock_client
        mock_auth_handler.get_client.side_effect = [mock_client, new_mock_client]

        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_exception"
            ) as mock_is_auth_exception,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._check_reauth_failure_rate"
            ) as mock_check_rate,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._record_reauth_failure"
            ) as mock_record,
        ):
            # Setup mocks
            mock_is_auth_exception.side_effect = lambda e: (
                "JWT" in str(e) if isinstance(e, Exception) else False
            )
            mock_check_rate.return_value = False  # Not blocked
            mock_reauth.return_value = True  # Re-auth succeeds

            holdings = adapter.get_holdings()

            # Should retry after re-auth and succeed
            assert len(holdings) == 1
            assert holdings[0].symbol == "TCS"
            # Verify re-auth was attempted
            mock_reauth.assert_called_once()
            # Should not record failure
            mock_record.assert_not_called()

    def test_get_holdings_reauth_fails_returns_empty(self, adapter, mock_client, mock_auth_handler):
        """Test get_holdings() returns empty list when re-auth fails"""
        mock_client.holdings.return_value = {"code": "900901", "message": "JWT token expired"}

        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_error"
            ) as mock_is_auth_error,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._check_reauth_failure_rate"
            ) as mock_check_rate,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._record_reauth_failure"
            ) as mock_record,
        ):
            # Setup mocks
            mock_is_auth_error.return_value = True
            mock_check_rate.return_value = False  # Not blocked
            mock_reauth.return_value = False  # Re-auth fails

            holdings = adapter.get_holdings()

            # Should return empty list
            assert holdings == []
            # Verify re-auth was attempted
            mock_reauth.assert_called_once()
            # Should record failure
            mock_record.assert_called_once()

    def test_get_account_limits_reauth_on_auth_error(self, adapter, mock_client, mock_auth_handler):
        """Test get_account_limits() triggers re-auth on auth error"""
        # First call returns auth error
        mock_client.limits.return_value = {"code": "900901", "message": "JWT token expired"}

        # Create a new mock client for after re-auth
        new_mock_client = MagicMock()
        new_mock_client.limits.return_value = {
            "Net": "100.50",
            "MarginUsed": "50.25",
            "CollateralValue": "200.75",
            "stCode": 200,
        }
        # get_client() should return mock_client first, then new_mock_client after re-auth
        # This simulates: refresh at start -> mock_client, refresh after re-auth -> new_mock_client
        mock_auth_handler.get_client.side_effect = [mock_client, new_mock_client]

        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_error"
            ) as mock_is_auth_error,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._check_reauth_failure_rate"
            ) as mock_check_rate,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._record_reauth_failure"
            ) as mock_record,
        ):
            # Setup mocks
            mock_is_auth_error.side_effect = lambda r: (
                r.get("code") == "900901" if isinstance(r, dict) else False
            )
            mock_check_rate.return_value = False  # Not blocked
            mock_reauth.return_value = True  # Re-auth succeeds

            limits = adapter.get_account_limits()

            # Should retry after re-auth and succeed
            assert "available_cash" in limits
            assert float(limits["available_cash"].amount) == pytest.approx(100.50, abs=0.01)
            # Verify re-auth was attempted
            mock_reauth.assert_called_once()
            # Should not record failure
            mock_record.assert_not_called()


class TestFailureRateLimiting:
    """Test failure rate limiting prevents infinite loops"""

    def test_get_holdings_blocked_by_failure_rate(self, adapter, mock_client, mock_auth_handler):
        """Test get_holdings() is blocked when failure rate is too high"""
        mock_client.holdings.return_value = {"code": "900901", "message": "JWT token expired"}

        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_error"
            ) as mock_is_auth_error,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._check_reauth_failure_rate"
            ) as mock_check_rate,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
        ):
            # Setup mocks
            mock_is_auth_error.return_value = True
            mock_check_rate.return_value = True  # Blocked due to too many failures

            holdings = adapter.get_holdings()

            # Should return empty list immediately (blocked)
            assert holdings == []
            # Should NOT attempt re-auth (blocked)
            mock_reauth.assert_not_called()

    def test_get_account_limits_blocked_by_failure_rate(
        self, adapter, mock_client, mock_auth_handler
    ):
        """Test get_account_limits() is blocked when failure rate is too high"""
        mock_client.limits.return_value = {"code": "900901", "message": "JWT token expired"}

        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_error"
            ) as mock_is_auth_error,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._check_reauth_failure_rate"
            ) as mock_check_rate,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
        ):
            # Setup mocks
            mock_is_auth_error.return_value = True
            mock_check_rate.return_value = True  # Blocked

            limits = adapter.get_account_limits()

            # Should return empty dict immediately (blocked)
            assert limits == {}
            # Should NOT attempt re-auth (blocked)
            mock_reauth.assert_not_called()


class TestTimeoutHandling:
    """Test timeout handling for SDK calls"""

    def test_get_holdings_timeout_returns_empty(self, adapter, mock_client):
        """Test get_holdings() handles timeout gracefully"""
        # Mock timeout utility to raise TimeoutError
        with patch(
            "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.call_with_timeout"
        ) as mock_timeout:
            mock_timeout.side_effect = TimeoutError("SDK call timed out after 30 seconds")

            holdings = adapter.get_holdings()

            # Should return empty list on timeout
            assert holdings == []
            # Verify timeout was called
            mock_timeout.assert_called()

    def test_get_account_limits_timeout_returns_empty(self, adapter, mock_client):
        """Test get_account_limits() handles timeout gracefully"""
        # Mock timeout utility to raise TimeoutError
        with patch(
            "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.call_with_timeout"
        ) as mock_timeout:
            mock_timeout.side_effect = TimeoutError("SDK call timed out after 30 seconds")

            limits = adapter.get_account_limits()

            # Should return empty dict on timeout
            assert limits == {}
            # Verify timeout was called
            mock_timeout.assert_called()

    def test_timeout_not_treated_as_auth_error(self, adapter, mock_client, mock_auth_handler):
        """Test timeout is not treated as auth error (no re-auth triggered)"""
        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.call_with_timeout"
            ) as mock_timeout,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
        ):
            mock_timeout.side_effect = TimeoutError("SDK call timed out")

            holdings = adapter.get_holdings()

            # Should return empty list
            assert holdings == []
            # Should NOT trigger re-auth (timeout is not auth error)
            mock_reauth.assert_not_called()


class TestRetryLogic:
    """Test retry logic after re-authentication"""

    def test_get_holdings_retries_only_once(self, adapter, mock_client, mock_auth_handler):
        """Test get_holdings() only retries once after re-auth"""
        # All calls return auth error (re-auth won't help)
        mock_client.holdings.return_value = {"code": "900901", "message": "JWT token expired"}

        # Create a new mock client for after re-auth (also returns auth error)
        new_mock_client = MagicMock()
        new_mock_client.holdings.return_value = {"code": "900901", "message": "JWT token expired"}
        # get_client() should return mock_client first, then new_mock_client after re-auth
        # This simulates: refresh at start -> mock_client, refresh after re-auth -> new_mock_client
        mock_auth_handler.get_client.side_effect = [mock_client, new_mock_client]

        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_error"
            ) as mock_is_auth_error,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._check_reauth_failure_rate"
            ) as mock_check_rate,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
        ):
            # Setup mocks
            mock_is_auth_error.side_effect = lambda r: (
                r.get("code") == "900901" if isinstance(r, dict) else False
            )
            mock_check_rate.return_value = False  # Not blocked
            mock_reauth.return_value = True  # Re-auth succeeds (but retry still fails)

            holdings = adapter.get_holdings()

            # Should return empty list (max retries reached)
            assert holdings == []
            # Should attempt re-auth once
            mock_reauth.assert_called_once()
            # Should call holdings twice (original + 1 retry)
            # Original client called once, new client called once after re-auth
            assert mock_client.holdings.call_count == 1
            assert new_mock_client.holdings.call_count == 1

    def test_get_account_limits_retries_only_once(self, adapter, mock_client, mock_auth_handler):
        """Test get_account_limits() only retries once after re-auth"""
        # All calls return auth error
        mock_client.limits.return_value = {"code": "900901", "message": "JWT token expired"}

        # Create a new mock client for after re-auth (also returns auth error)
        new_mock_client = MagicMock()
        new_mock_client.limits.return_value = {"code": "900901", "message": "JWT token expired"}
        # get_client() should return mock_client first, then new_mock_client after re-auth
        # This simulates: refresh at start -> mock_client, refresh after re-auth -> new_mock_client
        mock_auth_handler.get_client.side_effect = [mock_client, new_mock_client]

        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_error"
            ) as mock_is_auth_error,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._check_reauth_failure_rate"
            ) as mock_check_rate,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
        ):
            # Setup mocks
            mock_is_auth_error.side_effect = lambda r: (
                r.get("code") == "900901" if isinstance(r, dict) else False
            )
            mock_check_rate.return_value = False  # Not blocked
            mock_reauth.return_value = True  # Re-auth succeeds

            limits = adapter.get_account_limits()

            # Should return empty dict (max retries reached)
            assert limits == {}
            # Should attempt re-auth once
            mock_reauth.assert_called_once()
            # Should call limits twice (original + 1 retry)
            # Original client called once, new client called once after re-auth
            assert mock_client.limits.call_count == 1
            assert new_mock_client.limits.call_count == 1


class TestBackwardCompatibility:
    """Test backward compatibility - normal success cases still work"""

    def test_get_holdings_success_no_reauth(self, adapter, mock_client, mock_auth_handler):
        """Test get_holdings() works normally without triggering re-auth"""
        mock_client.holdings.return_value = {
            "data": [
                {
                    "displaySymbol": "IDEA",
                    "averagePrice": 9.57,
                    "quantity": 35,
                    "closingPrice": 9.36,
                }
            ]
        }

        with patch(
            "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
        ) as mock_reauth:
            holdings = adapter.get_holdings()

            # Should work normally
            assert len(holdings) == 1
            assert holdings[0].symbol == "IDEA"
            # Should NOT trigger re-auth (no auth error)
            mock_reauth.assert_not_called()

    def test_get_account_limits_success_no_reauth(self, adapter, mock_client, mock_auth_handler):
        """Test get_account_limits() works normally without triggering re-auth"""
        mock_client.limits.return_value = {
            "Net": "100.50",
            "MarginUsed": "50.25",
            "CollateralValue": "200.75",
            "stCode": 200,
        }

        with patch(
            "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
        ) as mock_reauth:
            limits = adapter.get_account_limits()

            # Should work normally
            assert "available_cash" in limits
            assert float(limits["available_cash"].amount) == pytest.approx(100.50, abs=0.01)
            # Should NOT trigger re-auth (no auth error)
            mock_reauth.assert_not_called()

    def test_non_auth_error_returns_empty_no_reauth(self, adapter, mock_client, mock_auth_handler):
        """Test non-auth errors return empty result without re-auth"""
        mock_client.holdings.side_effect = ValueError("Invalid symbol")

        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_exception"
            ) as mock_is_auth_exception,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
        ):
            # Setup mocks
            mock_is_auth_exception.return_value = False  # Not an auth error

            holdings = adapter.get_holdings()

            # Should return empty list
            assert holdings == []
            # Should NOT trigger re-auth (not an auth error)
            mock_reauth.assert_not_called()


class TestClientRefreshOnObjectChange:
    """Test client refresh when client object changes (simulating re-auth in another thread)"""

    def test_get_holdings_refreshes_when_client_object_changes(
        self, adapter, mock_client, mock_auth_handler
    ):
        """
        Test get_holdings() refreshes client when auth.client changes (simulating re-auth elsewhere).
        This is the key scenario for SDK timeout fix: when auth.client is replaced (e.g., by re-auth
        in another thread), we should refresh to get the new client with fresh session, even if
        the old client would still work.
        """
        # Initial client (old session)
        mock_client.holdings.return_value = {
            "data": [
                {
                    "displaySymbol": "IDEA",
                    "averagePrice": 9.57,
                    "quantity": 35,
                    "closingPrice": 9.36,
                }
            ]
        }

        # New client (fresh session after re-auth in another thread)
        new_mock_client = MagicMock()
        new_mock_client.holdings.return_value = {
            "data": [
                {
                    "displaySymbol": "TCS",
                    "averagePrice": 3500.0,
                    "quantity": 10,
                    "closingPrice": 3600.0,
                }
            ]
        }

        # Simulate: auth.client changed (re-auth happened elsewhere)
        # First call to get_client() returns new client (different object)
        mock_auth_handler.get_client.return_value = new_mock_client

        # Call get_holdings() - should refresh to use new client
        holdings = adapter.get_holdings()

        # Should use the new client (fresh session)
        assert len(holdings) == 1
        assert holdings[0].symbol == "TCS"
        # Verify new client was used
        new_mock_client.holdings.assert_called_once()
        # Verify old client was NOT used
        mock_client.holdings.assert_not_called()
        # Verify adapter's client was updated
        assert adapter._client is new_mock_client

    def test_get_all_orders_refreshes_when_client_object_changes(
        self, adapter, mock_client, mock_auth_handler
    ):
        """
        Test get_all_orders() refreshes client when auth.client changes.
        This ensures the SDK timeout fix works for all API methods.
        """
        # Initial client (old session)
        mock_client.order_report.return_value = {
            "data": [
                {
                    "nOrdNo": "11111",
                    "trdSym": "IDEA-EQ",
                    "qty": 10,
                    "stat": "OPEN",
                    "trnsTp": "B",
                }
            ]
        }

        # New client (fresh session after re-auth in another thread)
        new_mock_client = MagicMock()
        new_mock_client.order_report.return_value = {
            "data": [
                {
                    "nOrdNo": "22222",
                    "trdSym": "TCS-EQ",
                    "qty": 5,
                    "stat": "OPEN",
                    "trnsTp": "B",
                }
            ]
        }

        # Simulate: auth.client changed (re-auth happened elsewhere)
        mock_auth_handler.get_client.return_value = new_mock_client

        # Call get_all_orders() - should refresh to use new client
        orders = adapter.get_all_orders()

        # Should use the new client (fresh session)
        assert len(orders) == 1
        assert orders[0].order_id == "22222"
        # Verify new client was used
        new_mock_client.order_report.assert_called_once()
        # Verify old client was NOT used
        mock_client.order_report.assert_not_called()
        # Verify adapter's client was updated
        assert adapter._client is new_mock_client

    def test_place_order_refreshes_when_client_object_changes(
        self, adapter, mock_client, mock_auth_handler
    ):
        """
        Test place_order() refreshes client when auth.client changes.
        This ensures the SDK timeout fix works for order placement.
        """
        # Initial client (old session)
        mock_client.place_order.return_value = {"neoOrdNo": "11111", "status": "success"}

        # New client (fresh session after re-auth in another thread)
        new_mock_client = MagicMock()
        new_mock_client.place_order.return_value = {"neoOrdNo": "22222", "status": "success"}

        # Simulate: auth.client changed (re-auth happened elsewhere)
        mock_auth_handler.get_client.return_value = new_mock_client

        order = Order(
            symbol="IDEA",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            exchange=Exchange.NSE,
            price=Money.from_float(100.0),
        )

        # Call place_order() - should refresh to use new client
        order_id = adapter.place_order(order)

        # Should use the new client (fresh session)
        assert order_id == "22222"
        # Verify new client was used
        new_mock_client.place_order.assert_called_once()
        # Verify old client was NOT used
        mock_client.place_order.assert_not_called()
        # Verify adapter's client was updated
        assert adapter._client is new_mock_client

    def test_cancel_order_refreshes_when_client_object_changes(
        self, adapter, mock_client, mock_auth_handler
    ):
        """
        Test cancel_order() refreshes client when auth.client changes.
        This ensures the SDK timeout fix works for order cancellation.
        """
        # Initial client (old session)
        mock_client.cancel_order.return_value = True

        # New client (fresh session after re-auth in another thread)
        new_mock_client = MagicMock()
        new_mock_client.cancel_order.return_value = True

        # Simulate: auth.client changed (re-auth happened elsewhere)
        mock_auth_handler.get_client.return_value = new_mock_client

        # Call cancel_order() - should refresh to use new client
        result = adapter.cancel_order("12345")

        # Should use the new client (fresh session)
        assert result is True
        # Verify new client was used
        new_mock_client.cancel_order.assert_called_once_with("12345")
        # Verify old client was NOT used
        mock_client.cancel_order.assert_not_called()
        # Verify adapter's client was updated
        assert adapter._client is new_mock_client

    def test_client_not_refreshed_when_same_object(self, adapter, mock_client, mock_auth_handler):
        """
        Test that client is NOT refreshed when get_client() returns the same object.
        This ensures we don't unnecessarily refresh when the client hasn't changed.
        """
        mock_client.holdings.return_value = {
            "data": [
                {
                    "displaySymbol": "IDEA",
                    "averagePrice": 9.57,
                    "quantity": 35,
                    "closingPrice": 9.36,
                }
            ]
        }

        # get_client() returns the same object (normal case, no re-auth)
        mock_auth_handler.get_client.return_value = mock_client

        # Store original client reference
        original_client = adapter._client

        # Call get_holdings() - should NOT refresh (same object)
        holdings = adapter.get_holdings()

        # Should work normally
        assert len(holdings) == 1
        assert holdings[0].symbol == "IDEA"
        # Verify client was used
        mock_client.holdings.assert_called_once()
        # Verify adapter's client is still the same object (no unnecessary refresh)
        # Note: The refresh logic will still set it, but it's the same object, so no harm
        assert adapter._client is mock_client


class TestInfiniteLoopPrevention:
    """Test infinite loop prevention mechanisms"""

    def test_max_retries_enforced(self, adapter, mock_client, mock_auth_handler):
        """Test that max retries (1) is enforced"""
        # All calls return auth error
        mock_client.holdings.return_value = {"code": "900901", "message": "JWT token expired"}

        # Create a new mock client for after re-auth (also returns auth error)
        new_mock_client = MagicMock()
        new_mock_client.holdings.return_value = {"code": "900901", "message": "JWT token expired"}
        # get_client() should return mock_client first, then new_mock_client after re-auth
        # This simulates: refresh at start -> mock_client, refresh after re-auth -> new_mock_client
        mock_auth_handler.get_client.side_effect = [mock_client, new_mock_client]

        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_error"
            ) as mock_is_auth_error,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._check_reauth_failure_rate"
            ) as mock_check_rate,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
        ):
            # Setup mocks
            mock_is_auth_error.side_effect = lambda r: (
                r.get("code") == "900901" if isinstance(r, dict) else False
            )
            mock_check_rate.return_value = False  # Not blocked
            mock_reauth.return_value = True  # Re-auth always succeeds

            holdings = adapter.get_holdings()

            # Should return empty list (max retries reached)
            assert holdings == []
            # Should only attempt re-auth once
            mock_reauth.assert_called_once()
            # Should only call holdings twice (original + 1 retry, not infinite)
            # Original client called once, new client called once after re-auth
            assert mock_client.holdings.call_count == 1
            assert new_mock_client.holdings.call_count == 1

    def test_failure_rate_blocks_after_max_failures(self, adapter, mock_client, mock_auth_handler):
        """Test failure rate blocking prevents rapid re-auth attempts"""
        mock_client.holdings.return_value = {"code": "900901", "message": "JWT token expired"}

        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_error"
            ) as mock_is_auth_error,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._check_reauth_failure_rate"
            ) as mock_check_rate,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
        ):
            # Setup mocks
            mock_is_auth_error.return_value = True
            mock_check_rate.return_value = True  # Blocked (too many failures)

            holdings = adapter.get_holdings()

            # Should return empty list immediately (blocked)
            assert holdings == []
            # Should NOT attempt re-auth (blocked)
            mock_reauth.assert_not_called()
            # Should only call holdings once (no retry, blocked immediately)
            assert mock_client.holdings.call_count == 1


class TestPlaceOrderReAuth:
    """Test re-authentication for place_order()"""

    def test_place_order_reauth_on_auth_error_in_response(
        self, adapter, mock_client, mock_auth_handler
    ):
        """Test place_order() triggers re-auth on auth error in response"""
        # First call returns auth error, second call succeeds after re-auth
        mock_client.place_order.return_value = {"code": "900901", "message": "JWT token expired"}

        # Create a new mock client for after re-auth
        new_mock_client = MagicMock()
        new_mock_client.place_order.return_value = {"neoOrdNo": "12345", "status": "success"}
        # get_client() should return mock_client first, then new_mock_client after re-auth
        # This simulates: refresh at start -> mock_client, refresh after re-auth -> new_mock_client
        mock_auth_handler.get_client.side_effect = [mock_client, new_mock_client]

        order = Order(
            symbol="IDEA",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            exchange=Exchange.NSE,
            price=Money.from_float(100.0),
        )

        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_error"
            ) as mock_is_auth_error,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._check_reauth_failure_rate"
            ) as mock_check_rate,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._record_reauth_failure"
            ) as mock_record,
        ):
            # Setup mocks
            mock_is_auth_error.side_effect = lambda r: (
                r.get("code") == "900901" if isinstance(r, dict) else False
            )
            mock_check_rate.return_value = False  # Not blocked
            mock_reauth.return_value = True  # Re-auth succeeds

            order_id = adapter.place_order(order)

            # Should retry after re-auth and succeed
            assert order_id == "12345"
            # Verify re-auth was attempted
            mock_reauth.assert_called_once()
            # Should not record failure
            mock_record.assert_not_called()

    def test_place_order_reauth_on_auth_exception(self, adapter, mock_client, mock_auth_handler):
        """Test place_order() triggers re-auth on auth exception"""
        # First call raises auth exception
        mock_client.place_order.side_effect = Exception("JWT token expired")

        # Create a new mock client for after re-auth
        new_mock_client = MagicMock()
        new_mock_client.place_order.return_value = {"neoOrdNo": "67890", "status": "success"}
        # get_client() should return mock_client first, then new_mock_client after re-auth
        # This simulates: refresh at start -> mock_client, refresh after re-auth -> new_mock_client
        mock_auth_handler.get_client.side_effect = [mock_client, new_mock_client]

        order = Order(
            symbol="TCS",
            quantity=5,
            order_type=OrderType.LIMIT,
            transaction_type=TransactionType.BUY,
            exchange=Exchange.NSE,
            price=Money.from_float(3500.0),
        )

        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_exception"
            ) as mock_is_auth_exception,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._check_reauth_failure_rate"
            ) as mock_check_rate,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._record_reauth_failure"
            ) as mock_record,
        ):
            # Setup mocks
            mock_is_auth_exception.side_effect = lambda e: (
                "JWT" in str(e) if isinstance(e, Exception) else False
            )
            mock_check_rate.return_value = False  # Not blocked
            mock_reauth.return_value = True  # Re-auth succeeds

            order_id = adapter.place_order(order)

            # Should retry after re-auth and succeed
            assert order_id == "67890"
            # Verify re-auth was attempted
            mock_reauth.assert_called_once()
            # Should not record failure
            mock_record.assert_not_called()

    def test_place_order_timeout_raises_error(self, adapter, mock_client):
        """Test place_order() handles timeout gracefully when no auth handler"""
        order = Order(
            symbol="IDEA",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            exchange=Exchange.NSE,
            price=Money.from_float(100.0),
        )

        # Remove auth handler to test fallback behavior
        adapter.auth_handler = None

        # Mock timeout utility to raise TimeoutError
        with patch(
            "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.call_with_timeout"
        ) as mock_timeout:
            mock_timeout.side_effect = TimeoutError("SDK call timed out after 30 seconds")

            # Should raise RuntimeError after trying all methods
            with pytest.raises(RuntimeError, match="Failed to place order"):
                adapter.place_order(order)

    def test_place_order_timeout_refreshes_client_and_retries(
        self, adapter, mock_client, mock_auth_handler
    ):
        """Test place_order() refreshes client on timeout and retries successfully"""
        order = Order(
            symbol="IDEA",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            exchange=Exchange.NSE,
            price=Money.from_float(100.0),
        )

        # Create a new mock client for after refresh
        new_mock_client = MagicMock()
        new_mock_client.place_order.return_value = {"neoOrdNo": "12345", "status": "success"}
        mock_auth_handler.is_authenticated.return_value = True
        # get_client() should return mock_client first, then new_mock_client after re-auth
        # This simulates: refresh at start -> mock_client, refresh after re-auth -> new_mock_client
        mock_auth_handler.get_client.side_effect = [mock_client, new_mock_client]

        # First call times out, second call succeeds after client refresh
        call_count = 0

        def timeout_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("SDK call timed out after 30 seconds")
            return {"neoOrdNo": "12345", "status": "success"}

        with patch(
            "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.call_with_timeout"
        ) as mock_timeout:
            mock_timeout.side_effect = timeout_then_success

            result = adapter.place_order(order)

            # Should succeed after client refresh and retry
            assert result == "12345"
            # Verify client was refreshed
            assert adapter._client == new_mock_client
            # Verify timeout was called twice (original + retry)
            assert mock_timeout.call_count == 2

    def test_place_order_connection_error_refreshes_client_and_retries(
        self, adapter, mock_client, mock_auth_handler
    ):
        """Test place_order() refreshes client on connection error and retries successfully"""
        order = Order(
            symbol="IDEA",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            exchange=Exchange.NSE,
            price=Money.from_float(100.0),
        )

        # Create a new mock client for after refresh
        new_mock_client = MagicMock()
        new_mock_client.place_order.return_value = {"neoOrdNo": "12345", "status": "success"}
        mock_auth_handler.is_authenticated.return_value = True
        # get_client() should return mock_client first, then new_mock_client after re-auth
        # This simulates: refresh at start -> mock_client, refresh after re-auth -> new_mock_client
        mock_auth_handler.get_client.side_effect = [mock_client, new_mock_client]

        # First call raises connection error, second call succeeds after client refresh
        call_count = 0

        def connection_error_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Connection refused")
            return {"neoOrdNo": "12345", "status": "success"}

        mock_client.place_order.side_effect = connection_error_then_success

        result = adapter.place_order(order)

        # Should succeed after client refresh and retry
        assert result == "12345"
        # Verify client was refreshed
        assert adapter._client == new_mock_client
        # Verify place_order was called on original client once, then on new client once
        assert mock_client.place_order.call_count == 1
        assert new_mock_client.place_order.call_count == 1

    def test_place_order_blocked_by_failure_rate(self, adapter, mock_client, mock_auth_handler):
        """Test place_order() is blocked when failure rate is too high"""
        mock_client.place_order.return_value = {"code": "900901", "message": "JWT token expired"}

        order = Order(
            symbol="IDEA",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            exchange=Exchange.NSE,
            price=Money.from_float(100.0),
        )

        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_error"
            ) as mock_is_auth_error,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._check_reauth_failure_rate"
            ) as mock_check_rate,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
        ):
            # Setup mocks
            mock_is_auth_error.side_effect = lambda r: (
                r.get("code") == "900901" if isinstance(r, dict) else False
            )
            mock_check_rate.return_value = True  # Blocked

            # Should raise RuntimeError (blocked)
            with pytest.raises(RuntimeError, match="re-authentication blocked"):
                adapter.place_order(order)

            # Should NOT attempt re-auth (blocked)
            mock_reauth.assert_not_called()


class TestCancelOrderReAuth:
    """Test re-authentication for cancel_order()"""

    def test_cancel_order_reauth_on_auth_exception(self, adapter, mock_client, mock_auth_handler):
        """Test cancel_order() triggers re-auth on auth exception"""
        # First call raises auth exception
        mock_client.cancel_order.side_effect = Exception("JWT token expired")

        # Create a new mock client for after re-auth
        new_mock_client = MagicMock()
        new_mock_client.cancel_order.return_value = True
        # get_client() should return mock_client first, then new_mock_client after re-auth
        # This simulates: refresh at start -> mock_client, refresh after re-auth -> new_mock_client
        mock_auth_handler.get_client.side_effect = [mock_client, new_mock_client]

        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_exception"
            ) as mock_is_auth_exception,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._check_reauth_failure_rate"
            ) as mock_check_rate,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._record_reauth_failure"
            ) as mock_record,
        ):
            # Setup mocks
            mock_is_auth_exception.side_effect = lambda e: (
                "JWT" in str(e) if isinstance(e, Exception) else False
            )
            mock_check_rate.return_value = False  # Not blocked
            mock_reauth.return_value = True  # Re-auth succeeds

            result = adapter.cancel_order("12345")

            # Should retry after re-auth and succeed
            assert result is True
            # Verify re-auth was attempted
            mock_reauth.assert_called_once()
            # Should not record failure
            mock_record.assert_not_called()

    def test_cancel_order_timeout_returns_false(self, adapter, mock_client):
        """Test cancel_order() handles timeout gracefully when no auth handler"""
        # Remove auth handler to test fallback behavior
        adapter.auth_handler = None

        # Mock timeout utility to raise TimeoutError
        with patch(
            "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.call_with_timeout"
        ) as mock_timeout:
            mock_timeout.side_effect = TimeoutError("SDK call timed out after 30 seconds")

            result = adapter.cancel_order("12345")

            # Should return False on timeout
            assert result is False

    def test_cancel_order_timeout_refreshes_client_and_retries(
        self, adapter, mock_client, mock_auth_handler
    ):
        """Test cancel_order() refreshes client on timeout and retries successfully"""
        # Create a new mock client for after refresh
        new_mock_client = MagicMock()
        new_mock_client.cancel_order.return_value = True
        mock_auth_handler.is_authenticated.return_value = True
        # get_client() should return mock_client first, then new_mock_client after re-auth
        # This simulates: refresh at start -> mock_client, refresh after re-auth -> new_mock_client
        mock_auth_handler.get_client.side_effect = [mock_client, new_mock_client]

        # First call times out, second call succeeds after client refresh
        call_count = 0

        def timeout_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("SDK call timed out after 30 seconds")
            return True

        with patch(
            "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.call_with_timeout"
        ) as mock_timeout:
            mock_timeout.side_effect = timeout_then_success

            result = adapter.cancel_order("12345")

            # Should succeed after client refresh and retry
            assert result is True
            # Verify client was refreshed
            assert adapter._client == new_mock_client
            # Verify timeout was called twice (original + retry)
            assert mock_timeout.call_count == 2

    def test_cancel_order_connection_error_refreshes_client_and_retries(
        self, adapter, mock_client, mock_auth_handler
    ):
        """Test cancel_order() refreshes client on connection error and retries successfully"""
        # Create a new mock client for after refresh
        new_mock_client = MagicMock()
        new_mock_client.cancel_order.return_value = True
        mock_auth_handler.is_authenticated.return_value = True
        # get_client() should return mock_client first, then new_mock_client after re-auth
        # This simulates: refresh at start -> mock_client, refresh after re-auth -> new_mock_client
        mock_auth_handler.get_client.side_effect = [mock_client, new_mock_client]

        # First call raises connection error, second call succeeds after client refresh
        call_count = 0

        def connection_error_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Connection refused")
            return True

        mock_client.cancel_order.side_effect = connection_error_then_success

        result = adapter.cancel_order("12345")

        # Should succeed after client refresh and retry
        assert result is True
        # Verify client was refreshed
        assert adapter._client == new_mock_client
        # Verify cancel_order was called on original client once, then on new client once
        assert mock_client.cancel_order.call_count == 1
        assert new_mock_client.cancel_order.call_count == 1

    def test_cancel_order_blocked_by_failure_rate(self, adapter, mock_client, mock_auth_handler):
        """Test cancel_order() is blocked when failure rate is too high"""
        mock_client.cancel_order.side_effect = Exception("JWT token expired")

        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_exception"
            ) as mock_is_auth_exception,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._check_reauth_failure_rate"
            ) as mock_check_rate,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
        ):
            # Setup mocks
            mock_is_auth_exception.side_effect = lambda e: (
                "JWT" in str(e) if isinstance(e, Exception) else False
            )
            mock_check_rate.return_value = True  # Blocked

            result = adapter.cancel_order("12345")

            # Should return False (blocked)
            assert result is False
            # Should NOT attempt re-auth (blocked)
            mock_reauth.assert_not_called()


class TestGetAllOrdersReAuth:
    """Test re-authentication for get_all_orders()"""

    def test_get_all_orders_reauth_on_auth_error_in_response(
        self, adapter, mock_client, mock_auth_handler
    ):
        """Test get_all_orders() triggers re-auth on auth error in response"""
        # First call returns auth error, second call succeeds after re-auth
        mock_client.order_report.return_value = {"code": "900901", "message": "JWT token expired"}

        # Create a new mock client for after re-auth
        new_mock_client = MagicMock()
        new_mock_client.order_report.return_value = {
            "data": [
                {
                    "nOrdNo": "12345",
                    "trdSym": "IDEA-EQ",
                    "qty": 10,
                    "stat": "PENDING",
                    "trnsTp": "B",
                    "prcTp": "MKT",
                }
            ]
        }
        # get_client() should return mock_client first, then new_mock_client after re-auth
        # This simulates: refresh at start -> mock_client, refresh after re-auth -> new_mock_client
        mock_auth_handler.get_client.side_effect = [mock_client, new_mock_client]

        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_error"
            ) as mock_is_auth_error,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._check_reauth_failure_rate"
            ) as mock_check_rate,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._record_reauth_failure"
            ) as mock_record,
        ):
            # Setup mocks
            mock_is_auth_error.side_effect = lambda r: (
                r.get("code") == "900901" if isinstance(r, dict) else False
            )
            mock_check_rate.return_value = False  # Not blocked
            mock_reauth.return_value = True  # Re-auth succeeds

            orders = adapter.get_all_orders()

            # Should retry after re-auth and succeed
            assert len(orders) == 1
            assert orders[0].order_id == "12345"
            # Verify re-auth was attempted
            mock_reauth.assert_called_once()
            # Should not record failure
            mock_record.assert_not_called()

    def test_get_all_orders_reauth_on_auth_exception(self, adapter, mock_client, mock_auth_handler):
        """Test get_all_orders() triggers re-auth on auth exception"""
        # First call raises auth exception
        mock_client.order_report.side_effect = Exception("JWT token expired")

        # Create a new mock client for after re-auth
        new_mock_client = MagicMock()
        new_mock_client.order_report.return_value = {
            "data": [
                {
                    "nOrdNo": "67890",
                    "trdSym": "TCS-EQ",
                    "qty": 5,
                    "stat": "EXECUTED",
                    "trnsTp": "S",
                    "prcTp": "L",
                    "prc": "3500.0",  # Price required for LIMIT orders
                }
            ]
        }
        # get_client() should return mock_client first, then new_mock_client after re-auth
        # This simulates: refresh at start -> mock_client, refresh after re-auth -> new_mock_client
        mock_auth_handler.get_client.side_effect = [mock_client, new_mock_client]

        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_exception"
            ) as mock_is_auth_exception,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._check_reauth_failure_rate"
            ) as mock_check_rate,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._record_reauth_failure"
            ) as mock_record,
        ):
            # Setup mocks
            mock_is_auth_exception.side_effect = lambda e: (
                "JWT" in str(e) if isinstance(e, Exception) else False
            )
            mock_check_rate.return_value = False  # Not blocked
            mock_reauth.return_value = True  # Re-auth succeeds

            orders = adapter.get_all_orders()

            # Should retry after re-auth and succeed
            assert len(orders) == 1
            assert orders[0].order_id == "67890"
            # Verify re-auth was attempted
            mock_reauth.assert_called_once()
            # Should not record failure
            mock_record.assert_not_called()

    def test_get_all_orders_timeout_returns_empty(self, adapter, mock_client):
        """Test get_all_orders() handles timeout gracefully"""
        # Mock timeout utility to raise TimeoutError
        with patch(
            "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.call_with_timeout"
        ) as mock_timeout:
            mock_timeout.side_effect = TimeoutError("SDK call timed out after 30 seconds")

            orders = adapter.get_all_orders()

            # Should return empty list on timeout
            assert orders == []

    def test_get_all_orders_blocked_by_failure_rate(self, adapter, mock_client, mock_auth_handler):
        """Test get_all_orders() is blocked when failure rate is too high"""
        mock_client.order_report.return_value = {"code": "900901", "message": "JWT token expired"}

        with (
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter.is_auth_error"
            ) as mock_is_auth_error,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._check_reauth_failure_rate"
            ) as mock_check_rate,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter._attempt_reauth_thread_safe"
            ) as mock_reauth,
        ):
            # Setup mocks
            mock_is_auth_error.side_effect = lambda r: (
                r.get("code") == "900901" if isinstance(r, dict) else False
            )
            mock_check_rate.return_value = True  # Blocked

            orders = adapter.get_all_orders()

            # Should return empty list immediately (blocked)
            assert orders == []
            # Should NOT attempt re-auth (blocked)
            mock_reauth.assert_not_called()
