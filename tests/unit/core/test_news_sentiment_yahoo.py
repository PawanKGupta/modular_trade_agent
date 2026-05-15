"""Regression tests for Yahoo Finance news ingestion (``core.news_sentiment``).

Guarantees helpers used by ``tools/yfinance_news_smoke.py`` match sentiment semantics.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from core.news_sentiment import (
    analyze_news_sentiment,
    get_recent_news,
    parse_yfinance_news_timestamp,
    yfinance_news_raw_timestamp_and_title,
)


def test_yfinance_news_nested_content_iso_z_matches_smoke_semantics():
    raw = {"content": {"title": "  Headline ", "publishTime": "2026-05-11T03:52:44Z"}}
    ts_raw, title = yfinance_news_raw_timestamp_and_title(raw)
    assert title == "Headline"
    assert ts_raw == "2026-05-11T03:52:44Z"


def test_yfinance_news_root_priority_provider_publish_before_content_time():
    """First matching field wins (same precedence as prior inline loop)."""
    raw = {
        "providerPublishTime": "2026-05-09T09:30:00Z",
        "content": {"publishTime": "2099-01-01T00:00:00Z"},
    }
    ts_raw, _title = yfinance_news_raw_timestamp_and_title(raw)
    assert ts_raw == "2026-05-09T09:30:00Z"


def test_parse_iso_z_and_unix_ms_seconds():
    z = parse_yfinance_news_timestamp("2026-05-11T03:52:44Z")
    assert z == datetime(2026, 5, 11, 3, 52, 44)

    ms = parse_yfinance_news_timestamp(174_694_076_6000.0)
    assert ms is not None
    secs = parse_yfinance_news_timestamp(1746940766)
    assert secs is not None


def test_parse_bad_timestamp_returns_none():
    assert parse_yfinance_news_timestamp("not-a-date") is None


def test_get_recent_news_success_and_empty():
    stub = [{"content": {"title": "A", "publishTime": "2026-05-01T12:00:00Z"}}]
    fake = MagicMock(news=stub)
    with patch("core.news_sentiment.yf.Ticker", return_value=fake):
        assert get_recent_news("IOC.NS") == stub


def test_get_recent_news_exceptions_return_empty():
    with patch(
        "core.news_sentiment.yf.Ticker",
        side_effect=RuntimeError("network"),
    ):
        assert get_recent_news("IOC.NS") == []

    stub = MagicMock(news=None)
    with patch("core.news_sentiment.yf.Ticker", return_value=stub):
        assert get_recent_news("IOC.NS") == []


def test_analyze_news_sentiment_counts_nested_article_in_window(monkeypatch):
    monkeypatch.setattr("core.news_sentiment.NEWS_SENTIMENT_ENABLED", True)
    monkeypatch.setattr("core.news_sentiment.NEWS_SENTIMENT_CACHE_TTL_SEC", 0)
    monkeypatch.setattr("core.news_sentiment.NEWS_SENTIMENT_LOOKBACK_DAYS", 365)
    monkeypatch.setattr("core.news_sentiment.NEWS_SENTIMENT_BACKEND", "lexicon")

    stub = [
        {"content": {"title": "Surge beats expectations", "publishTime": "2026-05-08T09:00:18Z"}}
    ]
    with patch("core.news_sentiment.get_recent_news", return_value=stub):
        out = analyze_news_sentiment("IOC.NS", as_of_date="2026-05-09")

    assert out["used"] == 1
    assert out["total"] == 1
    assert out["articles"] == stub
