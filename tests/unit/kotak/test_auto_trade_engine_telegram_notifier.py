"""
Tests for AutoTradeEngine._get_telegram_notifier() method

Tests the user-specific TelegramNotifier initialization with comprehensive
edge case coverage.
"""

import pytest
from unittest.mock import MagicMock, Mock, patch
import os

from src.infrastructure.db.models import Users, UserNotificationPreferences


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
    )
    db_session.add(prefs)
    db_session.commit()
    return sample_user


@pytest.fixture
def auto_trade_engine(mock_auth, db_session, sample_user):
    """Create AutoTradeEngine instance with user context"""
    from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
    from config.strategy_config import StrategyConfig

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
        )

        # Mock portfolio and orders
        engine.portfolio = MagicMock()
        engine.orders = MagicMock()

        return engine


class TestGetTelegramNotifierSuccess:
    """Test successful TelegramNotifier creation"""

    def test_get_telegram_notifier_success_with_user_preferences(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test _get_telegram_notifier returns notifier when user has preferences"""
        with patch(
            "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
        ) as mock_telegram_class:
            mock_notifier = Mock()
            mock_notifier.enabled = True
            mock_telegram_class.return_value = mock_notifier

            notifier = auto_trade_engine._get_telegram_notifier()

            assert notifier is not None
            assert notifier == mock_notifier
            mock_telegram_class.assert_called_once_with(
                bot_token="test_bot_token_123",
                chat_id="123456789",
                enabled=True,
                db_session=auto_trade_engine.db,
            )

    def test_get_telegram_notifier_fallback_to_env_token(
        self, auto_trade_engine, db_session, sample_user
    ):
        """Test _get_telegram_notifier falls back to environment variable for bot token"""
        # Create preferences without bot_token
        prefs = UserNotificationPreferences(
            user_id=sample_user.id,
            telegram_enabled=True,
            telegram_chat_id="123456789",
            telegram_bot_token=None,  # No user token
        )
        db_session.add(prefs)
        db_session.commit()

        with (
            patch(
                "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
            ) as mock_telegram_class,
            patch(
                "modules.kotak_neo_auto_trader.auto_trade_engine.os.getenv",
                return_value="env_bot_token_456",
            ) as mock_getenv,
        ):
            mock_notifier = Mock()
            mock_notifier.enabled = True
            mock_telegram_class.return_value = mock_notifier

            notifier = auto_trade_engine._get_telegram_notifier()

            assert notifier is not None
            mock_getenv.assert_called_once_with("TELEGRAM_BOT_TOKEN")
            mock_telegram_class.assert_called_once_with(
                bot_token="env_bot_token_456",
                chat_id="123456789",
                enabled=True,
                db_session=auto_trade_engine.db,
            )

    def test_get_telegram_notifier_uses_user_bot_token_over_env(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test _get_telegram_notifier prefers user bot_token over environment variable"""
        with (
            patch(
                "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
            ) as mock_telegram_class,
            patch(
                "modules.kotak_neo_auto_trader.auto_trade_engine.os.getenv",
                return_value="env_token_should_not_be_used",
            ) as mock_getenv,
        ):
            mock_notifier = Mock()
            mock_notifier.enabled = True
            mock_telegram_class.return_value = mock_notifier

            notifier = auto_trade_engine._get_telegram_notifier()

            assert notifier is not None
            # Verify user token was used, not env token
            mock_telegram_class.assert_called_once_with(
                bot_token="test_bot_token_123",  # User token
                chat_id="123456789",
                enabled=True,
                db_session=auto_trade_engine.db,
            )
            # getenv should not be called when user has token
            mock_getenv.assert_not_called()


class TestGetTelegramNotifierFailureCases:
    """Test failure cases and edge cases"""

    def test_get_telegram_notifier_returns_none_when_telegram_disabled(
        self, auto_trade_engine, db_session, sample_user
    ):
        """Test _get_telegram_notifier returns None when Telegram is disabled"""
        prefs = UserNotificationPreferences(
            user_id=sample_user.id,
            telegram_enabled=False,  # Disabled
            telegram_chat_id="123456789",
            telegram_bot_token="test_token",
        )
        db_session.add(prefs)
        db_session.commit()

        notifier = auto_trade_engine._get_telegram_notifier()

        assert notifier is None

    def test_get_telegram_notifier_returns_none_when_no_bot_token(
        self, auto_trade_engine, db_session, sample_user
    ):
        """Test _get_telegram_notifier returns None when no bot token available"""
        prefs = UserNotificationPreferences(
            user_id=sample_user.id,
            telegram_enabled=True,
            telegram_chat_id="123456789",
            telegram_bot_token=None,  # No user token
        )
        db_session.add(prefs)
        db_session.commit()

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.os.getenv",
            return_value=None,
        ):  # No env token either
            notifier = auto_trade_engine._get_telegram_notifier()

            assert notifier is None

    def test_get_telegram_notifier_returns_none_when_no_chat_id(
        self, auto_trade_engine, db_session, sample_user
    ):
        """Test _get_telegram_notifier returns None when no chat ID"""
        prefs = UserNotificationPreferences(
            user_id=sample_user.id,
            telegram_enabled=True,
            telegram_chat_id=None,  # No chat ID
            telegram_bot_token="test_token",
        )
        db_session.add(prefs)
        db_session.commit()

        notifier = auto_trade_engine._get_telegram_notifier()

        assert notifier is None

    def test_get_telegram_notifier_returns_none_when_no_preferences(
        self, auto_trade_engine, sample_user
    ):
        """Test _get_telegram_notifier returns None when user has no preferences"""
        notifier = auto_trade_engine._get_telegram_notifier()

        assert notifier is None

    def test_get_telegram_notifier_handles_import_error(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test _get_telegram_notifier handles ImportError gracefully when TelegramNotifier import fails"""
        # Patch the import to raise ImportError when trying to import TelegramNotifier
        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.get_telegram_notifier"
        ) as mock_get_singleton:
            # Simulate ImportError by patching the import inside the method
            # We'll patch sys.modules to remove the module temporarily
            import sys
            original_module = sys.modules.get("modules.kotak_neo_auto_trader.telegram_notifier")
            
            # Remove the module to simulate import failure
            if "modules.kotak_neo_auto_trader.telegram_notifier" in sys.modules:
                del sys.modules["modules.kotak_neo_auto_trader.telegram_notifier"]
            
            try:
                # Mock the import to raise ImportError
                with patch(
                    "builtins.__import__",
                    side_effect=lambda name, *args, **kwargs: (
                        ImportError("Module not found")
                        if "telegram_notifier" in name
                        else __import__(name, *args, **kwargs)
                    ),
                ):
                    mock_singleton = Mock()
                    mock_get_singleton.return_value = mock_singleton

                    notifier = auto_trade_engine._get_telegram_notifier()

                    # Should fall back to singleton on ImportError
                    assert notifier == mock_singleton
            finally:
                # Restore the module
                if original_module:
                    sys.modules["modules.kotak_neo_auto_trader.telegram_notifier"] = original_module

    def test_get_telegram_notifier_handles_preference_service_import_error(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test _get_telegram_notifier handles NotificationPreferenceService ImportError"""
        with (
            patch(
                "services.notification_preference_service.NotificationPreferenceService",
                side_effect=ImportError("Service not available"),
            ),
            patch(
                "modules.kotak_neo_auto_trader.auto_trade_engine.get_telegram_notifier"
            ) as mock_get_singleton,
        ):
            mock_singleton = Mock()
            mock_get_singleton.return_value = mock_singleton

            notifier = auto_trade_engine._get_telegram_notifier()

            # Should fall back to singleton
            assert notifier == mock_singleton
            mock_get_singleton.assert_called_once_with(db_session=auto_trade_engine.db)

    def test_get_telegram_notifier_handles_exceptions_gracefully(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test _get_telegram_notifier handles exceptions and falls back to singleton"""
        with (
            patch(
                "services.notification_preference_service.NotificationPreferenceService"
            ) as mock_pref_service,
            patch(
                "modules.kotak_neo_auto_trader.auto_trade_engine.get_telegram_notifier"
            ) as mock_get_singleton,
        ):
            # Make get_preferences raise an exception
            mock_pref_service.return_value.get_preferences.side_effect = Exception(
                "Database error"
            )
            mock_singleton = Mock()
            mock_get_singleton.return_value = mock_singleton

            notifier = auto_trade_engine._get_telegram_notifier()

            # Should fall back to singleton on error
            assert notifier == mock_singleton
            mock_get_singleton.assert_called_once_with(db_session=auto_trade_engine.db)


class TestGetTelegramNotifierBackwardCompatibility:
    """Test backward compatibility scenarios"""

    def test_get_telegram_notifier_fallback_when_no_user_id(
        self, mock_auth, db_session
    ):
        """Test _get_telegram_notifier falls back to singleton when user_id is None"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
        from config.strategy_config import StrategyConfig

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"
        ) as mock_auth_class:
            mock_auth_class.return_value = mock_auth

            engine = AutoTradeEngine(
                env_file="test.env",
                auth=mock_auth,
                user_id=None,  # No user_id
                db_session=db_session,
                strategy_config=StrategyConfig.default(),
            )

            with patch(
                "modules.kotak_neo_auto_trader.auto_trade_engine.get_telegram_notifier"
            ) as mock_get_singleton:
                mock_singleton = Mock()
                mock_get_singleton.return_value = mock_singleton

                notifier = engine._get_telegram_notifier()

                # Should use singleton
                assert notifier == mock_singleton
                mock_get_singleton.assert_called_once_with(db_session=db_session)

    def test_get_telegram_notifier_fallback_when_no_db_session(
        self, mock_auth, sample_user
    ):
        """Test _get_telegram_notifier falls back to singleton when db_session is None"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
        from config.strategy_config import StrategyConfig

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"
        ) as mock_auth_class:
            mock_auth_class.return_value = mock_auth

            engine = AutoTradeEngine(
                env_file="test.env",
                auth=mock_auth,
                user_id=sample_user.id,
                db_session=None,  # No db_session
                strategy_config=StrategyConfig.default(),
            )

            with patch(
                "modules.kotak_neo_auto_trader.auto_trade_engine.get_telegram_notifier"
            ) as mock_get_singleton:
                mock_singleton = Mock()
                mock_get_singleton.return_value = mock_singleton

                notifier = engine._get_telegram_notifier()

                # Should use singleton
                assert notifier == mock_singleton
                mock_get_singleton.assert_called_once_with(db_session=None)

    def test_get_telegram_notifier_fallback_when_both_none(self, mock_auth):
        """Test _get_telegram_notifier falls back to singleton when both user_id and db are None"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
        from config.strategy_config import StrategyConfig

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"
        ) as mock_auth_class:
            mock_auth_class.return_value = mock_auth

            engine = AutoTradeEngine(
                env_file="test.env",
                auth=mock_auth,
                user_id=None,  # No user_id
                db_session=None,  # No db_session
                strategy_config=StrategyConfig.default(),
            )

            with patch(
                "modules.kotak_neo_auto_trader.auto_trade_engine.get_telegram_notifier"
            ) as mock_get_singleton:
                mock_singleton = Mock()
                mock_get_singleton.return_value = mock_singleton

                notifier = engine._get_telegram_notifier()

                # Should use singleton
                assert notifier == mock_singleton
                mock_get_singleton.assert_called_once_with(db_session=None)


class TestGetTelegramNotifierInitialization:
    """Test TelegramNotifier initialization in _initialize_phase2_modules"""

    def test_initialize_phase2_modules_creates_user_specific_notifier(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test _initialize_phase2_modules creates user-specific TelegramNotifier"""
        with patch(
            "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
        ) as mock_telegram_class:
            mock_notifier = Mock()
            mock_notifier.enabled = True
            mock_telegram_class.return_value = mock_notifier

            auto_trade_engine._initialize_phase2_modules()

            assert auto_trade_engine.telegram_notifier is not None
            assert auto_trade_engine.telegram_notifier == mock_notifier
            mock_telegram_class.assert_called_once_with(
                bot_token="test_bot_token_123",
                chat_id="123456789",
                enabled=True,
                db_session=auto_trade_engine.db,
            )

    def test_initialize_phase2_modules_handles_none_notifier(
        self, auto_trade_engine, sample_user
    ):
        """Test _initialize_phase2_modules handles None notifier gracefully"""
        # User has no preferences, so notifier will be None
        auto_trade_engine._initialize_phase2_modules()

        assert auto_trade_engine.telegram_notifier is None

    def test_initialize_phase2_modules_skips_when_telegram_disabled(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test _initialize_phase2_modules skips when _enable_telegram is False"""
        auto_trade_engine._enable_telegram = False

        auto_trade_engine._initialize_phase2_modules()

        assert auto_trade_engine.telegram_notifier is None


class TestGetTelegramNotifierEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_get_telegram_notifier_with_empty_strings(
        self, auto_trade_engine, db_session, sample_user
    ):
        """Test _get_telegram_notifier handles empty string credentials"""
        prefs = UserNotificationPreferences(
            user_id=sample_user.id,
            telegram_enabled=True,
            telegram_chat_id="",  # Empty string
            telegram_bot_token="",  # Empty string
        )
        db_session.add(prefs)
        db_session.commit()

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.os.getenv",
            return_value="",  # Empty env token
        ):
            notifier = auto_trade_engine._get_telegram_notifier()

            # Empty strings should be treated as missing
            assert notifier is None

    def test_get_telegram_notifier_with_whitespace_credentials(
        self, auto_trade_engine, db_session, sample_user
    ):
        """Test _get_telegram_notifier handles whitespace-only credentials"""
        prefs = UserNotificationPreferences(
            user_id=sample_user.id,
            telegram_enabled=True,
            telegram_chat_id="   ",  # Whitespace only
            telegram_bot_token="   ",  # Whitespace only
        )
        db_session.add(prefs)
        db_session.commit()

        notifier = auto_trade_engine._get_telegram_notifier()

        # Should still create notifier (whitespace is valid, but Telegram API will reject)
        # The notifier creation itself should succeed
        # Note: This tests the code path, actual Telegram API validation happens later
        assert notifier is not None

    def test_get_telegram_notifier_with_special_characters(
        self, auto_trade_engine, db_session, sample_user
    ):
        """Test _get_telegram_notifier handles special characters in credentials"""
        prefs = UserNotificationPreferences(
            user_id=sample_user.id,
            telegram_enabled=True,
            telegram_chat_id="-123456789",  # Negative chat ID (valid)
            telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",  # Valid format
        )
        db_session.add(prefs)
        db_session.commit()

        with patch(
            "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
        ) as mock_telegram_class:
            mock_notifier = Mock()
            mock_notifier.enabled = True
            mock_telegram_class.return_value = mock_notifier

            notifier = auto_trade_engine._get_telegram_notifier()

            assert notifier is not None
            mock_telegram_class.assert_called_once_with(
                bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                chat_id="-123456789",
                enabled=True,
                db_session=auto_trade_engine.db,
            )

    def test_get_telegram_notifier_concurrent_access(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test _get_telegram_notifier handles concurrent access (creates new instance each time)"""
        with patch(
            "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
        ) as mock_telegram_class:
            mock_notifier1 = Mock()
            mock_notifier1.enabled = True
            mock_notifier2 = Mock()
            mock_notifier2.enabled = True
            mock_telegram_class.side_effect = [mock_notifier1, mock_notifier2]

            # Call twice - should create new instances each time
            notifier1 = auto_trade_engine._get_telegram_notifier()
            notifier2 = auto_trade_engine._get_telegram_notifier()

            assert notifier1 is not None
            assert notifier2 is not None
            assert notifier1 != notifier2  # Different instances
            assert mock_telegram_class.call_count == 2

    def test_get_telegram_notifier_database_error(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test _get_telegram_notifier handles database errors gracefully"""
        with (
            patch(
                "services.notification_preference_service.NotificationPreferenceService"
            ) as mock_pref_service,
            patch(
                "modules.kotak_neo_auto_trader.auto_trade_engine.get_telegram_notifier"
            ) as mock_get_singleton,
        ):
            # Simulate database connection error
            mock_pref_service.side_effect = Exception("Database connection lost")
            mock_singleton = Mock()
            mock_get_singleton.return_value = mock_singleton

            notifier = auto_trade_engine._get_telegram_notifier()

            # Should fall back to singleton
            assert notifier == mock_singleton

    def test_get_telegram_notifier_preference_service_error(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test _get_telegram_notifier handles NotificationPreferenceService errors"""
        with (
            patch(
                "services.notification_preference_service.NotificationPreferenceService"
            ) as mock_pref_service,
            patch(
                "modules.kotak_neo_auto_trader.auto_trade_engine.get_telegram_notifier"
            ) as mock_get_singleton,
        ):
            # Simulate service initialization error
            mock_pref_service.side_effect = RuntimeError("Service initialization failed")
            mock_singleton = Mock()
            mock_get_singleton.return_value = mock_singleton

            notifier = auto_trade_engine._get_telegram_notifier()

            # Should fall back to singleton
            assert notifier == mock_singleton

    def test_get_telegram_notifier_telegram_notifier_creation_error(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test _get_telegram_notifier handles TelegramNotifier creation errors"""
        with (
            patch(
                "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
            ) as mock_telegram_class,
            patch(
                "modules.kotak_neo_auto_trader.auto_trade_engine.get_telegram_notifier"
            ) as mock_get_singleton,
        ):
            # Simulate TelegramNotifier creation error
            mock_telegram_class.side_effect = ValueError("Invalid credentials")
            mock_singleton = Mock()
            mock_get_singleton.return_value = mock_singleton

            notifier = auto_trade_engine._get_telegram_notifier()

            # Should fall back to singleton
            assert notifier == mock_singleton


class TestGetTelegramNotifierIntegration:
    """Integration tests with actual notification sending"""

    def test_notifier_used_in_order_placed_notification(
        self, auto_trade_engine, user_with_telegram_prefs
    ):
        """Test that user-specific notifier is used for order placed notifications"""
        with patch(
            "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
        ) as mock_telegram_class:
            mock_notifier = Mock()
            mock_notifier.enabled = True
            mock_notifier.notify_order_placed = Mock(return_value=True)
            mock_telegram_class.return_value = mock_notifier

            # Initialize notifier
            auto_trade_engine._initialize_phase2_modules()

            # Simulate order placement notification
            if auto_trade_engine.telegram_notifier and auto_trade_engine.telegram_notifier.enabled:
                auto_trade_engine.telegram_notifier.notify_order_placed(
                    symbol="RELIANCE-EQ",
                    order_id="TEST123",
                    quantity=10,
                    order_type="MARKET",
                    user_id=auto_trade_engine.user_id,
                )

            # Verify the user-specific notifier was used
            mock_notifier.notify_order_placed.assert_called_once()
            call_kwargs = mock_notifier.notify_order_placed.call_args[1]
            assert call_kwargs["user_id"] == auto_trade_engine.user_id

    def test_notifier_respects_user_preferences(
        self, auto_trade_engine, db_session, sample_user
    ):
        """Test that notifier respects user notification preferences"""
        # Create preferences with Telegram disabled
        prefs = UserNotificationPreferences(
            user_id=sample_user.id,
            telegram_enabled=False,  # Disabled
            telegram_chat_id="123456789",
            telegram_bot_token="test_token",
        )
        db_session.add(prefs)
        db_session.commit()

        # Initialize notifier
        auto_trade_engine._initialize_phase2_modules()

        # Notifier should be None when Telegram is disabled
        assert auto_trade_engine.telegram_notifier is None

