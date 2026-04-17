#!/usr/bin/env python3
"""
Regression tests for broker session re-authentication fixes.

These tests ensure that critical authentication fixes remain working:
1. Session expiration bypasses cooldown (allows immediate re-auth)
2. Stale session detection (is_authenticated=True but client=None)
3. Re-authentication during API calls when session expires
4. Session sharing across multiple API calls
5. Re-auth cooldown only applies to valid (non-expired) sessions

If any of these tests fail, it indicates a regression in the authentication
fixes that were implemented to handle session expiration and re-authentication.
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from modules.kotak_neo_auto_trader.domain.entities import Holding
from modules.kotak_neo_auto_trader.domain.value_objects import Exchange, Money
from server.app.routers import broker
from src.infrastructure.db.models import TradeMode


class DummyUser:
    """Dummy user for testing"""

    def __init__(self, id: int):
        self.id = id


class DummySettingsRepo:
    """Dummy settings repository for testing"""

    def __init__(self, db):
        self.db = db
        self.settings = MagicMock()
        self.settings.trade_mode = TradeMode.BROKER
        self.settings.broker_creds_encrypted = b"encrypted_creds"
        self.update_called = []
        self.get_by_user_id_called = []

    def get_by_user_id(self, user_id):
        self.get_by_user_id_called.append(user_id)
        return self.settings


class TestBrokerSessionReauthRegression:
    """
    Regression tests for broker session re-authentication.

    These tests verify that the critical fixes for session expiration
    and re-authentication continue to work correctly.
    """

    def test_expired_session_bypasses_cooldown(self, monkeypatch):
        """
        CRITICAL: Expired sessions must bypass cooldown to allow immediate re-auth.

        This test ensures that if a session is expired, it can be re-authenticated
        immediately even if there was a recent re-auth attempt (cooldown active).
        This prevents 500 errors when sessions expire during the cooldown period.
        """
        user = DummyUser(id=1)

        repo = DummySettingsRepo(object())
        monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

        def mock_decrypt(creds):
            return {"api_key": "key", "api_secret": "secret"}

        monkeypatch.setattr(broker, "decrypt_broker_credentials", mock_decrypt)

        def mock_create_temp_env(creds):
            return "/tmp/test.env"

        monkeypatch.setattr(broker, "create_temp_env_file", mock_create_temp_env)

        # Create expired session (is_session_valid returns False)
        expired_auth = MagicMock()
        expired_auth.is_authenticated.return_value = True
        expired_auth.get_client.return_value = None
        expired_auth.is_session_valid.return_value = False  # Session expired

        # New auth after re-authentication
        new_auth = MagicMock()
        new_auth.is_authenticated.return_value = True
        new_client = MagicMock()
        new_auth.get_client.return_value = new_client

        mock_session_manager = MagicMock()
        # First call returns expired auth, second call (with force_new) returns new auth
        # Even if cooldown is active, expired session should bypass it
        mock_session_manager.get_or_create_session.side_effect = [expired_auth, new_auth]

        # Set cooldown as if re-auth happened recently
        mock_session_manager._last_reauth_time = {user.id: 0}  # Recent re-auth

        # Mock broker gateway
        mock_holding = Holding(
            symbol="RELIANCE.NS",
            exchange=Exchange.NSE,
            quantity=10,
            average_price=Money(Decimal("2500.00")),
            current_price=Money(Decimal("2600.00")),
            last_updated=datetime.now(),
        )

        mock_broker = MagicMock()
        mock_broker.get_holdings.return_value = [mock_holding]
        mock_broker.get_account_limits.return_value = {
            "available_margin": {"cash": 100000.0},
        }
        mock_broker._connected = True

        def mock_broker_factory(broker_type, auth_handler):
            return mock_broker

        # Mock yfinance
        mock_ticker = MagicMock()
        mock_ticker.info = {"currentPrice": 2600.0}

        def mock_yf_ticker(symbol):
            return mock_ticker

        with (
            patch(
                "modules.kotak_neo_auto_trader.shared_session_manager.get_shared_session_manager",
                return_value=mock_session_manager,
            ),
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_factory.BrokerFactory.create_broker",
                mock_broker_factory,
            ),
            patch("yfinance.Ticker", mock_yf_ticker),
        ):
            db_session = MagicMock()
            result = broker.get_broker_portfolio(db=db_session, current=user)

            # Should succeed after re-authentication (cooldown bypassed)
            assert len(result.holdings) == 1

            # Verify re-authentication was attempted (cooldown bypassed)
            assert mock_session_manager.get_or_create_session.call_count == 2
            # Second call should use force_new=True
            second_call_kwargs = mock_session_manager.get_or_create_session.call_args_list[1].kwargs
            assert second_call_kwargs.get("force_new") is True

    def test_valid_session_with_client_respects_cooldown(self, monkeypatch):
        """
        CRITICAL: Valid (non-expired) sessions with client must respect cooldown.

        This test ensures that if a session is still valid AND has a client,
        the cooldown is applied to prevent OTP spam. Only expired sessions bypass cooldown.
        Note: If client is None, re-auth is triggered regardless of cooldown (stale session).
        """
        user = DummyUser(id=2)

        repo = DummySettingsRepo(object())
        monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

        def mock_decrypt(creds):
            return {"api_key": "key", "api_secret": "secret"}

        monkeypatch.setattr(broker, "decrypt_broker_credentials", mock_decrypt)

        def mock_create_temp_env(creds):
            return "/tmp/test.env"

        monkeypatch.setattr(broker, "create_temp_env_file", mock_create_temp_env)

        # Create valid session with client (both is_session_valid and client available)
        valid_auth = MagicMock()
        valid_auth.is_authenticated.return_value = True
        valid_client = MagicMock()
        valid_auth.get_client.return_value = valid_client  # Client available
        valid_auth.is_session_valid.return_value = True  # Session still valid

        mock_session_manager = MagicMock()
        # Should return existing session (cooldown active)
        mock_session_manager.get_or_create_session.return_value = valid_auth

        # Set cooldown as if re-auth happened recently
        mock_session_manager._last_reauth_time = {user.id: 0}  # Recent re-auth

        # Mock broker gateway
        mock_holding = Holding(
            symbol="RELIANCE.NS",
            exchange=Exchange.NSE,
            quantity=10,
            average_price=Money(Decimal("2500.00")),
            current_price=Money(Decimal("2600.00")),
            last_updated=datetime.now(),
        )

        mock_broker = MagicMock()
        mock_broker.get_holdings.return_value = [mock_holding]
        mock_broker.get_account_limits.return_value = {
            "available_margin": {"cash": 100000.0},
        }
        mock_broker._connected = True

        def mock_broker_factory(broker_type, auth_handler):
            return mock_broker

        # Mock yfinance
        mock_ticker = MagicMock()
        mock_ticker.info = {"currentPrice": 2600.0}

        def mock_yf_ticker(symbol):
            return mock_ticker

        with (
            patch(
                "modules.kotak_neo_auto_trader.shared_session_manager.get_shared_session_manager",
                return_value=mock_session_manager,
            ),
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_factory.BrokerFactory.create_broker",
                mock_broker_factory,
            ),
            patch("yfinance.Ticker", mock_yf_ticker),
        ):
            db_session = MagicMock()
            result = broker.get_broker_portfolio(db=db_session, current=user)

            # Should succeed using existing session (cooldown respected)
            assert len(result.holdings) == 1

            # Verify re-authentication was NOT attempted (cooldown active)
            # get_or_create_session should be called once (returns existing)
            assert mock_session_manager.get_or_create_session.call_count == 1
            # Should NOT use force_new=True (cooldown prevents it)
            call_kwargs = mock_session_manager.get_or_create_session.call_args.kwargs
            assert call_kwargs.get("force_new") is not True

    def test_stale_session_detection_triggers_reauth(self, monkeypatch):
        """
        CRITICAL: Stale session (is_authenticated=True but client=None) must trigger re-auth.

        This test ensures that when is_authenticated() returns True but get_client()
        returns None, the system detects this as a stale session and forces re-authentication.
        """
        user = DummyUser(id=3)

        repo = DummySettingsRepo(object())
        monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

        def mock_decrypt(creds):
            return {"api_key": "key", "api_secret": "secret"}

        monkeypatch.setattr(broker, "decrypt_broker_credentials", mock_decrypt)

        def mock_create_temp_env(creds):
            return "/tmp/test.env"

        monkeypatch.setattr(broker, "create_temp_env_file", mock_create_temp_env)

        # Stale session: is_authenticated=True but client=None
        # Session must be valid (not expired) for stale session check to trigger
        stale_auth = MagicMock()
        stale_auth.is_authenticated.return_value = True
        stale_auth.get_client.return_value = None  # Client is None - session is stale
        stale_auth.is_session_valid.return_value = True  # Session valid but client None

        # New auth after re-authentication
        new_auth = MagicMock()
        new_auth.is_authenticated.return_value = True
        new_client = MagicMock()
        new_auth.get_client.return_value = new_client

        mock_session_manager = MagicMock()
        mock_session_manager.get_or_create_session.side_effect = [stale_auth, new_auth]
        mock_session_manager.clear_session = MagicMock()

        # Mock broker gateway
        mock_holding = Holding(
            symbol="RELIANCE.NS",
            exchange=Exchange.NSE,
            quantity=10,
            average_price=Money(Decimal("2500.00")),
            current_price=Money(Decimal("2600.00")),
            last_updated=datetime.now(),
        )

        mock_broker = MagicMock()
        mock_broker.get_holdings.return_value = [mock_holding]
        mock_broker.get_account_limits.return_value = {
            "available_margin": {"cash": 100000.0},
        }
        mock_broker._connected = True

        def mock_broker_factory(broker_type, auth_handler):
            return mock_broker

        # Mock yfinance
        mock_ticker = MagicMock()
        mock_ticker.info = {"currentPrice": 2600.0}

        def mock_yf_ticker(symbol):
            return mock_ticker

        with (
            patch(
                "modules.kotak_neo_auto_trader.shared_session_manager.get_shared_session_manager",
                return_value=mock_session_manager,
            ),
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_factory.BrokerFactory.create_broker",
                mock_broker_factory,
            ),
            patch("yfinance.Ticker", mock_yf_ticker),
        ):
            db_session = MagicMock()
            result = broker.get_broker_portfolio(db=db_session, current=user)

            # Should succeed after re-authentication
            assert len(result.holdings) == 1

            # Verify stale session was detected and cleared
            assert mock_session_manager.clear_session.called
            assert mock_session_manager.clear_session.call_args[0][0] == user.id

            # Verify re-authentication was attempted
            assert mock_session_manager.get_or_create_session.call_count == 2
            # Second call should use force_new=True
            second_call_kwargs = mock_session_manager.get_or_create_session.call_args_list[1].kwargs
            assert second_call_kwargs.get("force_new") is True

    def test_multiple_reauth_attempts_when_client_still_none(self, monkeypatch):
        """
        CRITICAL: Multiple re-auth attempts when client is None after first re-auth.

        This test ensures that if after the first re-auth, client is still None,
        the system attempts a second re-auth and then calls connect().
        """
        user = DummyUser(id=4)

        repo = DummySettingsRepo(object())
        monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

        def mock_decrypt(creds):
            return {"api_key": "key", "api_secret": "secret"}

        monkeypatch.setattr(broker, "decrypt_broker_credentials", mock_decrypt)

        def mock_create_temp_env(creds):
            return "/tmp/test.env"

        monkeypatch.setattr(broker, "create_temp_env_file", mock_create_temp_env)

        # Stale session: is_authenticated=True but client=None
        stale_auth = MagicMock()
        stale_auth.is_authenticated.return_value = True
        stale_auth.get_client.return_value = None
        stale_auth.is_session_valid.return_value = True

        # First re-auth succeeds but client is still None
        first_reauth_auth = MagicMock()
        first_reauth_auth.is_authenticated.return_value = True
        first_reauth_auth.get_client.return_value = None  # Client still None

        # Second re-auth succeeds and connect() is called
        second_reauth_auth = MagicMock()
        second_reauth_auth.is_authenticated.return_value = True
        second_reauth_auth.get_client.return_value = None  # Will trigger connect()

        mock_session_manager = MagicMock()
        mock_session_manager.get_or_create_session.side_effect = [
            stale_auth,
            first_reauth_auth,
            second_reauth_auth,
        ]

        # Mock broker gateway - connect() succeeds after second re-auth
        mock_holding = Holding(
            symbol="RELIANCE.NS",
            exchange=Exchange.NSE,
            quantity=10,
            average_price=Money(Decimal("2500.00")),
            current_price=Money(Decimal("2600.00")),
            last_updated=datetime.now(),
        )

        mock_broker = MagicMock()
        mock_broker.get_holdings.return_value = [mock_holding]
        mock_broker.get_account_limits.return_value = {
            "available_margin": {"cash": 100000.0},
        }
        mock_broker.connect.return_value = True  # Connect succeeds

        def mock_broker_factory(broker_type, auth_handler):
            return mock_broker

        # Mock yfinance
        mock_ticker = MagicMock()
        mock_ticker.info = {"currentPrice": 2600.0}

        def mock_yf_ticker(symbol):
            return mock_ticker

        with (
            patch(
                "modules.kotak_neo_auto_trader.shared_session_manager.get_shared_session_manager",
                return_value=mock_session_manager,
            ),
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_factory.BrokerFactory.create_broker",
                mock_broker_factory,
            ),
            patch("yfinance.Ticker", mock_yf_ticker),
        ):
            db_session = MagicMock()
            result = broker.get_broker_portfolio(db=db_session, current=user)

            # Should succeed after multiple re-auth attempts
            assert len(result.holdings) == 1

            # Verify multiple re-authentication attempts
            assert mock_session_manager.get_or_create_session.call_count >= 3

            # Verify connect() was called after second re-auth
            assert mock_broker.connect.called

    def test_session_sharing_across_api_calls(self, monkeypatch):
        """
        CRITICAL: Session must be shared across multiple API calls.

        This test ensures that the same session is reused across multiple
        API calls (portfolio and orders), demonstrating session sharing.
        """
        user = DummyUser(id=5)

        repo = DummySettingsRepo(object())
        monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

        def mock_decrypt(creds):
            return {"api_key": "key", "api_secret": "secret"}

        monkeypatch.setattr(broker, "decrypt_broker_credentials", mock_decrypt)

        def mock_create_temp_env(creds):
            return "/tmp/test.env"

        monkeypatch.setattr(broker, "create_temp_env_file", mock_create_temp_env)

        # Valid session shared across calls
        shared_auth = MagicMock()
        shared_auth.is_authenticated.return_value = True
        shared_client = MagicMock()
        shared_auth.get_client.return_value = shared_client
        shared_auth.is_session_valid.return_value = True

        mock_session_manager = MagicMock()
        # Same session returned for both calls
        mock_session_manager.get_or_create_session.return_value = shared_auth

        # Mock broker gateway
        mock_holding = Holding(
            symbol="RELIANCE.NS",
            exchange=Exchange.NSE,
            quantity=10,
            average_price=Money(Decimal("2500.00")),
            current_price=Money(Decimal("2600.00")),
            last_updated=datetime.now(),
        )

        mock_order = MagicMock()
        mock_order.order_id = "ORDER123"
        mock_order.symbol = "RELIANCE-EQ"
        mock_order.quantity = 10
        mock_order.price = Money(Decimal("2500.00"))
        mock_order.status = "PENDING"
        mock_order.order_type = "BUY"
        mock_order.timestamp = datetime.now()

        mock_broker = MagicMock()
        mock_broker.get_holdings.return_value = [mock_holding]
        mock_broker.get_account_limits.return_value = {
            "available_margin": {"cash": 100000.0},
        }
        mock_broker.get_all_orders.return_value = [mock_order]
        mock_broker._connected = True

        def mock_broker_factory(broker_type, auth_handler):
            return mock_broker

        # Mock yfinance
        mock_ticker = MagicMock()
        mock_ticker.info = {"currentPrice": 2600.0}

        def mock_yf_ticker(symbol):
            return mock_ticker

        with (
            patch(
                "modules.kotak_neo_auto_trader.shared_session_manager.get_shared_session_manager",
                return_value=mock_session_manager,
            ),
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_factory.BrokerFactory.create_broker",
                mock_broker_factory,
            ),
            patch("yfinance.Ticker", mock_yf_ticker),
        ):
            db_session = MagicMock()

            # First API call - portfolio
            portfolio_result = broker.get_broker_portfolio(db=db_session, current=user)
            assert len(portfolio_result.holdings) == 1

            # Second API call - orders (should use same session)
            orders_result = broker.get_broker_orders(db=db_session, current=user)
            assert len(orders_result) == 1

            # Verify same session was used for both calls
            # get_or_create_session should be called twice (once per endpoint)
            assert mock_session_manager.get_or_create_session.call_count == 2

            # Both calls should return the same auth object (session sharing)
            first_call_auth = mock_session_manager.get_or_create_session.call_args_list[0]
            second_call_auth = mock_session_manager.get_or_create_session.call_args_list[1]
            # Both should request the same user_id
            assert first_call_auth[0][0] == user.id
            assert second_call_auth[0][0] == user.id

    def test_reauth_failure_raises_503(self, monkeypatch):
        """
        CRITICAL: Re-authentication failure must raise 503 error.

        This test ensures that if re-authentication fails, the system
        raises a 503 error with an appropriate message.
        """
        user = DummyUser(id=6)

        repo = DummySettingsRepo(object())
        monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)

        def mock_decrypt(creds):
            return {"api_key": "key", "api_secret": "secret"}

        monkeypatch.setattr(broker, "decrypt_broker_credentials", mock_decrypt)

        def mock_create_temp_env(creds):
            return "/tmp/test.env"

        monkeypatch.setattr(broker, "create_temp_env_file", mock_create_temp_env)

        # Stale session
        stale_auth = MagicMock()
        stale_auth.is_authenticated.return_value = True
        stale_auth.get_client.return_value = None
        stale_auth.is_session_valid.return_value = True

        # Re-authentication fails (returns None or not authenticated)
        failed_auth = MagicMock()
        failed_auth.is_authenticated.return_value = False  # Re-auth failed

        mock_session_manager = MagicMock()
        mock_session_manager.get_or_create_session.side_effect = [
            stale_auth,
            failed_auth,
        ]

        mock_broker = MagicMock()

        def mock_broker_factory(broker_type, auth_handler):
            return mock_broker

        with (
            patch(
                "modules.kotak_neo_auto_trader.shared_session_manager.get_shared_session_manager",
                return_value=mock_session_manager,
            ),
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_factory.BrokerFactory.create_broker",
                mock_broker_factory,
            ),
        ):
            db_session = MagicMock()
            with pytest.raises(HTTPException) as exc:
                broker.get_broker_portfolio(db=db_session, current=user)

            assert exc.value.status_code == 503
            assert "re-authentication failed" in exc.value.detail.lower() or (
                "session expired" in exc.value.detail.lower()
            )

    def test_broker_orders_maps_executed_to_closed(self, monkeypatch):
        """Broker EXECUTED status should be normalized to closed for UI."""
        user = DummyUser(id=7)

        repo = DummySettingsRepo(object())
        monkeypatch.setattr(broker, "SettingsRepository", lambda db: repo)
        monkeypatch.setattr(
            broker,
            "decrypt_broker_credentials",
            lambda creds: {"api_key": "key", "api_secret": "secret"},
        )
        monkeypatch.setattr(broker, "create_temp_env_file", lambda creds: "/tmp/test.env")

        auth = MagicMock()
        auth.is_authenticated.return_value = True
        auth.get_client.return_value = MagicMock()
        auth.is_session_valid.return_value = True

        mock_session_manager = MagicMock()
        mock_session_manager.get_or_create_session.return_value = auth

        mock_order = MagicMock()
        mock_order.order_id = "ORDER_EXEC_1"
        mock_order.symbol = "AXISBANK-EQ"
        mock_order.transaction_type.value = "BUY"
        mock_order.quantity = 7
        mock_order.price = Money(Decimal("1295.20"))
        mock_order.status = "EXECUTED"
        mock_order.executed_price = Money(Decimal("1295.20"))
        mock_order.executed_quantity = 7
        mock_order.created_at = datetime.now()

        mock_broker = MagicMock()
        mock_broker.get_all_orders.return_value = [mock_order]
        mock_broker._connected = True

        with (
            patch(
                "modules.kotak_neo_auto_trader.shared_session_manager.get_shared_session_manager",
                return_value=mock_session_manager,
            ),
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_factory.BrokerFactory.create_broker",
                return_value=mock_broker,
            ),
        ):
            result = broker.get_broker_orders(db=MagicMock(), current=user)

        assert len(result) == 1
        assert result[0]["status"] == "closed"
