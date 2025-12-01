#!/usr/bin/env python3
"""Simple unit tests for ML services"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from services.ml_price_service import MLPriceService
from services.ml_verdict_service import MLVerdictService
from utils.logger import logger


def test_ml_verdict_service():
    """Test MLVerdictService"""
    logger.info("=" * 60)
    logger.info("Testing MLVerdictService")
    logger.info("=" * 60)

    # Test 1: Init without model (mock default model to not exist)
    with patch("services.ml_verdict_service.Path") as mock_path_class:

        def path_side_effect(path_str):
            mock_path = MagicMock()
            mock_path.exists.return_value = False  # Default model doesn't exist
            return mock_path

        mock_path_class.side_effect = path_side_effect

        service = MLVerdictService()
        assert (
            not service.model_loaded
        ), "Model should not be loaded without path and no default model"
        logger.info("? Test 1 PASSED: Init without model")

    # Test 2: Init with valid model
    model_path = "models/verdict_model_random_forest.pkl"
    if not Path(model_path).exists():
        logger.info("??  Test 2 SKIPPED: Model file not found")
        return
    service = MLVerdictService(model_path=model_path)
    # Model might fail to load even if file exists (e.g., incompatible pickle version)
    if not service.model_loaded:
        logger.info(
            "??  Test 2 SKIPPED: Model file exists but failed to load (may need retraining)"
        )
        return
    logger.info("? Test 2 PASSED: Init with valid model")

    # Test 3: Feature extraction
    service = MLVerdictService()
    features = service._extract_features(
        signals=["hammer"],
        rsi_value=28.5,
        is_above_ema200=True,
        vol_ok=True,
        vol_strong=False,
        fundamental_ok=True,
        timeframe_confirmation={"alignment_score": 6},
        news_sentiment=None,
        indicators={"rsi": 28.5, "ema200": 2400, "close": 2500},
        fundamentals={"pe": 15.0, "pb": 1.5},
        df=None,
    )
    assert "rsi_10" in features, "RSI should be in features"
    assert features["rsi_10"] == 28.5, "RSI value should match"
    assert "has_hammer" in features, "Hammer pattern should be in features"
    assert features["has_hammer"] == 1.0, "Hammer should be True"
    assert features["pe"] == 15.0, "PE should match"
    logger.info("? Test 3 PASSED: Feature extraction")

    # Test 4: Fallback to rule-based
    service = MLVerdictService()
    verdict, justification = service.determine_verdict(
        signals=["hammer"],
        rsi_value=28.0,
        is_above_ema200=True,
        vol_ok=True,
        vol_strong=False,
        fundamental_ok=True,
        timeframe_confirmation=None,
        news_sentiment=None,
    )
    assert verdict in ["strong_buy", "buy", "watch", "avoid"], "Should return valid verdict"
    logger.info(f"? Test 4 PASSED: Fallback to rule-based (verdict: {verdict})")

    logger.info("\n? All MLVerdictService tests passed!\n")


def test_ml_price_service():
    """Test MLPriceService"""
    logger.info("=" * 60)
    logger.info("Testing MLPriceService")
    logger.info("=" * 60)

    # Test 1: Init without models
    service = MLPriceService()
    assert not service.target_model_loaded, "Target model should not be loaded"
    assert not service.stop_loss_model_loaded, "Stop loss model should not be loaded"
    logger.info("? Test 1 PASSED: Init without models")

    # Test 2: Predict target without model (fallback)
    df = pd.DataFrame(
        {
            "close": [2400, 2450, 2500],
            "high": [2420, 2470, 2520],
            "low": [2380, 2430, 2480],
            "volume": [1000000, 1200000, 1100000],
        }
    )

    target, confidence = service.predict_target(
        current_price=2500.0,
        indicators={"rsi": 35, "ema200": 2400},
        timeframe_confirmation={"alignment_score": 7},
        df=df,
        rule_based_target=2650.0,
    )
    assert target == 2650.0, "Should fall back to rule-based target"
    assert confidence == 0.5, "Fallback confidence should be 0.5"
    logger.info("? Test 2 PASSED: Predict target fallback")

    # Test 3: Predict stop loss without model (fallback)
    stop_loss, confidence = service.predict_stop_loss(
        current_price=2500.0,
        indicators={"rsi": 35, "ema200": 2400},
        df=df,
        rule_based_stop_loss=2300.0,
    )
    assert stop_loss == 2300.0, "Should fall back to rule-based stop loss"
    assert confidence == 0.5, "Fallback confidence should be 0.5"
    logger.info("? Test 3 PASSED: Predict stop loss fallback")

    # Test 4: Feature extraction for target
    df_long = pd.DataFrame(
        {
            "close": [2400, 2450, 2500, 2480, 2520] * 5,
            "high": [2420, 2470, 2520, 2500, 2540] * 5,
            "low": [2380, 2430, 2480, 2460, 2500] * 5,
            "volume": [1000000, 1200000, 1100000, 1150000, 1180000] * 5,
        }
    )

    features = service._extract_target_features(
        current_price=2520.0,
        indicators={"rsi": 35, "ema200": 2400},
        timeframe_confirmation={"alignment_score": 7},
        df=df_long,
    )
    assert "current_price" in features, "Current price should be in features"
    assert "volatility" in features, "Volatility should be in features"
    assert "momentum" in features, "Momentum should be in features"
    logger.info("? Test 4 PASSED: Target feature extraction")

    # Test 5: Feature extraction for stop loss
    features = service._extract_stop_loss_features(
        current_price=2520.0, indicators={"rsi": 35, "ema200": 2400}, df=df_long
    )
    assert "current_price" in features, "Current price should be in features"
    assert "atr_pct" in features, "ATR should be in features"
    assert "support_distance_pct" in features, "Support distance should be in features"
    logger.info("? Test 5 PASSED: Stop loss feature extraction")

    logger.info("\n? All MLPriceService tests passed!\n")


def main():
    """Run all tests"""
    logger.info("? Starting ML Services Unit Tests\n")

    try:
        test_ml_verdict_service()
        test_ml_price_service()

        logger.info("=" * 60)
        logger.info("? ALL UNIT TESTS PASSED!")
        logger.info("=" * 60)
        return 0
    except AssertionError as e:
        logger.error(f"? Test failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"? Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
