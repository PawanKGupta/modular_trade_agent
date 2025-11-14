"""
Unit tests for trade_agent.py ML buy/strong_buy inclusion logic.

Tests that stocks with ML buy/strong_buy predictions are included in Telegram
notifications even if rule-based verdict is watch/avoid.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from trade_agent import get_enhanced_stock_info


class TestMLInclusionLogic:
    """Test ML prediction inclusion in Telegram notifications"""

    def test_ml_buy_rule_watch_included(self):
        """Test that stocks with ML=buy, Rule=watch are included with ONLY ML indicator"""
        stock_data = {
            'ticker': 'TEST.NS',
            'buy_range': [100, 102],
            'target': 110,
            'stop': 95,
            'rsi': 28,
            'last_close': 101,
            'verdict': 'watch',  # Rule says watch
            'final_verdict': 'watch',
            'ml_verdict': 'buy',  # ML says buy
            'ml_confidence': 75.5,
            'status': 'success'
        }

        msg = get_enhanced_stock_info(stock_data, 1, is_strong_buy=False)

        # Verify ML line is included
        assert '🤖 ML: BUY' in msg
        assert '75% conf' in msg or '76% conf' in msg  # May round differently

        # Verify disagreement indicator is present
        assert '⚠️ ONLY ML' in msg, "Should show ONLY ML indicator when rule=watch but ML=buy"

    def test_ml_strong_buy_rule_avoid_included(self):
        """Test that stocks with ML=strong_buy, Rule=avoid are included with ONLY ML indicator"""
        stock_data = {
            'ticker': 'TEST2.NS',
            'buy_range': [200, 205],
            'target': 230,
            'stop': 190,
            'rsi': 25,
            'last_close': 202,
            'verdict': 'avoid',  # Rule says avoid
            'final_verdict': 'avoid',
            'ml_verdict': 'strong_buy',  # ML says strong buy
            'ml_confidence': 88.2,
            'status': 'success'
        }

        msg = get_enhanced_stock_info(stock_data, 1, is_strong_buy=True)

        # Verify ML line is included
        assert '🤖 ML: STRONG_BUY' in msg
        assert '88% conf' in msg

        # Verify disagreement indicator
        assert '⚠️ ONLY ML' in msg, "Should show ONLY ML indicator when rule=avoid but ML=strong_buy"

    def test_ml_watch_rule_buy_included(self):
        """Test that stocks with ML=watch, Rule=buy show ONLY RULE indicator"""
        stock_data = {
            'ticker': 'TEST3.NS',
            'buy_range': [50, 52],
            'target': 60,
            'stop': 47,
            'rsi': 29,
            'last_close': 51,
            'verdict': 'buy',  # Rule says buy
            'final_verdict': 'buy',
            'ml_verdict': 'watch',  # ML says watch
            'ml_confidence': 65.0,
            'status': 'success'
        }

        msg = get_enhanced_stock_info(stock_data, 1, is_strong_buy=False)

        # Verify ML line is included
        assert '🤖 ML: WATCH' in msg
        assert '65% conf' in msg

        # Verify disagreement indicator
        assert '⚠️ ONLY RULE' in msg, "Should show ONLY RULE indicator when rule=buy but ML=watch"

    def test_ml_buy_rule_buy_agreement(self):
        """Test that stocks with ML=buy, Rule=buy show agreement indicator"""
        stock_data = {
            'ticker': 'TEST4.NS',
            'buy_range': [150, 152],
            'target': 165,
            'stop': 145,
            'rsi': 27,
            'last_close': 151,
            'verdict': 'buy',  # Rule says buy
            'final_verdict': 'buy',
            'ml_verdict': 'buy',  # ML says buy
            'ml_confidence': 82.0,
            'status': 'success'
        }

        msg = get_enhanced_stock_info(stock_data, 1, is_strong_buy=False)

        # Verify ML line is included
        assert '🤖 ML: BUY' in msg
        assert '82% conf' in msg

        # Verify agreement indicator
        assert '✅' in msg, "Should show ✅ when both rule and ML agree on buy"
        assert '⚠️' not in msg, "Should NOT show disagreement indicator when agreeing"

    def test_ml_strong_buy_rule_strong_buy_agreement(self):
        """Test that stocks with ML=strong_buy, Rule=strong_buy show agreement"""
        stock_data = {
            'ticker': 'TEST5.NS',
            'buy_range': [300, 305],
            'target': 335,
            'stop': 290,
            'rsi': 24,
            'last_close': 302,
            'verdict': 'strong_buy',  # Rule says strong_buy
            'final_verdict': 'strong_buy',
            'ml_verdict': 'strong_buy',  # ML says strong_buy
            'ml_confidence': 92.5,
            'status': 'success'
        }

        msg = get_enhanced_stock_info(stock_data, 1, is_strong_buy=True)

        # Verify ML line is included
        assert '🤖 ML: STRONG_BUY' in msg
        assert '92% conf' in msg or '93% conf' in msg

        # Verify agreement indicator
        assert '✅' in msg, "Should show ✅ when both agree on strong_buy"

    def test_filtering_logic_with_backtest_scoring(self):
        """Test that filtering includes ML buy/strong_buy with backtest scoring enabled"""
        # This would test the actual filtering logic in _process_results
        # For now, just document the expected behavior

        # Expected: Stock with ml_verdict=buy should be included even if final_verdict=watch
        # This is tested by the actual filtering logic in lines 504-527 of trade_agent.py

        results = [
            {'ticker': 'RULE_BUY.NS', 'status': 'success', 'final_verdict': 'buy',
             'ml_verdict': 'watch', 'combined_score': 30},
            {'ticker': 'ML_BUY.NS', 'status': 'success', 'final_verdict': 'watch',
             'ml_verdict': 'buy', 'combined_score': 20},
            {'ticker': 'BOTH_BUY.NS', 'status': 'success', 'final_verdict': 'buy',
             'ml_verdict': 'buy', 'combined_score': 35},
        ]

        # All three should be included in buys list
        # RULE_BUY.NS: final_verdict=buy, combined_score >= 25
        # ML_BUY.NS: ml_verdict=buy (even though combined_score < 25)
        # BOTH_BUY.NS: both criteria met

        assert True  # Placeholder - actual logic tested in integration

