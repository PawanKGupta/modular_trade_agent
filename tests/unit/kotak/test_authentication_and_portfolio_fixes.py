#!/usr/bin/env python3
"""
REST-focused auth and portfolio tests.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio


class TestRestAuthentication(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.env_path = self.tmp_dir / "kotak_neo.env"
        self.env_path.write_text(
            "KOTAK_CONSUMER_KEY=test_key\n"
            "KOTAK_CONSUMER_SECRET=ucc123\n"
            "KOTAK_MOBILE_NUMBER=9999999999\n"
            "KOTAK_TOTP_SECRET=BASE32SECRET3232\n"
            "KOTAK_MPIN=123456\n"
            "KOTAK_ENVIRONMENT=sandbox\n",
            encoding="utf-8",
        )

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_login_uses_rest_flow(self):
        auth = KotakNeoAuth(config_file=str(self.env_path))
        with patch.object(auth, "_perform_rest_login", return_value=True) as mock_rest:
            self.assertTrue(auth.login())
            mock_rest.assert_called_once()

    def test_get_client_returns_rest_client(self):
        auth = KotakNeoAuth(config_file=str(self.env_path))
        auth.is_logged_in = True
        auth.base_url = "https://example.invalid"
        auth.session_token = "trade_token"
        auth.trade_sid = "trade_sid"
        dummy = object()
        with patch.object(auth, "get_rest_client", return_value=dummy):
            self.assertIs(auth.get_client(), dummy)


class TestPortfolioRestClientIntegration(unittest.TestCase):
    def test_portfolio_get_holdings_uses_rest_client(self):
        mock_auth = Mock(spec=KotakNeoAuth)
        mock_rest = Mock()
        mock_auth.get_rest_client.return_value = mock_rest
        mock_rest.get_holdings.return_value = {"data": [{"symbol": "TEST", "quantity": 1}]}

        portfolio = KotakNeoPortfolio(mock_auth)
        data = portfolio.get_holdings()

        self.assertEqual(data, {"data": [{"symbol": "TEST", "quantity": 1}]})
        mock_auth.get_rest_client.assert_called_once()
        mock_rest.get_holdings.assert_called_once()

    def test_portfolio_get_positions_and_limits(self):
        mock_auth = Mock(spec=KotakNeoAuth)
        mock_rest = Mock()
        mock_auth.get_rest_client.return_value = mock_rest
        mock_rest.get_positions.return_value = {"data": []}
        mock_rest.get_limits.return_value = {"stat": "Ok", "Net": "1000"}

        portfolio = KotakNeoPortfolio(mock_auth)
        self.assertEqual(portfolio.get_positions(), {"data": []})
        self.assertEqual(portfolio.get_limits(), {"stat": "Ok", "Net": "1000"})


if __name__ == "__main__":
    unittest.main()

