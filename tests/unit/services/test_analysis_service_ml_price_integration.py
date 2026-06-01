"""Tests for ML-driven target/stop overlay in AnalysisService."""

from unittest.mock import MagicMock

import pandas as pd
import pytest

from config.strategy_config import StrategyConfig
from services.analysis_service import AnalysisService


@pytest.fixture
def price_overlay_df_last():
    """Minimal OHLCV history for ML price feature extraction."""
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    df = pd.DataFrame(
        {
            "open": 100.0,
            "high": 102.0,
            "low": 98.0,
            "close": 100.0,
            "volume": 1_000_000,
        },
        index=dates,
    )
    last = df.iloc[-1].copy()
    last["ema_200"] = 105.0
    return df, last


def test_maybe_enrich_unchanged_when_no_ml_service(price_overlay_df_last):
    """Rule-based params are unchanged when no ML price service is attached."""
    config = StrategyConfig(ml_price_enabled=False)
    svc = AnalysisService(config=config)
    df, last = price_overlay_df_last
    tp = {"buy_range": (99.0, 101.0), "target": 110.0, "stop": 95.0}
    out, meta = svc._maybe_enrich_trading_params_with_ml_price(tp, "buy", df, last, {}, 25.0)
    assert out == tp
    assert meta["ml_price_target_applied"] is False


def test_maybe_enrich_sets_target_when_model_confidence_high(price_overlay_df_last):
    """Target is overridden when prediction confidence clears threshold."""
    config = StrategyConfig(ml_price_enabled=False, ml_confidence_threshold=0.5)
    svc = AnalysisService(config=config)
    mock_ml = MagicMock()
    mock_ml.target_model_loaded = True
    mock_ml.stop_loss_model_loaded = False
    mock_ml.predict_target.return_value = (312.52, 0.95)
    svc._ml_price_service = mock_ml

    df, last = price_overlay_df_last
    tp = {"buy_range": (99.0, 101.0), "target": 290.0, "stop": 250.0}
    out, meta = svc._maybe_enrich_trading_params_with_ml_price(
        tp, "buy", df, last, {"alignment_score": 7.0}, 25.0
    )

    assert out["target"] == 312.52
    assert out["stop"] == 250.0
    assert meta["ml_price_target_applied"] is True
    assert meta["ml_price_stop_applied"] is False
    mock_ml.predict_target.assert_called_once()


def test_maybe_enrich_keeps_rules_when_ml_confidence_low(price_overlay_df_last):
    mock_ml = MagicMock()
    mock_ml.target_model_loaded = True
    mock_ml.stop_loss_model_loaded = False
    mock_ml.predict_target.return_value = (312.52, 0.1)

    config = StrategyConfig(ml_price_enabled=False, ml_confidence_threshold=0.5)
    svc = AnalysisService(config=config)
    svc._ml_price_service = mock_ml

    df, last = price_overlay_df_last
    tp = {"buy_range": (99.0, 101.0), "target": 290.0, "stop": 250.0}
    out, meta = svc._maybe_enrich_trading_params_with_ml_price(tp, "buy", df, last, {}, 25.0)
    assert out["target"] == 290.0
    assert meta["ml_price_target_applied"] is False
