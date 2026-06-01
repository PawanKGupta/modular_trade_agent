"""News sentiment downgrade rules: only strong, well-supported negatives."""

from __future__ import annotations

import pytest

import services.verdict_service as verdict_service_module
from config.strategy_config import StrategyConfig
from services.verdict_service import VerdictService


def _strong_buy_inputs(config: StrategyConfig):
    """Inputs that yield strong_buy before news adjustment (above EMA200, RSI oversold)."""
    return {
        "signals": ["excellent_uptrend_dip"],
        "rsi_value": 25.0,
        "is_above_ema200": True,
        "vol_ok": True,
        "vol_strong": True,
        "fundamental_ok": True,
        "timeframe_confirmation": {"alignment_score": 10.0},
        "chart_quality_passed": True,
        "fundamental_assessment": None,
    }


@pytest.fixture
def config_base() -> StrategyConfig:
    return StrategyConfig.default()


@pytest.fixture
def svc(config_base: StrategyConfig) -> VerdictService:
    return VerdictService(config_base)


class TestNewsStrongNegativeDowngrade:
    """Downgrade requires score env threshold, confidence floor, and min articles."""

    def test_weak_negative_does_not_downgrade(self, svc: VerdictService) -> None:
        base = _strong_buy_inputs(svc.config)
        verdict, jst = svc.determine_verdict(
            **base,
            news_sentiment={
                "enabled": True,
                "score": -0.35,
                "used": 3,
                "confidence": 0.6,
            },
            indicators=None,
            fundamentals=None,
            df=None,
        )
        assert verdict == "strong_buy"
        assert "news_negative" not in jst

    def test_strong_negative_downgrades(self, svc: VerdictService) -> None:
        base = _strong_buy_inputs(svc.config)
        verdict, jst = svc.determine_verdict(
            **base,
            news_sentiment={
                "enabled": True,
                "score": -0.65,
                "used": 3,
                "confidence": 0.6,
            },
            indicators=None,
            fundamentals=None,
            df=None,
        )
        assert verdict == "watch"
        assert "news_negative" in jst

    def test_not_enough_articles_skips_downgrade(self, svc: VerdictService) -> None:
        base = _strong_buy_inputs(svc.config)
        verdict, jst = svc.determine_verdict(
            **base,
            news_sentiment={
                "enabled": True,
                "score": -0.9,
                "used": 1,
                "confidence": 0.2,
            },
            indicators=None,
            fundamentals=None,
            df=None,
        )
        assert verdict == "strong_buy"
        assert "news_negative" not in jst

    def test_low_confidence_skips_downgrade(self, svc: VerdictService, monkeypatch) -> None:
        monkeypatch.setattr(
            verdict_service_module,
            "NEWS_SENTIMENT_DOWNGRADE_MIN_CONFIDENCE",
            0.5,
        )
        base = _strong_buy_inputs(svc.config)
        verdict, jst = svc.determine_verdict(
            **base,
            news_sentiment={
                "enabled": True,
                "score": -0.7,
                "used": 3,
                "confidence": 0.4,
            },
            indicators=None,
            fundamentals=None,
            df=None,
        )
        assert verdict == "strong_buy"
        assert "news_negative" not in jst
