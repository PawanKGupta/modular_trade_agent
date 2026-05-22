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


def test_chartink_scraper_failures(monkeypatch):
    import src.infrastructure.web_scraping.chartink_scraper as mod

    monkeypatch.setattr(mod, "get_stock_list", lambda: "")
    s = ChartInkScraper()
    assert s.get_stocks() == []
    assert s.is_available() is False
