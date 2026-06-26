"""
Unit tests for MLPriceService — focuses on predict_target unit conversion and fallbacks.
"""

# ruff: noqa: E402 -- project root on path before services imports

import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from services.ml_price_service import MLPriceService  # noqa: E402
from services.ml_training_metadata import PRICE_TARGET_FEATURE_COLUMNS  # noqa: E402


def _make_ohlcv(n: int = 25, close: float = 100.0) -> pd.DataFrame:
    """Minimal OHLCV dataframe for feature extraction."""
    closes = np.linspace(close * 0.95, close, n)
    return pd.DataFrame(
        {
            "open": closes * 0.995,
            "high": closes * 1.01,
            "low": closes * 0.99,
            "close": closes,
            "volume": np.ones(n) * 1_000_000,
        }
    )


def _stub_service(predicted_pct: float) -> MLPriceService:
    """MLPriceService with a mock model that returns `predicted_pct`."""
    svc = MLPriceService.__new__(MLPriceService)
    svc.target_model = MagicMock()
    svc.target_model.predict = MagicMock(return_value=np.array([predicted_pct]))
    svc.target_model_loaded = True
    svc.stop_loss_model = None
    svc.stop_loss_model_loaded = False
    svc.feature_cols = list(PRICE_TARGET_FEATURE_COLUMNS)
    return svc


class TestPredictTargetUnitConversion:
    """Model output is % — service must convert to ₹ price."""

    def test_predicted_pct_converts_to_price(self):
        """10% predicted ceiling on ₹100 → calibrated target ₹106 (capture 0.6)."""
        from services.ml_price_service import _TARGET_CAPTURE_FRACTION

        svc = _stub_service(predicted_pct=10.0)
        df = _make_ohlcv(close=100.0)
        target, confidence = svc.predict_target(
            current_price=100.0,
            indicators={"rsi": 28.0},
            timeframe_confirmation=None,
            df=df,
            rule_based_target=102.0,  # EMA9 target < calibrated ML → ML wins
        )
        expected = 100.0 * (1.0 + _TARGET_CAPTURE_FRACTION * 10.0 / 100.0)
        assert abs(target - expected) < 0.01, f"Expected ~{expected}, got {target}"

    def test_confidence_above_zero_point_five(self):
        svc = _stub_service(predicted_pct=6.0)
        df = _make_ohlcv(close=200.0)
        _, confidence = svc.predict_target(
            current_price=200.0,
            indicators={"rsi": 30.0},
            timeframe_confirmation=None,
            df=df,
            rule_based_target=204.0,
        )
        assert confidence > 0.5

    def test_confidence_capped_at_0_9(self):
        svc = _stub_service(predicted_pct=50.0)  # unrealistically large prediction
        df = _make_ohlcv(close=100.0)
        _, confidence = svc.predict_target(
            current_price=100.0,
            indicators={"rsi": 25.0},
            timeframe_confirmation=None,
            df=df,
            rule_based_target=101.0,
        )
        assert confidence <= 0.9


class TestPredictTargetEMA9Fallback:
    """When ML predicts less upside than EMA9, the rule-based target is used."""

    def test_returns_rule_based_when_ml_undershoots(self):
        """ML predicts 1% but EMA9 target is at 3% — return EMA9."""
        svc = _stub_service(predicted_pct=1.0)
        df = _make_ohlcv(close=100.0)
        target, confidence = svc.predict_target(
            current_price=100.0,
            indicators={"rsi": 28.0, "ema9": 103.0},
            timeframe_confirmation=None,
            df=df,
            rule_based_target=105.0,
        )
        assert abs(target - 103.0) < 0.01, f"Expected 103.0 (EMA9 floor fallback), got {target}"
        assert confidence == 0.5

    def test_returns_rule_based_when_model_not_loaded(self):
        svc = MLPriceService.__new__(MLPriceService)
        svc.target_model = None
        svc.target_model_loaded = False
        svc.stop_loss_model = None
        svc.stop_loss_model_loaded = False
        svc.feature_cols = []
        df = _make_ohlcv(close=500.0)
        target, confidence = svc.predict_target(
            current_price=500.0,
            indicators={"rsi": 30.0},
            timeframe_confirmation=None,
            df=df,
            rule_based_target=515.0,
        )
        assert target == 515.0
        assert confidence == 0.5

    def test_default_fallback_when_no_rule_based(self):
        """No rule_based_target → 10% default (current * 1.10)."""
        svc = MLPriceService.__new__(MLPriceService)
        svc.target_model = None
        svc.target_model_loaded = False
        svc.stop_loss_model = None
        svc.stop_loss_model_loaded = False
        svc.feature_cols = []
        df = _make_ohlcv(close=200.0)
        target, _ = svc.predict_target(
            current_price=200.0,
            indicators={},
            timeframe_confirmation=None,
            df=df,
            rule_based_target=None,
        )
        assert abs(target - 220.0) < 0.01


class TestExtractTargetFeatures:
    """_extract_target_features returns all expected keys."""

    def test_returns_all_feature_cols(self):
        svc = _stub_service(predicted_pct=5.0)
        df = _make_ohlcv(n=25, close=150.0)
        features = svc._extract_target_features(
            current_price=150.0,
            indicators={"rsi": 28.0, "ema9": 155.0},
            df=df,
        )
        for col in svc.feature_cols:
            assert col in features, f"Missing feature: {col}"

    def test_ema9_from_df_when_not_in_indicators(self):
        svc = _stub_service(predicted_pct=3.0)
        df = _make_ohlcv(n=25, close=100.0)
        features = svc._extract_target_features(
            current_price=100.0,
            indicators={"rsi": 30.0},  # no ema9 key
            df=df,
        )
        # ema9_distance_pct should still be computed (from df)
        assert "ema9_distance_pct" in features
        assert isinstance(features["ema9_distance_pct"], float)
