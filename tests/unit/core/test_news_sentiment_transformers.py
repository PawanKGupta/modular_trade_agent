"""Tests for CPU transformer headline sentiment helpers and analyze wiring."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

import core.news_sentiment as news_sentiment_mod
from core.news_sentiment_transformers import map_label_scores_to_float


class TestMapLabelScores:
    def test_binary_positive(self) -> None:
        s = map_label_scores_to_float(
            [
                {"label": "NEGATIVE", "score": 0.1},
                {"label": "POSITIVE", "score": 0.9},
            ]
        )
        assert s == pytest.approx(0.8)

    def test_binary_label_ids(self) -> None:
        s = map_label_scores_to_float(
            [
                {"label": "LABEL_0", "score": 0.25},
                {"label": "LABEL_1", "score": 0.75},
            ]
        )
        assert s == pytest.approx(0.5)

    def test_three_way_finbert_style(self) -> None:
        s = map_label_scores_to_float(
            [
                {"label": "negative", "score": 0.1},
                {"label": "neutral", "score": 0.1},
                {"label": "positive", "score": 0.8},
            ]
        )
        assert s == pytest.approx(0.7)

    def test_empty(self) -> None:
        assert map_label_scores_to_float([]) == 0.0


class TestAnalyzeNewsSentimentBackend:
    """``analyze_news_sentiment`` integration with mocked news and scorer."""

    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        news_sentiment_mod._cache.clear()
        yield
        news_sentiment_mod._cache.clear()

    def _one_article(self, title: str) -> dict:
        return {
            "title": title,
            "providerPublishTime": int(datetime.utcnow().timestamp()),
        }

    @patch("core.news_sentiment.get_recent_news")
    @patch("core.news_sentiment_transformers.score_headlines_cpu")
    def test_prefers_transformer_when_available(self, mock_score, mock_news, monkeypatch) -> None:
        mock_news.return_value = [self._one_article("Company earnings beat forecasts")]
        mock_score.return_value = [0.8]

        monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_BACKEND", "auto")
        monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_ENABLED", True)

        out = news_sentiment_mod.analyze_news_sentiment("TESTTICKER")
        assert out["scorer"] == "transformer"
        assert out["model"] == news_sentiment_mod.NEWS_SENTIMENT_TRANSFORMER_MODEL
        assert out["score"] == pytest.approx(0.8)
        mock_score.assert_called_once()

    @patch("core.news_sentiment.get_recent_news")
    @patch("core.news_sentiment_transformers.score_headlines_cpu")
    def test_falls_back_to_lexicon_when_transformer_returns_none(
        self, mock_score, mock_news, monkeypatch
    ) -> None:
        mock_news.return_value = [self._one_article("Stock surges on strong profit growth")]
        mock_score.return_value = None

        monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_BACKEND", "auto")
        monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_ENABLED", True)

        out = news_sentiment_mod.analyze_news_sentiment("TESTTICKER2")
        assert out["scorer"] == "lexicon"
        assert "model" not in out
        assert out["score"] > 0

    @patch("core.news_sentiment.get_recent_news")
    def test_lexicon_backend_skips_transformer(self, mock_news, monkeypatch) -> None:
        mock_news.return_value = [self._one_article("Market rally continues")]

        monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_BACKEND", "lexicon")
        monkeypatch.setattr(news_sentiment_mod, "NEWS_SENTIMENT_ENABLED", True)

        with patch("core.news_sentiment_transformers.score_headlines_cpu") as mock_tf:
            news_sentiment_mod.analyze_news_sentiment("TESTTICKER3")
            mock_tf.assert_not_called()
