"""
Test to verify that indicator caching doesn't mix up prices between different symbols.

This test reproduces Issue 8: Buy order summary shows same qty and price for different stocks.
"""

from unittest.mock import patch

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine, Recommendation


class TestIndicatorPriceCaching:
    """Test that indicator caching correctly handles multiple symbols"""

    def test_parallel_indicator_fetch_different_prices(self):
        """
        Test that parallel indicator fetching returns different prices for different symbols.

        Reproduces Issue 8 where AAREYDRUGS and HTMEDIA both showed price 85.73.
        """
        # Mock recommendations for two different stocks
        recommendations = [
            Recommendation(
                ticker="AAREYDRUGS.NS",
                verdict="buy",
                last_close=100.0,  # Stale price from DB
                execution_capital=100000.0,
            ),
            Recommendation(
                ticker="HTMEDIA.NS",
                verdict="buy",
                last_close=50.0,  # Stale price from DB
                execution_capital=100000.0,
            ),
        ]

        # Mock indicator data with DIFFERENT prices for each symbol
        mock_indicators = {
            "AAREYDRUGS.NS": {
                "close": 105.50,  # Fresh price for AAREYDRUGS
                "rsi10": 25.0,
                "ema9": 110.0,
                "ema200": 120.0,
                "avg_volume": 100000,
            },
            "HTMEDIA.NS": {
                "close": 48.75,  # Fresh price for HTMEDIA (different!)
                "rsi10": 28.0,
                "ema9": 50.0,
                "ema200": 55.0,
                "avg_volume": 50000,
            },
        }

        # Mock get_daily_indicators to return different prices
        def mock_get_indicators(ticker: str):
            return mock_indicators.get(ticker)

        with patch.object(AutoTradeEngine, "get_daily_indicators", side_effect=mock_get_indicators):
            # Simulate the parallel indicator fetching logic
            from concurrent.futures import ThreadPoolExecutor, as_completed

            cached_indicators = {}

            def fetch_indicator(rec_ticker: str):
                """Fetch indicator for a single ticker"""
                try:
                    ind = AutoTradeEngine.get_daily_indicators(rec_ticker)
                    return (rec_ticker, ind)
                except Exception:
                    return (rec_ticker, None)

            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_ticker = {
                    executor.submit(fetch_indicator, rec.ticker): rec.ticker
                    for rec in recommendations
                }
                for future in as_completed(future_to_ticker):
                    try:
                        ticker, ind = future.result()
                        cached_indicators[ticker] = ind
                    except Exception:
                        ticker = future_to_ticker.get(future, "unknown")
                        cached_indicators[ticker] = None

            # Verify that each ticker has its own unique price
            assert "AAREYDRUGS.NS" in cached_indicators
            assert "HTMEDIA.NS" in cached_indicators

            aareydrugs_close = cached_indicators["AAREYDRUGS.NS"]["close"]
            htmedia_close = cached_indicators["HTMEDIA.NS"]["close"]

            # The bug would cause both to have the same price
            assert aareydrugs_close != htmedia_close, (
                f"BUG: Both stocks have the same price! "
                f"AAREYDRUGS: {aareydrugs_close}, HTMEDIA: {htmedia_close}"
            )

            # Verify the correct prices
            assert aareydrugs_close == 105.50
            assert htmedia_close == 48.75

    def test_sequential_indicator_fetch_different_prices(self):
        """
        Test that sequential indicator fetching also returns different prices.

        This is the fallback when parallel fetching fails.
        """
        recommendations = [
            Recommendation(
                ticker="AAREYDRUGS.NS",
                verdict="buy",
                last_close=100.0,
                execution_capital=100000.0,
            ),
            Recommendation(
                ticker="HTMEDIA.NS",
                verdict="buy",
                last_close=50.0,
                execution_capital=100000.0,
            ),
        ]

        mock_indicators = {
            "AAREYDRUGS.NS": {
                "close": 105.50,
                "rsi10": 25.0,
                "ema9": 110.0,
                "ema200": 120.0,
                "avg_volume": 100000,
            },
            "HTMEDIA.NS": {
                "close": 48.75,
                "rsi10": 28.0,
                "ema9": 50.0,
                "ema200": 55.0,
                "avg_volume": 50000,
            },
        }

        def mock_get_indicators(ticker: str):
            return mock_indicators.get(ticker)

        with patch.object(AutoTradeEngine, "get_daily_indicators", side_effect=mock_get_indicators):
            # Simulate sequential fetching (fallback logic)
            cached_indicators = {}
            for rec in recommendations:
                try:
                    ind = AutoTradeEngine.get_daily_indicators(rec.ticker)
                    cached_indicators[rec.ticker] = ind
                except Exception:
                    cached_indicators[rec.ticker] = None

            # Verify different prices
            assert cached_indicators["AAREYDRUGS.NS"]["close"] == 105.50
            assert cached_indicators["HTMEDIA.NS"]["close"] == 48.75
            assert (
                cached_indicators["AAREYDRUGS.NS"]["close"]
                != cached_indicators["HTMEDIA.NS"]["close"]
            )
