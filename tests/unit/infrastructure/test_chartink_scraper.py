import types

from src.infrastructure.web_scraping.chartink_scraper import ChartInkScraper


def test_chartink_scraper_parses_stocks(monkeypatch):
    import src.infrastructure.web_scraping.chartink_scraper as mod

    monkeypatch.setattr(mod, 'get_stock_list', lambda: 'reliance, tcs , infy')

    s = ChartInkScraper()
    lst = s.get_stocks()
    assert lst == ['RELIANCE', 'TCS', 'INFY']
    assert s.get_stocks_with_suffix('.NS') == ['RELIANCE.NS', 'TCS.NS', 'INFY.NS']


def test_chartink_scraper_failures(monkeypatch):
    import src.infrastructure.web_scraping.chartink_scraper as mod

    monkeypatch.setattr(mod, 'get_stock_list', lambda: '')
    s = ChartInkScraper()
    assert s.get_stocks() == []
    assert s.is_available() is False
