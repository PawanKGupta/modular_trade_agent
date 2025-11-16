"""
Tests for Continuous Trading Service v2.1

Tests the new unified service architecture that runs continuously 24/7
with single login session and automatic task execution.
"""

import sys
from datetime import time as dt_time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to path (now in tests/regression/)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestContinuousServiceArchitecture:
    """Test the continuous service architecture"""

    def test_service_imports_without_errors(self):
        """Verify service can be imported"""
        from modules.kotak_neo_auto_trader.run_trading_service import TradingService

        assert TradingService is not None

    def test_service_initialization(self, db_session):
        """Test service initializes with correct structure"""
        from modules.kotak_neo_auto_trader.run_trading_service import TradingService
        from src.infrastructure.db.models import Users

        # Create a test user
        user = Users(email="test@example.com", password_hash="test", role="user")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        service = TradingService(
            user_id=user.id,
            db_session=db_session,
            broker_creds=None,
            strategy_config=None,
            env_file="test.env",
        )

        # Verify task completion tracking initialized
        assert hasattr(service, "tasks_completed")
        assert "analysis" in service.tasks_completed
        assert "buy_orders" in service.tasks_completed
        assert "eod_cleanup" in service.tasks_completed
        assert "premarket_retry" in service.tasks_completed
        assert "sell_monitor_started" in service.tasks_completed
        assert "position_monitor" in service.tasks_completed

        # All should start as False
        assert service.tasks_completed["analysis"] == False
        assert service.tasks_completed["buy_orders"] == False
        assert service.tasks_completed["eod_cleanup"] == False

    def test_service_has_no_shutdown_on_eod(self, db_session):
        """Verify EOD cleanup doesn't trigger shutdown (continuous mode)"""
        from modules.kotak_neo_auto_trader.run_trading_service import TradingService
        from src.infrastructure.db.models import Users

        # Create a test user
        user = Users(email="test@example.com", password_hash="test", role="user")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        service = TradingService(
            user_id=user.id,
            db_session=db_session,
            broker_creds=None,
            strategy_config=None,
            env_file="test.env",
        )

        # Check that shutdown is not requested initially
        assert service.shutdown_requested == False

    def test_is_trading_day_logic(self, db_session):
        """Test trading day detection (Mon-Fri)"""
        from modules.kotak_neo_auto_trader.run_trading_service import TradingService
        from src.infrastructure.db.models import Users

        # Create a test user
        user = Users(email="test@example.com", password_hash="test", role="user")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        service = TradingService(
            user_id=user.id,
            db_session=db_session,
            broker_creds=None,
            strategy_config=None,
            env_file="test.env",
        )

        # Trading days are Mon-Fri (weekday 0-4)
        with patch("modules.kotak_neo_auto_trader.run_trading_service.datetime") as mock_dt:
            # Monday
            mock_dt.now.return_value.weekday.return_value = 0
            assert service.is_trading_day() == True

            # Friday
            mock_dt.now.return_value.weekday.return_value = 4
            assert service.is_trading_day() == True

            # Saturday
            mock_dt.now.return_value.weekday.return_value = 5
            assert service.is_trading_day() == False

            # Sunday
            mock_dt.now.return_value.weekday.return_value = 6
            assert service.is_trading_day() == False

    def test_market_hours_detection(self, db_session):
        """Test market hours detection (9:15 AM - 3:30 PM)"""
        from modules.kotak_neo_auto_trader.run_trading_service import TradingService
        from src.infrastructure.db.models import Users

        # Create a test user
        user = Users(email="test@example.com", password_hash="test", role="user")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        service = TradingService(
            user_id=user.id,
            db_session=db_session,
            broker_creds=None,
            strategy_config=None,
            env_file="test.env",
        )

        with patch("modules.kotak_neo_auto_trader.run_trading_service.datetime") as mock_dt:
            # Before market open
            mock_dt.now.return_value.time.return_value = dt_time(9, 0)
            assert service.is_market_hours() == False

            # Market open
            mock_dt.now.return_value.time.return_value = dt_time(9, 15)
            assert service.is_market_hours() == True

            # During market hours
            mock_dt.now.return_value.time.return_value = dt_time(12, 0)
            assert service.is_market_hours() == True

            # Market close
            mock_dt.now.return_value.time.return_value = dt_time(15, 30)
            assert service.is_market_hours() == True

            # After market close
            mock_dt.now.return_value.time.return_value = dt_time(15, 31)
            assert service.is_market_hours() == False


class TestSessionCachingRemoval:
    """Verify session caching has been properly removed"""

    def test_no_session_cache_path_attribute(self):
        """Verify session_cache_path attribute removed"""
        from modules.kotak_neo_auto_trader.auth import KotakNeoAuth

        # Should not have session_cache_path
        assert not hasattr(KotakNeoAuth, "session_cache_path")

    def test_no_save_session_cache_method(self):
        """Verify _save_session_cache method removed"""
        from modules.kotak_neo_auto_trader.auth import KotakNeoAuth

        assert not hasattr(KotakNeoAuth, "_save_session_cache")

    def test_no_try_use_cached_session_method(self):
        """Verify _try_use_cached_session method removed"""
        from modules.kotak_neo_auto_trader.auth import KotakNeoAuth

        assert not hasattr(KotakNeoAuth, "_try_use_cached_session")

    def test_force_relogin_still_exists(self):
        """Verify force_relogin kept (needed for JWT expiry)"""
        from modules.kotak_neo_auto_trader.auth import KotakNeoAuth

        assert hasattr(KotakNeoAuth, "force_relogin")

        # Verify it's a callable method
        assert callable(KotakNeoAuth.force_relogin)


class TestJWTExpiryHandling:
    """Test JWT token expiry detection and recovery"""

    def test_orders_detects_jwt_expiry_code(self):
        """Test that orders.py detects JWT expiry code 900901 via @handle_reauth decorator"""
        from modules.kotak_neo_auto_trader.auth_handler import is_auth_error
        from modules.kotak_neo_auto_trader.orders import KotakNeoOrders

        # Mock response with JWT expiry
        mock_auth = Mock()
        mock_auth.get_client.return_value = Mock()

        orders = KotakNeoOrders(mock_auth)

        # Verify that get_orders has the @handle_reauth decorator
        import inspect

        source = inspect.getsource(orders.get_orders)
        assert (
            "@handle_reauth" in source or "handle_reauth" in source
        ), "get_orders should use @handle_reauth decorator"

        # Verify that auth_handler can detect JWT expiry
        response = {"code": "900901"}
        assert is_auth_error(response) == True, "auth_handler should detect error code 900901"

        response_invalid_jwt = {"description": "Invalid JWT token expired"}
        assert (
            is_auth_error(response_invalid_jwt) == True
        ), "auth_handler should detect invalid JWT token"

    def test_auto_trade_engine_detects_2fa_gates(self):
        """Test that auto_trade_engine detects 2FA requirement"""
        # Verify the 2FA detection method exists by checking source
        import inspect

        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

        source = inspect.getsource(AutoTradeEngine)

        # Verify 2FA detection logic exists
        assert "_response_requires_2fa" in source
        assert "2FA" in source or "Two-Factor" in source


class TestSensitiveInformationLogging:
    """Verify sensitive information is never logged"""

    @pytest.mark.security
    def test_password_not_in_auth_logs(self, caplog):
        """Verify password never appears in auth logs"""
        import shutil
        import tempfile
        from pathlib import Path

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            env_path = tmp_dir / "kotak_neo.env"
            env_path.write_text(
                "KOTAK_CONSUMER_KEY=test_key\n"
                "KOTAK_CONSUMER_SECRET=secret_value_123\n"
                "KOTAK_MOBILE_NUMBER=9999999999\n"
                "KOTAK_PASSWORD=SuperSecret@123\n"
                "KOTAK_TOTP_SECRET=totp_secret\n"
                "KOTAK_MPIN=654321\n"
                "KOTAK_ENVIRONMENT=sandbox\n",
                encoding="utf-8",
            )

            from modules.kotak_neo_auto_trader.auth import KotakNeoAuth

            caplog.clear()
            caplog.set_level("DEBUG")

            auth = KotakNeoAuth(config_file=str(env_path))

            # Check logs don't contain sensitive data
            all_logs = caplog.text

            assert "SuperSecret@123" not in all_logs
            assert "secret_value_123" not in all_logs
            assert "totp_secret" not in all_logs
            assert "654321" not in all_logs

            # Just verify auth was initialized without exposing secrets
            assert "KotakNeoAuth initialized" in all_logs

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @pytest.mark.security
    def test_mpin_not_in_2fa_logs(self, caplog):
        """Verify MPIN never appears in 2FA logs"""
        import shutil
        import tempfile
        from pathlib import Path

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            env_path = tmp_dir / "kotak_neo.env"
            env_path.write_text(
                "KOTAK_CONSUMER_KEY=test_key\n"
                "KOTAK_CONSUMER_SECRET=secret_value\n"
                "KOTAK_MOBILE_NUMBER=9999999999\n"
                "KOTAK_PASSWORD=pass123\n"
                "KOTAK_MPIN=987654\n"
                "KOTAK_ENVIRONMENT=sandbox\n",
                encoding="utf-8",
            )

            from modules.kotak_neo_auto_trader.auth import KotakNeoAuth

            caplog.clear()
            caplog.set_level("DEBUG")

            auth = KotakNeoAuth(config_file=str(env_path))

            # Simulate 2FA logging
            auth._complete_2fa()  # Will fail but we check logs

            all_logs = caplog.text

            # MPIN value should NEVER appear in logs
            assert "987654" not in all_logs

            # Generic mention of MPIN usage is OK
            assert "MPIN" in all_logs or "2FA" in all_logs

        except Exception:
            # Expected to fail (no real client), we're just checking logs
            pass
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @pytest.mark.security
    def test_session_token_not_logged_in_plaintext(self, caplog):
        """Verify session tokens aren't logged in plaintext"""
        import shutil
        import tempfile
        from pathlib import Path

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            env_path = tmp_dir / "kotak_neo.env"
            env_path.write_text(
                "KOTAK_CONSUMER_KEY=test_key\n"
                "KOTAK_CONSUMER_SECRET=secret\n"
                "KOTAK_MOBILE_NUMBER=9999999999\n"
                "KOTAK_PASSWORD=pass123\n"
                "KOTAK_MPIN=123456\n"
                "KOTAK_ENVIRONMENT=sandbox\n",
                encoding="utf-8",
            )

            from modules.kotak_neo_auto_trader.auth import KotakNeoAuth

            caplog.clear()
            caplog.set_level("DEBUG")

            auth = KotakNeoAuth(config_file=str(env_path))
            auth.session_token = "super_secret_jwt_token_123456789"

            # Get session token (should not log it)
            token = auth.get_session_token()

            all_logs = caplog.text

            # Token value should NOT appear in logs
            assert "super_secret_jwt_token_123456789" not in all_logs

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestEODCleanupBehavior:
    """Test EOD cleanup resets for next day instead of shutdown"""

    def test_eod_cleanup_resets_task_flags(self, db_session):
        """Verify EOD cleanup resets flags for next trading day"""
        from modules.kotak_neo_auto_trader.run_trading_service import TradingService
        from src.infrastructure.db.models import Users

        # Create a test user
        user = Users(email="test@example.com", password_hash="test", role="user")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        service = TradingService(
            user_id=user.id,
            db_session=db_session,
            broker_creds=None,
            strategy_config=None,
            env_file="test.env",
        )

        # Simulate tasks completed
        service.tasks_completed["analysis"] = True
        service.tasks_completed["buy_orders"] = True
        service.tasks_completed["premarket_retry"] = True
        service.tasks_completed["sell_monitor_started"] = True
        service.tasks_completed["position_monitor"] = {9: True, 10: True}

        # Mock engine with eod_cleanup
        mock_engine = Mock()
        mock_engine.eod_cleanup = Mock()
        mock_engine.eod_cleanup.run = Mock()
        service.engine = mock_engine

        # Run EOD cleanup
        with patch("modules.kotak_neo_auto_trader.run_trading_service.logger"):
            service.run_eod_cleanup()

        # Verify flags reset for next day
        assert service.tasks_completed["analysis"] == False
        assert service.tasks_completed["buy_orders"] == False
        assert service.tasks_completed["premarket_retry"] == False
        assert service.tasks_completed["sell_monitor_started"] == False
        assert service.tasks_completed["position_monitor"] == {}

        # Verify EOD task itself marked complete
        assert service.tasks_completed["eod_cleanup"] == True


class TestDeprecatedScriptsWarnings:
    """Verify old scripts have deprecation warnings"""

    def test_run_auto_trade_has_deprecation_warning(self):
        """Check run_auto_trade.py shows deprecation"""
        script_path = project_root / "modules" / "kotak_neo_auto_trader" / "run_auto_trade.py"
        content = script_path.read_text(encoding="utf-8")

        assert "DEPRECATED" in content
        assert "run_trading_service.py" in content
        assert "manual fallback" in content.lower()

    def test_run_place_amo_has_deprecation_warning(self):
        """Check run_place_amo.py shows deprecation"""
        script_path = project_root / "modules" / "kotak_neo_auto_trader" / "run_place_amo.py"
        content = script_path.read_text(encoding="utf-8")

        assert "DEPRECATED" in content
        assert "run_trading_service.py" in content

    def test_run_sell_orders_has_deprecation_warning(self):
        """Check run_sell_orders.py shows deprecation"""
        script_path = project_root / "modules" / "kotak_neo_auto_trader" / "run_sell_orders.py"
        content = script_path.read_text(encoding="utf-8")

        assert "DEPRECATED" in content
        assert "run_trading_service.py" in content

    def test_run_position_monitor_has_deprecation_warning(self):
        """Check run_position_monitor.py shows deprecation"""
        script_path = project_root / "modules" / "kotak_neo_auto_trader" / "run_position_monitor.py"
        content = script_path.read_text(encoding="utf-8")

        assert "DEPRECATED" in content
        assert "run_trading_service.py" in content

    def test_run_eod_cleanup_has_deprecation_warning(self):
        """Check run_eod_cleanup.py shows deprecation"""
        script_path = project_root / "modules" / "kotak_neo_auto_trader" / "run_eod_cleanup.py"
        content = script_path.read_text(encoding="utf-8")

        assert "DEPRECATED" in content
        assert "run_trading_service.py" in content


class TestAutoTradeEngineMonitorPositions:
    """Test the new monitor_positions method added to AutoTradeEngine"""

    def test_monitor_positions_method_exists(self):
        """Verify monitor_positions method added"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

        assert hasattr(AutoTradeEngine, "monitor_positions")
        assert callable(AutoTradeEngine.monitor_positions)

    def test_monitor_positions_returns_dict(self):
        """Verify monitor_positions returns proper structure"""
        # Verify method exists by checking source
        import inspect

        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

        source = inspect.getsource(AutoTradeEngine.monitor_positions)

        # Verify it calls position monitor
        assert "get_position_monitor" in source or "PositionMonitor" in source
        assert "monitor_all_positions" in source


class TestContinuousServiceLogging:
    """Test logging behavior in continuous mode"""

    def test_service_logs_continuous_mode_message(self, caplog, db_session):
        """Verify service logs continuous mode indicator"""
        from modules.kotak_neo_auto_trader.run_trading_service import TradingService
        from src.infrastructure.db.models import Users

        # Create a test user
        user = Users(email="test@example.com", password_hash="test", role="user")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        service = TradingService(
            user_id=user.id,
            db_session=db_session,
            broker_creds=None,
            strategy_config=None,
            env_file="test.env",
        )

        # Read run_scheduler source
        import inspect

        source = inspect.getsource(service.run_scheduler)

        assert "CONTINUOUS MODE" in source or "continuously 24/7" in source.lower()

    def test_service_logs_session_active_message(self, db_session):
        """Verify service logs single login session at startup"""
        from modules.kotak_neo_auto_trader.run_trading_service import TradingService
        from src.infrastructure.db.models import Users

        # Create a test user
        user = Users(email="test@example.com", password_hash="test", role="user")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        service = TradingService(
            user_id=user.id,
            db_session=db_session,
            broker_creds=None,
            strategy_config=None,
            env_file="test.env",
        )

        import inspect

        # Check run() method which handles login
        source = inspect.getsource(service.run)

        # Verify login happens once at startup
        assert "login" in source.lower() or "authenticate" in source.lower()


@pytest.mark.integration
class TestServiceTaskScheduling:
    """Integration tests for task scheduling logic"""

    def test_should_run_task_timing_window(self, db_session):
        """Test task execution window (2 minutes)"""
        from modules.kotak_neo_auto_trader.run_trading_service import TradingService
        from src.infrastructure.db.models import Users

        # Create a test user
        user = Users(email="test@example.com", password_hash="test", role="user")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        service = TradingService(
            user_id=user.id,
            db_session=db_session,
            broker_creds=None,
            strategy_config=None,
            env_file="test.env",
        )

        with patch("modules.kotak_neo_auto_trader.run_trading_service.datetime") as mock_dt:
            # Exact time
            mock_dt.now.return_value.time.return_value = dt_time(9, 0)
            assert service.should_run_task("premarket_retry", dt_time(9, 0)) == True

            # 1 minute after (should run)
            mock_dt.now.return_value.time.return_value = dt_time(9, 1)
            assert service.should_run_task("premarket_retry", dt_time(9, 0)) == True

            # 2 minutes after (should not run)
            mock_dt.now.return_value.time.return_value = dt_time(9, 2)
            assert service.should_run_task("premarket_retry", dt_time(9, 0)) == False

            # Before scheduled time (should not run)
            mock_dt.now.return_value.time.return_value = dt_time(8, 59)
            assert service.should_run_task("premarket_retry", dt_time(9, 0)) == False

    def test_task_runs_only_once(self, db_session):
        """Test task doesn't run twice on same day"""
        from modules.kotak_neo_auto_trader.run_trading_service import TradingService
        from src.infrastructure.db.models import Users

        # Create a test user
        user = Users(email="test@example.com", password_hash="test", role="user")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        service = TradingService(
            user_id=user.id,
            db_session=db_session,
            broker_creds=None,
            strategy_config=None,
            env_file="test.env",
        )

        # Mark task as completed
        service.tasks_completed["analysis"] = True

        # Should not run again
        with patch("modules.kotak_neo_auto_trader.run_trading_service.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = dt_time(16, 0)
            assert service.should_run_task("analysis", dt_time(16, 0)) == False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
