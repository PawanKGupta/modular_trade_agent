"""Aggregate outcome tests for ``analyze_news_sentiment`` (label, confidence, used).

Uses mocked ``score_headlines_cpu`` so defaults CI does not require torch/transformers.

Optional HF smoke test is gated by env ``RUN_HF_SENTIMENT_SMOKE=1`` (downloads model).

"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

import core.news_sentiment as news_sentiment_mod


@pytest.fixture(autouse=True)
def _clear_news_cache() -> None:
    news_sentiment_mod._cache.clear()
    yield
    news_sentiment_mod._cache.clear()


def _article(title: str) -> dict:
    """Flattened Yahoo-shaped item compatible with parsers (root-level time + title).

    ``as_of_date`` is parsed as start-of-day UTC; timestamps must satisfy
    ``start_dt <= dt <= end_dt`` (``end_dt`` is midnight of ``as_of`` day).
    """
    return {
        "title": title,
        # Before end-of-period midnight (same calendar day semantics as analyzer).
        "providerPublishTime": int(datetime(2026, 5, 9, 15, 0, 0, tzinfo=UTC).timestamp()),
    }


@patch("core.news_sentiment.get_recent_news")
@patch("core.news_sentiment_transformers.score_headlines_cpu")
def test_transformer_aggregate_positive_label_score_confidence_used(
    mock_score, mock_news, monkeypatch
) -> None:
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_ENABLED", True)
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_BACKEND", "transformer")
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_CACHE_TTL_SEC", 0)
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_LOOKBACK_DAYS", 365)
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_POS_THRESHOLD", 0.25)
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_NEG_THRESHOLD", -0.25)
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_MIN_ARTICLES", 2)

    mock_news.return_value = [
        _article("ignored title a"),
        _article("ignored title b"),
    ]
    mock_score.return_value = [0.9, 0.5]

    out = news_sentiment_mod.analyze_news_sentiment("X", as_of_date="2026-05-10")

    assert out["scorer"] == "transformer"
    assert out["used"] == 2
    assert out["total"] == 2
    assert out["score"] == pytest.approx(0.7)
    assert out["label"] == "positive"
    # confidence = used / max(MIN_ARTICLES, 5) = 2 / 5
    assert out["confidence"] == pytest.approx(0.4)
    assert len(out["articles"]) == 2
    assert out["model"] == news_sentiment_mod.NEWS_SENTIMENT_TRANSFORMER_MODEL


@patch("core.news_sentiment.get_recent_news")
@patch("core.news_sentiment_transformers.score_headlines_cpu")
def test_transformer_aggregate_negative_label(mock_score, mock_news, monkeypatch) -> None:
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_ENABLED", True)
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_BACKEND", "auto")
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_CACHE_TTL_SEC", 0)
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_LOOKBACK_DAYS", 365)
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_POS_THRESHOLD", 0.25)
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_NEG_THRESHOLD", -0.25)
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_MIN_ARTICLES", 2)

    mock_news.return_value = [_article("t1"), _article("t2")]
    mock_score.return_value = [-0.6, -0.4]

    out = news_sentiment_mod.analyze_news_sentiment("Y", as_of_date="2026-05-10")

    assert out["scorer"] == "transformer"
    assert out["label"] == "negative"
    assert out["score"] == pytest.approx(-0.5)
    assert out["confidence"] == pytest.approx(0.4)


@patch("core.news_sentiment.get_recent_news")
@patch("core.news_sentiment_transformers.score_headlines_cpu")
def test_transformer_aggregate_neutral_band(mock_score, mock_news, monkeypatch) -> None:
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_ENABLED", True)
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_BACKEND", "auto")
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_CACHE_TTL_SEC", 0)
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_LOOKBACK_DAYS", 365)
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_POS_THRESHOLD", 0.25)
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_NEG_THRESHOLD", -0.25)

    mock_news.return_value = [_article("x"), _article("y")]
    mock_score.return_value = [0.1, -0.1]

    out = news_sentiment_mod.analyze_news_sentiment("Z", as_of_date="2026-05-10")

    assert out["scorer"] == "transformer"
    assert out["label"] == "neutral"
    assert out["score"] == pytest.approx(0.0)


@patch("core.news_sentiment.get_recent_news")
def test_lexicon_aggregate_confidence_clamped_high(mock_news, monkeypatch) -> None:
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_ENABLED", True)
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_BACKEND", "lexicon")
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_CACHE_TTL_SEC", 0)
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_LOOKBACK_DAYS", 365)
    monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_MIN_ARTICLES", 2)

    mock_news.return_value = [
        _article("Stock surges on profit beat"),
        _article("Another rally and strong growth"),
        _article("Rally continues with gains"),
        _article("Market jump on upgrade"),
        _article("Surge in revenue tops estimates"),
        _article("Major rally and positive outlook"),
    ]

    out = news_sentiment_mod.analyze_news_sentiment("L", as_of_date="2026-05-10")

    assert out["scorer"] == "lexicon"
    assert out["used"] == 6
    assert out["confidence"] == pytest.approx(1.0)  # min(1, 6/5)


@pytest.mark.slow
def test_score_headlines_cpu_smoke_optional_download() -> None:
    """Run only with RUN_HF_SENTIMENT_SMOKE=1; needs network/HF hub on cold cache."""

    if os.getenv("RUN_HF_SENTIMENT_SMOKE") != "1":
        pytest.skip("Set RUN_HF_SENTIMENT_SMOKE=1 to run Hugging Face CPU smoke (may download).")

    pytest.importorskip("torch")
    pytest.importorskip("transformers")

    from core.news_sentiment_transformers import score_headlines_cpu

    model_id = "distilbert-base-uncased-finetuned-sst-2-english"
    titles = [
        "Company reports record quarterly profit and raises guidance.",
        "Regulators open fraud investigation into the firm.",
    ]
    scores = score_headlines_cpu(
        titles,
        model_id=model_id,
        batch_size=2,
        max_length=128,
    )
    assert scores is not None
    assert len(scores) == 2
    for s in scores:
        assert -1.0 <= s <= 1.0
