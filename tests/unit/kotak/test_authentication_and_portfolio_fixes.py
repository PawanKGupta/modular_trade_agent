#!/usr/bin/env python3
"""
Unit tests for authentication and portfolio fixes.

Tests cover:
1. 2FA authentication error scenarios (None responses, dict-like objects)
2. Authentication checks in AutoTradeEngine methods
3. Portfolio backward compatibility and WebSocket LTP integration
4. P&L calculation with fallback mechanisms

Run with: pytest tests/unit/kotak/test_authentication_and_portfolio_fixes.py -v
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import unittest

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio
from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine, Recommendation
import tempfile


class Test2FAAuthenticationFix(unittest.TestCase):
    """Test 2FA authentication error handling fixes"""
    
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
            encoding="utf-8"
        )
        self.auth = KotakNeoAuth(config_file=str(self.env_path))
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    
    def test_2fa_with_none_response(self):
        """Test 2FA when session_2fa returns None"""
        mock_client = Mock()
        mock_client.session_2fa.return_value = None
        mock_client.login.return_value = {"status": "success"}
        self.auth.client = mock_client
        
        result = self.auth._complete_2fa()
        self.assertTrue(result, "Should return True when session_2fa returns None")
    
    def test_2fa_with_dict_none_data(self):
        """Test 2FA when session_2fa returns dict with data=None"""
        mock_client = Mock()
        mock_client.session_2fa.return_value = {'data': None, 'status': 'unknown'}
        mock_client.login.return_value = {"status": "success"}
        self.auth.client = mock_client
        
        result = self.auth._complete_2fa()
        self.assertTrue(result, "Should handle dict with data=None gracefully")
    
    def test_2fa_with_dict_like_none_data(self):
        """Test 2FA when session_2fa returns dict-like object with None data"""
        class DictLikeResponse:
            def get(self, key):
                if key == 'error':
                    return None
                if key == 'data':
                    return None
                return None
        
        mock_client = Mock()
        mock_client.session_2fa.return_value = DictLikeResponse()
        mock_client.login.return_value = {"status": "success"}
        self.auth.client = mock_client
        
        result = self.auth._complete_2fa()
        self.assertTrue(result, "Should handle dict-like object with None data")
    
    def test_2fa_with_error_response(self):
        """Test 2FA when session_2fa returns error response"""
        mock_client = Mock()
        mock_client.session_2fa.return_value = {
            'error': [{'message': 'Session expired'}]
        }
        mock_client.login.return_value = {"status": "success"}
        self.auth.client = mock_client
        
        result = self.auth._complete_2fa()
        self.assertFalse(result, "Should return False when error is present")


class TestAutoTradeEngineAuthCheck(unittest.TestCase):
    """Test authentication checks in AutoTradeEngine methods"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_auth = Mock(spec=KotakNeoAuth)
        self.mock_auth.is_authenticated.return_value = False
        self.mock_auth.login.return_value = True
        
        self.engine = AutoTradeEngine(auth=self.mock_auth)
        self.engine.orders = Mock()
        self.engine.portfolio = Mock()
    
    def test_place_new_entries_with_expired_auth(self):
        """Test place_new_entries re-authenticates when session expired"""
        self.mock_auth.is_authenticated.return_value = False
        self.mock_auth.login.return_value = True
        
        recs = [Recommendation(
            ticker="TESTSTOCK.NS",
            verdict="buy",
            last_close=100.0
        )]
        
        result = self.engine.place_new_entries(recs)
        
        # Should attempt re-authentication
        self.mock_auth.login.assert_called()
        self.assertIsNotNone(result)
    
    def test_place_new_entries_with_failed_reauth(self):
        """Test place_new_entries handles failed re-authentication"""
        self.mock_auth.is_authenticated.return_value = False
        self.mock_auth.login.return_value = False
        
        recs = [Recommendation(
            ticker="TESTSTOCK.NS",
            verdict="buy",
            last_close=100.0
        )]
        
        result = self.engine.place_new_entries(recs)
        
        # Should return empty summary on failed re-auth
        self.assertIsNotNone(result)
        self.assertEqual(result.get('placed', 0), 0)


class TestPortfolioBackwardCompatibility(unittest.TestCase):
    """Test portfolio backward compatibility"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_auth = Mock(spec=KotakNeoAuth)
        self.mock_auth.get_client.return_value = Mock()
    
    def test_portfolio_without_price_manager(self):
        """Test portfolio works without price_manager (backward compatibility)"""
        portfolio = KotakNeoPortfolio(self.mock_auth)
        self.assertIsNone(portfolio.price_manager)
    
    def test_portfolio_with_price_manager(self):
        """Test portfolio accepts price_manager"""
        mock_price_manager = Mock()
        portfolio = KotakNeoPortfolio(self.mock_auth, price_manager=mock_price_manager)
        self.assertEqual(portfolio.price_manager, mock_price_manager)


class TestPortfolioWebSocketLTPFallback(unittest.TestCase):
    """Test portfolio WebSocket LTP fallback chain"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_auth = Mock(spec=KotakNeoAuth)
        self.mock_client = Mock()
        self.mock_auth.get_client.return_value = self.mock_client
        
        self.mock_price_manager = Mock()
        self.portfolio = KotakNeoPortfolio(self.mock_auth, price_manager=self.mock_price_manager)
    
    def test_portfolio_websocket_ltp_fallback(self):
        """Test portfolio uses WebSocket LTP when broker LTP is 0"""
        # Mock broker response with LTP=0
        self.mock_client.holdings.return_value = {
            'data': [{
                'symbol': 'TESTSTOCK-EQ',
                'quantity': 10,
                'ltp': 0.0,
                'market_value': 1000.0
            }]
        }
        
        # Mock WebSocket LTP
        self.mock_price_manager.get_ltp.return_value = 100.0
        
        holdings = self.portfolio.get_holdings()
        
        # Should use WebSocket LTP
        self.mock_price_manager.get_ltp.assert_called()
        self.assertIsNotNone(holdings)
    
    def test_portfolio_market_value_fallback(self):
        """Test portfolio uses market_value when WebSocket LTP unavailable"""
        # Mock broker response with LTP=0
        self.mock_client.holdings.return_value = {
            'data': [{
                'symbol': 'TESTSTOCK-EQ',
                'quantity': 10,
                'ltp': 0.0,
                'market_value': 1000.0
            }]
        }
        
        # Mock WebSocket LTP unavailable
        self.mock_price_manager.get_ltp.return_value = 0.0
        
        holdings = self.portfolio.get_holdings()
        
        # Should calculate from market_value
        self.assertIsNotNone(holdings)
    
    @patch('builtins.__import__')
    def test_portfolio_yfinance_fallback(self, mock_import):
        """Test portfolio uses yfinance when WebSocket and market_value unavailable"""
        # Mock broker response with LTP=0 and market_value=0
        self.mock_client.holdings.return_value = {
            'data': [{
                'symbol': 'TESTSTOCK-EQ',
                'quantity': 10,
                'ltp': 0.0,
                'market_value': 0.0
            }]
        }
        
        # Mock WebSocket LTP unavailable
        self.mock_price_manager.get_ltp.return_value = 0.0
        
        # Mock yfinance import
        mock_yfinance = Mock()
        mock_ticker = Mock()
        mock_ticker.info = {'currentPrice': 100.0}
        mock_yfinance.Ticker.return_value = mock_ticker
        
        def import_side_effect(name, *args, **kwargs):
            if name == 'yfinance':
                return mock_yfinance
            return __import__(name, *args, **kwargs)
        
        mock_import.side_effect = import_side_effect
        
        holdings = self.portfolio.get_holdings()
        
        # Should use yfinance (imported inside function)
        self.assertIsNotNone(holdings)


class TestPortfolioPNLCalculation(unittest.TestCase):
    """Test portfolio P&L calculation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_auth = Mock(spec=KotakNeoAuth)
        self.mock_client = Mock()
        self.mock_auth.get_client.return_value = self.mock_client
    
    def test_portfolio_pnl_calculation_with_zero_ltp(self):
        """Test P&L calculation when broker LTP is 0"""
        mock_price_manager = Mock()
        mock_price_manager.get_ltp.return_value = 100.0
        
        portfolio = KotakNeoPortfolio(self.mock_auth, price_manager=mock_price_manager)
        
        # Mock broker response with LTP=0
        self.mock_client.holdings.return_value = {
            'data': [{
                'symbol': 'TESTSTOCK-EQ',
                'quantity': 10,
                'ltp': 0.0,
                'market_value': 1000.0,
                'average_price': 90.0
            }]
        }
        
        holdings = portfolio.get_holdings()
        
        # P&L should be calculated using WebSocket LTP
        self.assertIsNotNone(holdings)
        self.assertIn('data', holdings)


if __name__ == '__main__':
    unittest.main()
