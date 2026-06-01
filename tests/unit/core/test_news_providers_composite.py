"""Tests for composite news merge and sentiment on combined headlines."""

from __future__ import annotations

from unittest.mock import patch

from core.news_providers import dedupe_key, fetch_composite_news, merge_articles, normalize_article
from core.news_sentiment import analyze_news_sentiment


def test_dedupe_key_strips_trailing_publisher():
    a = "Profit plunges 98% - Mint"
    b = "Profit plunges 98% - Economic Times"
    assert dedupe_key(a) == dedupe_key(b)


def test_merge_articles_dedupes_and_sorts_newest_first():
    older = normalize_article(
        "Old headline - Publisher",
        __import__("datetime").datetime(2026, 5, 1, tzinfo=__import__("datetime").timezone.utc),
        "google_rss",
    )
    newer = normalize_article(
        "Fresh headline - Other",
        __import__("datetime").datetime(2026, 5, 28, tzinfo=__import__("datetime").timezone.utc),
        "marketaux",
    )
    dupe = normalize_article(
        "Fresh headline - Duplicate source",
        __import__("datetime").datetime(2026, 5, 27, tzinfo=__import__("datetime").timezone.utc),
        "newsdata",
    )
    merged = merge_articles([older], [newer, dupe])
    assert len(merged) == 2
    assert merged[0]["title"].startswith("Fresh")


def test_enabled_sources_cheap_skips_paid(monkeypatch):
    monkeypatch.setenv("MARKETAUX_API_KEY", "dummy")
    monkeypatch.setenv("NEWSDATA_API_KEY", "dummy")
    from core.news_providers import enabled_sources

    cheap = enabled_sources("cheap")
    full = enabled_sources("full")
    assert "marketaux" not in cheap
    assert "newsdata" not in cheap
    assert "yfinance" in cheap
    assert "google_rss" in cheap
    assert "marketaux" in full
    assert "newsdata" in full


def test_resolve_news_profile_backtest_is_cheap(monkeypatch):
    monkeypatch.setenv("NEWS_BACKTEST_PROFILE", "cheap")
    monkeypatch.setenv("NEWS_LIVE_PROFILE", "full")
    from core.news_providers import resolve_news_profile

    assert resolve_news_profile(as_of_date="2024-01-15") == "cheap"
    assert resolve_news_profile(news_profile="full") == "full"
    assert resolve_news_profile() == "full"


def test_enabled_sources_excludes_finnhub(monkeypatch):
    monkeypatch.setenv("NEWS_SOURCES", "composite")
    monkeypatch.setenv("FINNHUB_API_KEY", "dummy-key")
    monkeypatch.setenv("MARKETAUX_API_KEY", "dummy")
    from core.news_providers import enabled_sources

    names = enabled_sources()
    assert "finnhub" not in names
    assert "marketaux" in names

    monkeypatch.setenv("NEWS_SOURCES", "yfinance,finnhub,google_rss")
    assert "finnhub" not in enabled_sources()


def test_fetch_composite_merges_provider_outputs(monkeypatch):
    monkeypatch.setenv("NEWS_SOURCES", "yfinance,google_rss")
    yf_article = {
        "title": "Yahoo only",
        "providerPublishTime": 1_700_000_000,
        "source": "yfinance",
    }
    rss_article = normalize_article(
        "Google unique headline",
        __import__("datetime").datetime(2026, 5, 20, tzinfo=__import__("datetime").timezone.utc),
        "google_rss",
    )
    with patch("core.news_providers.fetch_yfinance_articles", return_value=[yf_article]):
        with patch("core.news_providers.fetch_google_rss_articles", return_value=[rss_article]):
            merged = fetch_composite_news("TEST.NS")
    titles = {a.get("title") for a in merged}
    assert "Yahoo only" in titles
    assert "Google unique headline" in titles


def test_analyze_news_sentiment_passes_resolved_profile_to_fetch(monkeypatch):
    """Backtest as_of_date must request cheap sources even without ContextVar."""
    monkeypatch.setenv("NEWS_BACKTEST_PROFILE", "cheap")
    monkeypatch.setenv("NEWS_LIVE_PROFILE", "full")
    monkeypatch.setattr("core.news_sentiment.NEWS_SENTIMENT_ENABLED", True)
    monkeypatch.setattr("core.news_sentiment.NEWS_SENTIMENT_CACHE_TTL_SEC", 0)

    with patch("core.news_sentiment.get_recent_news", return_value=[]) as mock_get:
        analyze_news_sentiment("TEST.NS", as_of_date="2024-01-15")

    mock_get.assert_called_once_with("TEST.NS", profile="cheap")


def test_analyze_sentiment_on_merged_articles(monkeypatch):
    monkeypatch.setattr("core.news_sentiment.NEWS_SENTIMENT_ENABLED", True)
    monkeypatch.setattr("core.news_sentiment.NEWS_SENTIMENT_CACHE_TTL_SEC", 0)
    monkeypatch.setattr("core.news_sentiment.NEWS_SENTIMENT_LOOKBACK_DAYS", 365)
    monkeypatch.setattr("core.news_sentiment.NEWS_SENTIMENT_BACKEND", "lexicon")
    monkeypatch.setattr("core.news_sentiment.NEWS_SENTIMENT_MIN_ARTICLES", 2)

    articles = [
        normalize_article(
            "Company beats profit estimates with strong growth",
            __import__("datetime").datetime(2026, 5, 8, tzinfo=__import__("datetime").timezone.utc),
            "google_rss",
        ),
        normalize_article(
            "Shares surge on record earnings beat",
            __import__("datetime").datetime(2026, 5, 9, tzinfo=__import__("datetime").timezone.utc),
            "marketaux",
        ),
    ]
    with patch("core.news_sentiment.get_recent_news", return_value=articles):
        out = analyze_news_sentiment("TEST.NS", as_of_date="2026-05-10")

    assert out["used"] == 2
    assert out["total"] == 2
    assert out["label"] in ("positive", "neutral", "negative")
    assert out.get("sources")
