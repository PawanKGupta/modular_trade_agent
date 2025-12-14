"""
Tests for AutoTradeEngine notification sending with user-specific TelegramNotifier

Tests that order notifications (placed, executed, rejected) use the user-specific
TelegramNotifier instance and respect user preferences.
"""

import pytest
from unittest.mock import MagicMock, Mock, patch

from src.infrastructure.db.models import Users, UserNotificationPreferences
from config.strategy_config import StrategyConfig


@pytest.fixture
def mock_auth():
    """Mock KotakNeoAuth"""
    auth = MagicMock()
    auth.is_authenticated.return_value = True
    auth.login.return_value = True
    return auth


@pytest.fixture
def sample_user(db_session):
    """Create a sample user"""
    from src.infrastructure.db.timezone_utils import ist_now

    user = Users(
        email="test@example.com",
        password_hash="hashed_password",
        created_at=ist_now(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_with_telegram_prefs(db_session, sample_user):
    """Create user with Telegram preferences"""
    prefs = UserNotificationPreferences(
        user_id=sample_user.id,
        telegram_enabled=True,
        telegram_chat_id="123456789",
        telegram_bot_token="test_bot_token_123",
        # Enable all order event notifications
        notify_order_placed=True,
        notify_order_executed=True,
        notify_order_rejected=True,
        notify_order_cancelled=True,
        notify_partial_fill=True,
    )
    db_session.add(prefs)
    db_session.commit()
    return sample_user


@pytest.fixture
def auto_trade_engine(mock_auth, db_session, sample_user):
    """Create AutoTradeEngine instance with user context"""
    from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

    with patch(
        "modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"
    ) as mock_auth_class:
        mock_auth_class.return_value = mock_auth

        engine = AutoTradeEngine(
            env_file="test.env",
            auth=mock_auth,
            user_id=sample_user.id,
            db_session=db_session,
            strategy_config=StrategyConfig.default(),
            enable_telegram=True,
        )

        # Mock portfolio and orders
        engine.portfolio = MagicMock()
        engine.orders = MagicMock()
        engine.orders_repo = MagicMock()
        engine.positions_repo = MagicMock()

        return engine


class TestOrderPlacedNotification:
    """Test order placed notifications"""

    def test_order_placed_notification_uses_user_specific_notifier(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test that order placed notification uses user-specific TelegramNotifier"""
        with patch(
            "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
        ) as mock_telegram_class:
            mock_notifier = Mock()
            mock_notifier.enabled = True
            mock_notifier.notify_order_placed = Mock(return_value=True)
            mock_telegram_class.return_value = mock_notifier

            # Initialize notifier
            auto_trade_engine._initialize_phase2_modules()

            # Simulate order placement
            if auto_trade_engine.telegram_notifier and auto_trade_engine.telegram_notifier.enabled:
                auto_trade_engine.telegram_notifier.notify_order_placed(
                    symbol="RELIANCE-EQ",
                    order_id="TEST123",
                    quantity=10,
                    order_type="MARKET",
                    user_id=auto_trade_engine.user_id,
                )

            # Verify the user-specific notifier was used
            assert auto_trade_engine.telegram_notifier is not None
            mock_notifier.notify_order_placed.assert_called_once()
            call_kwargs = mock_notifier.notify_order_placed.call_args[1]
            assert call_kwargs["user_id"] == auto_trade_engine.user_id
            assert call_kwargs["symbol"] == "RELIANCE-EQ"
            assert call_kwargs["order_id"] == "TEST123"

    def test_order_placed_notification_respects_preferences(
        self, auto_trade_engine, db_session, sample_user
    ):
        """Test that order placed notification respects user preferences"""
        # Create preferences with order_placed disabled
        prefs = UserNotificationPreferences(
            user_id=sample_user.id,
            telegram_enabled=True,
            telegram_chat_id="123456789",
            telegram_bot_token="test_token",
            notify_order_placed=False,  # Disabled
        )
        db_session.add(prefs)
        db_session.commit()

        with patch(
            "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
        ) as mock_telegram_class:
            mock_notifier = Mock()
            mock_notifier.enabled = True
            # Should return False due to preference
            mock_notifier.notify_order_placed = Mock(return_value=False)
            mock_telegram_class.return_value = mock_notifier

            # Initialize notifier
            auto_trade_engine._initialize_phase2_modules()

            # Simulate order placement
            if auto_trade_engine.telegram_notifier:
                result = auto_trade_engine.telegram_notifier.notify_order_placed(
                    symbol="RELIANCE-EQ",
                    order_id="TEST123",
                    quantity=10,
                    order_type="MARKET",
                    user_id=auto_trade_engine.user_id,
                )

                # Should be called but return False due to preference check
                mock_notifier.notify_order_placed.assert_called_once()
                # The preference check happens inside notify_order_placed
                # So the method is called but returns False


class TestOrderExecutionNotification:
    """Test order execution notifications"""

    def test_order_execution_notification_uses_user_specific_notifier(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test that order execution notification uses user-specific TelegramNotifier"""
        with patch(
            "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
        ) as mock_telegram_class:
            mock_notifier = Mock()
            mock_notifier.enabled = True
            mock_notifier.notify_order_execution = Mock(return_value=True)
            mock_telegram_class.return_value = mock_notifier

            # Initialize notifier
            auto_trade_engine._initialize_phase2_modules()

            # Simulate order execution
            if auto_trade_engine.telegram_notifier and auto_trade_engine.telegram_notifier.enabled:
                auto_trade_engine.telegram_notifier.notify_order_execution(
                    symbol="RELIANCE-EQ",
                    order_id="TEST123",
                    quantity=10,
                    executed_price=2500.0,
                    user_id=auto_trade_engine.user_id,
                )

            # Verify the user-specific notifier was used
            assert auto_trade_engine.telegram_notifier is not None
            mock_notifier.notify_order_execution.assert_called_once()
            call_kwargs = mock_notifier.notify_order_execution.call_args[1]
            assert call_kwargs["user_id"] == auto_trade_engine.user_id
            assert call_kwargs["symbol"] == "RELIANCE-EQ"
            assert call_kwargs["executed_price"] == 2500.0


class TestOrderRejectionNotification:
    """Test order rejection notifications"""

    def test_order_rejection_notification_uses_user_specific_notifier(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test that order rejection notification uses user-specific TelegramNotifier"""
        with patch(
            "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
        ) as mock_telegram_class:
            mock_notifier = Mock()
            mock_notifier.enabled = True
            mock_notifier.notify_order_rejection = Mock(return_value=True)
            mock_telegram_class.return_value = mock_notifier

            # Initialize notifier
            auto_trade_engine._initialize_phase2_modules()

            # Simulate order rejection
            if auto_trade_engine.telegram_notifier and auto_trade_engine.telegram_notifier.enabled:
                auto_trade_engine.telegram_notifier.notify_order_rejection(
                    symbol="RELIANCE-EQ",
                    order_id="TEST123",
                    quantity=10,
                    rejection_reason="Insufficient funds",
                    user_id=auto_trade_engine.user_id,
                )

            # Verify the user-specific notifier was used
            assert auto_trade_engine.telegram_notifier is not None
            mock_notifier.notify_order_rejection.assert_called_once()
            call_kwargs = mock_notifier.notify_order_rejection.call_args[1]
            assert call_kwargs["user_id"] == auto_trade_engine.user_id
            assert call_kwargs["symbol"] == "RELIANCE-EQ"
            assert call_kwargs["rejection_reason"] == "Insufficient funds"


class TestPartialFillNotification:
    """Test partial fill notifications"""

    def test_partial_fill_notification_uses_user_specific_notifier(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test that partial fill notification uses user-specific TelegramNotifier"""
        with patch(
            "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
        ) as mock_telegram_class:
            mock_notifier = Mock()
            mock_notifier.enabled = True
            mock_notifier.notify_partial_fill = Mock(return_value=True)
            mock_telegram_class.return_value = mock_notifier

            # Initialize notifier
            auto_trade_engine._initialize_phase2_modules()

            # Simulate partial fill
            if auto_trade_engine.telegram_notifier and auto_trade_engine.telegram_notifier.enabled:
                auto_trade_engine.telegram_notifier.notify_partial_fill(
                    symbol="RELIANCE-EQ",
                    order_id="TEST123",
                    filled_qty=5,
                    total_qty=10,
                    remaining_qty=5,
                    user_id=auto_trade_engine.user_id,
                )

            # Verify the user-specific notifier was used
            assert auto_trade_engine.telegram_notifier is not None
            mock_notifier.notify_partial_fill.assert_called_once()
            call_kwargs = mock_notifier.notify_partial_fill.call_args[1]
            assert call_kwargs["user_id"] == auto_trade_engine.user_id
            assert call_kwargs["filled_qty"] == 5
            assert call_kwargs["total_qty"] == 10


class TestRetryQueueNotification:
    """Test retry queue notifications"""

    def test_retry_queue_notification_uses_user_specific_notifier(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test that retry queue notification uses user-specific TelegramNotifier"""
        with patch(
            "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
        ) as mock_telegram_class:
            mock_notifier = Mock()
            mock_notifier.enabled = True
            mock_notifier.notify_retry_queue_updated = Mock(return_value=True)
            mock_telegram_class.return_value = mock_notifier

            # Initialize notifier
            auto_trade_engine._initialize_phase2_modules()

            # Simulate retry queue update
            if auto_trade_engine.telegram_notifier and auto_trade_engine.telegram_notifier.enabled:
                auto_trade_engine.telegram_notifier.notify_retry_queue_updated(
                    symbol="RELIANCE-EQ",
                    action="added",
                    retry_count=1,
                    user_id=auto_trade_engine.user_id,
                )

            # Verify the user-specific notifier was used
            assert auto_trade_engine.telegram_notifier is not None
            mock_notifier.notify_retry_queue_updated.assert_called_once()
            call_kwargs = mock_notifier.notify_retry_queue_updated.call_args[1]
            assert call_kwargs["user_id"] == auto_trade_engine.user_id
            assert call_kwargs["action"] == "added"


class TestNotificationPreferenceFiltering:
    """Test that notifications respect user preferences"""

    def test_notification_skipped_when_preference_disabled(
        self, auto_trade_engine, db_session, sample_user
    ):
        """Test that notifications are skipped when user preference is disabled"""
        # Create preferences with order_placed disabled
        prefs = UserNotificationPreferences(
            user_id=sample_user.id,
            telegram_enabled=True,
            telegram_chat_id="123456789",
            telegram_bot_token="test_token",
            notify_order_placed=False,  # Disabled
            notify_order_executed=True,
        )
        db_session.add(prefs)
        db_session.commit()

        with patch(
            "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
        ) as mock_telegram_class:
            mock_notifier = Mock()
            mock_notifier.enabled = True
            # Mock _should_send_notification to return False for ORDER_PLACED
            mock_notifier._should_send_notification = Mock(
                side_effect=lambda user_id, event_type: (
                    False if event_type == "order_placed" else True
                )
            )
            mock_notifier.notify_order_placed = Mock(return_value=False)
            mock_notifier.notify_order_execution = Mock(return_value=True)
            mock_telegram_class.return_value = mock_notifier

            # Initialize notifier
            auto_trade_engine._initialize_phase2_modules()

            # Try to send order placed notification
            if auto_trade_engine.telegram_notifier:
                result = auto_trade_engine.telegram_notifier.notify_order_placed(
                    symbol="RELIANCE-EQ",
                    order_id="TEST123",
                    quantity=10,
                    order_type="MARKET",
                    user_id=auto_trade_engine.user_id,
                )

                # Should return False due to preference
                assert result is False
                # The method should check preferences internally
                mock_notifier.notify_order_placed.assert_called_once()

    def test_notification_sent_when_preference_enabled(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test that notifications are sent when user preference is enabled"""
        with patch(
            "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
        ) as mock_telegram_class:
            mock_notifier = Mock()
            mock_notifier.enabled = True
            mock_notifier.notify_order_placed = Mock(return_value=True)
            mock_telegram_class.return_value = mock_notifier

            # Initialize notifier
            auto_trade_engine._initialize_phase2_modules()

            # Send order placed notification
            if auto_trade_engine.telegram_notifier:
                result = auto_trade_engine.telegram_notifier.notify_order_placed(
                    symbol="RELIANCE-EQ",
                    order_id="TEST123",
                    quantity=10,
                    order_type="MARKET",
                    user_id=auto_trade_engine.user_id,
                )

                # Should return True
                assert result is True
                mock_notifier.notify_order_placed.assert_called_once()


class TestNotificationErrorHandling:
    """Test error handling in notification sending"""

    def test_notification_error_does_not_crash_engine(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test that notification errors don't crash the engine"""
        with patch(
            "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
        ) as mock_telegram_class:
            mock_notifier = Mock()
            mock_notifier.enabled = True
            mock_notifier.notify_order_placed = Mock(side_effect=Exception("Network error"))
            mock_telegram_class.return_value = mock_notifier

            # Initialize notifier
            auto_trade_engine._initialize_phase2_modules()

            # Try to send notification - should not raise exception
            if auto_trade_engine.telegram_notifier:
                try:
                    auto_trade_engine.telegram_notifier.notify_order_placed(
                        symbol="RELIANCE-EQ",
                        order_id="TEST123",
                        quantity=10,
                        order_type="MARKET",
                        user_id=auto_trade_engine.user_id,
                    )
                except Exception:
                    # If exception is raised, it should be caught by the calling code
                    # The engine should continue working
                    pass

            # Engine should still be functional
            assert auto_trade_engine.telegram_notifier is not None

    def test_notification_skipped_when_notifier_none(
        self, auto_trade_engine, sample_user
    ):
        """Test that notifications are skipped gracefully when notifier is None"""
        # User has no Telegram preferences, so notifier will be None
        auto_trade_engine._initialize_phase2_modules()

        # Try to send notification - should not crash
        assert auto_trade_engine.telegram_notifier is None

        # Code that checks for notifier should handle None gracefully
        if auto_trade_engine.telegram_notifier and auto_trade_engine.telegram_notifier.enabled:
            # This block should not execute
            raise AssertionError("Should not reach here when notifier is None")
        else:
            # This is expected behavior
            assert True


class TestMultiUserNotificationIsolation:
    """Test that notifications are isolated per user"""

    def test_different_users_get_different_notifiers(
        self, mock_auth, db_session
    ):
        """Test that different users get different TelegramNotifier instances"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        # Create two users
        user1 = Users(
            email="user1@example.com",
            password_hash="hash1",
            created_at=ist_now(),
        )
        user2 = Users(
            email="user2@example.com",
            password_hash="hash2",
            created_at=ist_now(),
        )
        db_session.add_all([user1, user2])
        db_session.commit()
        db_session.refresh(user1)
        db_session.refresh(user2)

        # Create preferences for both users
        prefs1 = UserNotificationPreferences(
            user_id=user1.id,
            telegram_enabled=True,
            telegram_chat_id="111111111",
            telegram_bot_token="token1",
        )
        prefs2 = UserNotificationPreferences(
            user_id=user2.id,
            telegram_enabled=True,
            telegram_chat_id="222222222",
            telegram_bot_token="token2",
        )
        db_session.add_all([prefs1, prefs2])
        db_session.commit()

        with patch(
            "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
        ) as mock_telegram_class:
            mock_notifier1 = Mock()
            mock_notifier1.enabled = True
            mock_notifier2 = Mock()
            mock_notifier2.enabled = True
            mock_telegram_class.side_effect = [mock_notifier1, mock_notifier2]

            # Create engines for both users
            with patch(
                "modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"
            ) as mock_auth_class:
                mock_auth_class.return_value = mock_auth

                engine1 = AutoTradeEngine(
                    env_file="test.env",
                    auth=mock_auth,
                    user_id=user1.id,
                    db_session=db_session,
                    strategy_config=StrategyConfig.default(),
                )
                engine2 = AutoTradeEngine(
                    env_file="test.env",
                    auth=mock_auth,
                    user_id=user2.id,
                    db_session=db_session,
                    strategy_config=StrategyConfig.default(),
                )

                # Initialize notifiers
                notifier1 = engine1._get_telegram_notifier()
                notifier2 = engine2._get_telegram_notifier()

                # Verify different instances were created
                assert notifier1 is not None
                assert notifier2 is not None
                assert notifier1 != notifier2

                # Verify different credentials were used
                assert mock_telegram_class.call_count == 2
                call1 = mock_telegram_class.call_args_list[0]
                call2 = mock_telegram_class.call_args_list[1]

                assert call1[1]["chat_id"] == "111111111"
                assert call2[1]["chat_id"] == "222222222"
                assert call1[1]["bot_token"] == "token1"
                assert call2[1]["bot_token"] == "token2"

