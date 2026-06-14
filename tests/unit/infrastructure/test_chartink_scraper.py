from unittest.mock import patch

from src.infrastructure.brokers.tradable_equity_resolver import (
    build_scrip_master_from_instruments,
)
from src.infrastructure.web_scraping.chartink_scraper import ChartInkScraper


def test_chartink_scraper_parses_stocks(monkeypatch):
    import src.infrastructure.web_scraping.chartink_scraper as mod

    monkeypatch.setattr(mod, "get_stock_list", lambda: "reliance, tcs , infy")

    s = ChartInkScraper()
    lst = s.get_stocks()
    assert lst == ["RELIANCE", "TCS", "INFY"]
    assert s.get_stocks_with_suffix(".NS") == ["RELIANCE.NS", "TCS.NS", "INFY.NS"]


def test_chartink_scraper_excludes_bees_etfs(monkeypatch):
    import src.infrastructure.web_scraping.chartink_scraper as mod

    monkeypatch.setattr(mod, "get_stock_list", lambda: "LTGILTBEES, RELIANCE, NIFTYBEES")

    s = ChartInkScraper()
    assert s.get_stocks() == ["RELIANCE"]
    assert s.get_stocks_with_suffix(".NS") == ["RELIANCE.NS"]


def test_chartink_scraper_excludes_bharat_bond(monkeypatch):
    import src.infrastructure.web_scraping.chartink_scraper as mod

    monkeypatch.setattr(
        mod,
        "get_stock_list",
        lambda: "BHARATBOND-APR31, BHARATBOND-APR30, POWERGRID, KSB",
    )

    s = ChartInkScraper()
    assert s.get_stocks() == ["POWERGRID", "KSB"]
    assert s.get_stocks_with_suffix(".NS") == ["POWERGRID.NS", "KSB.NS"]


def test_chartink_scraper_uses_resolver_when_scrip_cache_available(monkeypatch):
    import src.infrastructure.web_scraping.chartink_scraper as mod

    monkeypatch.setattr(
        mod,
        "get_stock_list",
        lambda: "GALLANTT, SILVERAG, SALSTEEL, RELIANCE",
    )
    sm = build_scrip_master_from_instruments(
        [
            {"pTrdSymbol": "GALLANTT-EQ", "pISIN": "INE297H01019"},
            {"pTrdSymbol": "SILVERAG-EQ", "pISIN": "INF769K01KG6"},
            {"pTrdSymbol": "SALSTEEL-BE", "pISIN": "INE999A01099"},
            {"pTrdSymbol": "RELIANCE-EQ", "pISIN": "INE002A01018"},
        ]
    )
    with patch(
        "src.infrastructure.web_scraping.screener_symbol_filters.load_cached_scrip_master",
        return_value=sm,
    ):
        s = ChartInkScraper()
        assert s.get_stocks() == ["GALLANTT", "RELIANCE"]
        assert s.get_stocks_with_suffix(".NS") == ["GALLANTT.NS", "RELIANCE.NS"]


def test_chartink_scraper_failures(monkeypatch):
    import src.infrastructure.web_scraping.chartink_scraper as mod

    monkeypatch.setattr(mod, "get_stock_list", lambda: "")
    s = ChartInkScraper()
    assert s.get_stocks() == []
    assert s.is_available() is False
