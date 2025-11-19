#!/usr/bin/env python3
# ruff: noqa: E402
"""
Unit tests for production scenarios.

Tests cover:
1. Service initialization
2. Concurrent tasks
3. Network failures
4. Broker API failures
5. Service restart
6. Long-running operations

Run with: pytest tests/unit/kotak/test_production_scenarios.py -v
"""

import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from sqlalchemy.orm import Session

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.auto_trade_engine import (
    AutoTradeEngine,
    OrderPlacementError,
    Recommendation,
)
from modules.kotak_neo_auto_trader.run_trading_service import TradingService


class TestServiceInitialization(unittest.TestCase):
    """Test service initialization scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.env_path = self.tmp_dir / "kotak_neo.env"
        self.env_path.write_text(
            "KOTAK_CONSUMER_KEY=test_key\n"
            "KOTAK_CONSUMER_SECRET=secret\n"
            "KOTAK_MOBILE_NUMBER=9999999999\n"
            "KOTAK_PASSWORD=pass123\n"
            "KOTAK_MPIN=123456\n"
            "KOTAK_ENVIRONMENT=sandbox\n",
            encoding="utf-8",
        )

    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @patch("modules.kotak_neo_auto_trader.run_trading_service.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.run_trading_service.AutoTradeEngine")
    def test_service_initialization_creates_single_auth(self, mock_engine_class, mock_auth_class):
        """Test that service creates single auth session"""
        mock_auth = Mock(spec=KotakNeoAuth)
        mock_auth.login.return_value = True
        mock_auth.is_logged_in = True
        mock_auth.client = Mock()
        mock_auth.get_client.return_value = mock_auth.client

        mock_auth_class.return_value = mock_auth

        mock_engine = Mock()
        mock_engine.login.return_value = True
        mock_engine.portfolio = Mock()
        mock_engine_class.return_value = mock_engine

        # Create a mock db_session
        mock_db = MagicMock(spec=Session)

        service = TradingService(
            user_id=1,
            db_session=mock_db,
            broker_creds=None,
            strategy_config=None,
            env_file=str(self.env_path),
        )
        result = service.initialize()

        # Should create auth once
        mock_auth_class.assert_called_once()
        # Should pass auth and config to engine
        mock_engine_class.assert_called_once()
        _, kwargs = mock_engine_class.call_args
        self.assertEqual(kwargs.get("env_file"), str(self.env_path))
        self.assertIs(kwargs.get("auth"), mock_auth)
        self.assertEqual(kwargs.get("user_id"), 1)
        self.assertIs(kwargs.get("db_session"), mock_db)
        self.assertIsNotNone(kwargs.get("strategy_config"))
        self.assertTrue(result)


class TestConcurrentTasks(unittest.TestCase):
    """Test concurrent task scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_auth = Mock(spec=KotakNeoAuth)
        self.mock_auth.is_authenticated.return_value = True
        self.mock_auth.login.return_value = True

        self.engine = AutoTradeEngine(auth=self.mock_auth)
        self.engine.orders = Mock()
        self.engine.portfolio = Mock()
        self.engine.portfolio.get_holdings.return_value = {"data": []}
        self.engine.portfolio.get_limits.return_value = {
            "data": {"day": {"used": 0, "available": 100000}}
        }

    def test_concurrent_place_new_entries(self):
        """Test concurrent place_new_entries calls"""
        results = []
        results_lock = threading.Lock()

        def place_orders():
            recs = []
            result = self.engine.place_new_entries(recs)
            with results_lock:
                results.append(result)

        # Create multiple threads
        threads = []
        for _ in range(3):
            t = threading.Thread(target=place_orders)
            threads.append(t)

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all threads
        for t in threads:
            t.join(timeout=5.0)

        # All should complete successfully
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r is not None for r in results))


class TestNetworkFailures(unittest.TestCase):
    """Test network failure scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_auth = Mock(spec=KotakNeoAuth)
        self.mock_auth.is_authenticated.return_value = True
        self.mock_auth.login.return_value = True

        self.engine = AutoTradeEngine(auth=self.mock_auth)
        self.engine.orders = Mock()
        self.engine.portfolio = Mock()
        self.engine.portfolio.get_limits.return_value = {
            "data": {"day": {"used": 0, "available": 100000}}
        }

    def test_network_failure_during_holdings_fetch(self):
        """Test network failure during holdings fetch"""
        # Mock to return None instead of raising exception (get_holdings handles None)
        self.engine.portfolio.get_holdings.return_value = None

        recs = []
        result = self.engine.place_new_entries(recs)

        # Should handle gracefully and return empty summary
        self.assertIsNotNone(result)
        self.assertEqual(result.get("placed", 0), 0)


class TestBrokerAPIFailures(unittest.TestCase):
    """Test broker API failure scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_auth = Mock(spec=KotakNeoAuth)
        self.mock_auth.is_authenticated.return_value = True
        self.mock_auth.login.return_value = True

        self.engine = AutoTradeEngine(auth=self.mock_auth)
        self.engine.orders = Mock()
        self.engine.portfolio = Mock()
        self.engine.portfolio.get_limits.return_value = {
            "data": {"day": {"used": 0, "available": 100000}}
        }

    def test_broker_api_error_response(self):
        """Test broker API error response"""
        self.engine.portfolio.get_holdings.return_value = {
            "code": "500",
            "message": "Internal server error",
        }

        recs = []
        result = self.engine.place_new_entries(recs)

        # Should handle gracefully
        self.assertIsNotNone(result)
        self.assertEqual(result.get("placed", 0), 0)

    def test_order_placement_error_stops_run(self):
        """Ensure broker/API order errors raise and halt further processing"""
        self.engine.portfolio.get_holdings.return_value = {"data": []}
        self.engine.current_symbols_in_portfolio = Mock(return_value=0)
        self.engine.portfolio_size = Mock(return_value=0)
        self.engine.has_holding = Mock(return_value=False)
        self.engine.has_active_buy_order = Mock(return_value=False)
        self.engine.parse_symbol_for_broker = Mock(return_value="TEST")
        self.engine.get_daily_indicators = Mock(
            return_value={
                "close": 100.0,
                "rsi10": 25.0,
                "ema9": 95.0,
                "ema200": 150.0,
                "avg_volume": 100000,
            }
        )
        self.engine.check_position_volume_ratio = Mock(return_value=True)
        self.engine.get_affordable_qty = Mock(return_value=1000)
        self.engine.get_available_cash = Mock(return_value=100000)
        self.engine._attempt_place_order = Mock(return_value=(False, None))

        recs = [
            Recommendation(
                ticker="TEST.NS", verdict="buy", last_close=100.0, execution_capital=10000.0
            )
        ]

        with self.assertRaises(OrderPlacementError):
            self.engine.place_new_entries(recs)

        self.engine._attempt_place_order.assert_called_once()


class TestServiceRestart(unittest.TestCase):
    """Test service restart scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.env_path = self.tmp_dir / "kotak_neo.env"
        self.env_path.write_text(
            "KOTAK_CONSUMER_KEY=test_key\n"
            "KOTAK_CONSUMER_SECRET=secret\n"
            "KOTAK_MOBILE_NUMBER=9999999999\n"
            "KOTAK_PASSWORD=pass123\n"
            "KOTAK_MPIN=123456\n"
            "KOTAK_ENVIRONMENT=sandbox\n",
            encoding="utf-8",
        )

    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @patch("modules.kotak_neo_auto_trader.run_trading_service.KotakNeoAuth")
    def test_service_restart_creates_fresh_session(self, mock_auth_class):
        """Test that service restart creates fresh auth session"""
        mock_auth = Mock(spec=KotakNeoAuth)
        mock_auth.login.return_value = True
        mock_auth.is_logged_in = True
        mock_auth.client = Mock()
        mock_auth.get_client.return_value = mock_auth.client

        mock_auth_class.return_value = mock_auth

        # First service instance
        # Create a mock db_session
        mock_db = MagicMock(spec=Session)

        service1 = TradingService(
            user_id=1,
            db_session=mock_db,
            broker_creds=None,
            strategy_config=None,
            env_file=str(self.env_path),
        )
        service1.initialize()

        first_call_count = mock_auth_class.call_count

        # Second service instance (restart)
        service2 = TradingService(
            user_id=1,
            db_session=mock_db,
            broker_creds=None,
            strategy_config=None,
            env_file=str(self.env_path),
        )
        service2.initialize()

        # Should create new auth session (call count should increase)
        self.assertGreater(mock_auth_class.call_count, first_call_count)
        self.assertEqual(mock_auth_class.call_count, 2)


class TestLongRunningOperations(unittest.TestCase):
    """Test long-running operation scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_auth = Mock(spec=KotakNeoAuth)
        self.mock_auth.is_authenticated.return_value = True
        self.mock_auth.login.return_value = True

        self.engine = AutoTradeEngine(auth=self.mock_auth)
        self.engine.orders = Mock()
        self.engine.portfolio = Mock()
        self.engine.portfolio.get_holdings.return_value = {"data": []}
        self.engine.portfolio.get_limits.return_value = {
            "data": {"day": {"used": 0, "available": 100000}}
        }

    def test_long_running_operation_with_session_expiry(self):
        """Test long-running operation that spans session expiry"""
        # Simulate session expiry during operation
        call_count = {"count": 0}

        def mock_get_holdings():
            call_count["count"] += 1
            if call_count["count"] == 1:
                return {"code": "900901", "message": "JWT token expired"}
            return {"data": []}

        self.engine.portfolio.get_holdings = mock_get_holdings
        self.mock_auth.force_relogin.return_value = True

        recs = []
        result = self.engine.place_new_entries(recs)

        # Should handle session expiry and retry
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
