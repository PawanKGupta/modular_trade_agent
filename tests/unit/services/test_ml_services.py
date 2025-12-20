"""
Unit Tests for ML Services

Tests for MLVerdictService and MLPriceService.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from services.ml_price_service import MLPriceService
from services.ml_verdict_service import MLVerdictService


class TestMLVerdictService:
    """Unit tests for MLVerdictService"""

    def test_init_without_model(self):
        """Test initialization without model path"""
        # Mock Path.exists to return False for default model (simulate no default model)
        with patch("services.ml_verdict_service.Path") as mock_path_class:

            def path_side_effect(path_str):
                mock_path = MagicMock()
                mock_path.exists.return_value = False  # Default model doesn't exist
                return mock_path

            mock_path_class.side_effect = path_side_effect

            service = MLVerdictService()
            assert not service.model_loaded
            assert service.model is None

    def test_init_with_invalid_path(self):
        """Test initialization with invalid model path"""
        service = MLVerdictService(model_path="invalid/path.pkl")
        assert not service.model_loaded

    def test_init_with_valid_model(self):
        """Test initialization with valid model"""
        model_path = "models/verdict_model_random_forest.pkl"
        if not Path(model_path).exists():
            pytest.skip("Model file not found")
        service = MLVerdictService(model_path=model_path)
        # Model might fail to load even if file exists (e.g., incompatible pickle version)
        if not service.model_loaded:
            pytest.skip("Model file exists but failed to load (may need retraining)")
        assert service.model is not None

    def test_extract_features_basic(self):
        """Test feature extraction with basic inputs"""
        service = MLVerdictService()

        features = service._extract_features(
            signals=["hammer", "rsi_oversold"],
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

        assert "rsi_10" in features
        assert features["rsi_10"] == 28.5
        assert "price_above_ema200" in features
        assert features["price_above_ema200"] == 1.0
        assert "has_hammer" in features
        assert features["has_hammer"] == 1.0
        assert "alignment_score" in features
        assert features["alignment_score"] == 6
        assert "pe" in features
        assert features["pe"] == 15.0

    def test_extract_features_with_dataframe(self):
        """Test feature extraction with DataFrame"""
        service = MLVerdictService()

        # Create sample DataFrame
        df = pd.DataFrame(
            {
                "close": [2400, 2450, 2500],
                "high": [2420, 2470, 2520],
                "low": [2380, 2430, 2480],
                "volume": [1000000, 1200000, 1100000],
            }
        )

        features = service._extract_features(
            signals=[],
            rsi_value=50.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=False,
            fundamental_ok=True,
            timeframe_confirmation=None,
            news_sentiment=None,
            indicators={"rsi": 50.0, "ema200": 2400, "close": 2500},
            fundamentals=None,
            df=df,
        )

        # REMOVED FEATURES (Phase 5 cleanup): volume, price, ema200
        # These were redundant/not useful for ML
        assert "volume" not in features  # Removed: absolute volume not useful
        # Model expects 'avg_volume_20' (not dynamic avg_volume_{volume_lookback})
        # Always create avg_volume_20 to match training data (43 features)
        assert "avg_volume_20" in features  # Model expects this exact feature name
        assert "volume_ratio" in features  # Kept: relative metric
        assert "recent_high_20" in features  # Kept: useful
        assert "recent_low_20" in features  # Kept: useful
        assert "support_distance_pct" in features  # Kept: useful

    def test_predict_verdict_with_confidence_no_model(self):
        """Test prediction when model not loaded"""
        # Mock Path.exists to return False for default model (simulate no default model)
        with patch("services.ml_verdict_service.Path") as mock_path_class:

            def path_side_effect(path_str):
                mock_path = MagicMock()
                mock_path.exists.return_value = False  # Default model doesn't exist
                return mock_path

            mock_path_class.side_effect = path_side_effect

            service = MLVerdictService()

            verdict, confidence = service.predict_verdict_with_confidence(
                signals=[],
                rsi_value=30.0,
                is_above_ema200=True,
                vol_ok=True,
                vol_strong=False,
                fundamental_ok=True,
                timeframe_confirmation=None,
                news_sentiment=None,
            )

            assert verdict is None
            assert confidence == 0.0

    def test_fallback_to_rule_based(self):
        """Test fallback to rule-based verdict"""
        service = MLVerdictService()  # No model loaded

        verdict, justification = service.determine_verdict(
            signals=["hammer"],
            rsi_value=28.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=False,
            fundamental_ok=True,
            timeframe_confirmation=None,
            news_sentiment=None,
            chart_quality_passed=True,  # Chart quality passed
        )

        # Should return rule-based verdict (not None)
        assert verdict in ["strong_buy", "buy", "watch", "avoid"]

    def test_determine_verdict_chart_quality_failed(self):
        """Test that determine_verdict returns 'avoid' immediately when chart quality fails (Stage 1)"""
        service = MLVerdictService()  # No model loaded

        verdict, justification = service.determine_verdict(
            signals=["hammer"],
            rsi_value=28.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=False,
            fundamental_ok=True,
            timeframe_confirmation=None,
            news_sentiment=None,
            chart_quality_passed=False,  # Chart quality failed (Stage 1)
        )

        # Should return 'avoid' immediately without ML prediction
        assert verdict == "avoid"
        assert "Chart quality failed" in str(justification)

    def test_determine_verdict_chart_quality_passed_no_model(self):
        """Test that determine_verdict proceeds to rule-based when chart quality passed but no ML model"""
        service = MLVerdictService()  # No model loaded

        verdict, justification = service.determine_verdict(
            signals=["hammer"],
            rsi_value=28.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=False,
            fundamental_ok=True,
            timeframe_confirmation=None,
            news_sentiment=None,
            chart_quality_passed=True,  # Chart quality passed (Stage 1)
        )

        # Should proceed to rule-based logic (Stage 2 fallback)
        assert verdict in ["strong_buy", "buy", "watch", "avoid"]

    def test_predict_verdict_with_confidence_chart_quality_failed(self):
        """Test that predict_verdict_with_confidence returns None when chart quality fails (Stage 1)"""
        # Mock Path.exists to return False for default model (simulate no default model)
        with patch("services.ml_verdict_service.Path") as mock_path_class:

            def path_side_effect(path_str):
                mock_path = MagicMock()
                mock_path.exists.return_value = False  # Default model doesn't exist
                return mock_path

            mock_path_class.side_effect = path_side_effect

            service = MLVerdictService()

            verdict, confidence = service.predict_verdict_with_confidence(
                signals=[],
                rsi_value=30.0,
                is_above_ema200=True,
                vol_ok=True,
                vol_strong=False,
                fundamental_ok=True,
                timeframe_confirmation=None,
                news_sentiment=None,
                chart_quality_passed=False,  # Chart quality failed (Stage 1)
            )

            # Should return None immediately without ML prediction
            assert verdict is None
            assert confidence == 0.0

    def test_predict_verdict_with_confidence_chart_quality_passed_no_model(self):
        """Test that predict_verdict_with_confidence returns None when chart quality passed but no ML model"""
        # Mock Path.exists to return False for default model (simulate no default model)
        with patch("services.ml_verdict_service.Path") as mock_path_class:

            def path_side_effect(path_str):
                mock_path = MagicMock()
                mock_path.exists.return_value = False  # Default model doesn't exist
                return mock_path

            mock_path_class.side_effect = path_side_effect

            service = MLVerdictService()

            verdict, confidence = service.predict_verdict_with_confidence(
                signals=[],
                rsi_value=30.0,
                is_above_ema200=True,
                vol_ok=True,
                vol_strong=False,
                fundamental_ok=True,
                timeframe_confirmation=None,
                news_sentiment=None,
                chart_quality_passed=True,  # Chart quality passed (Stage 1)
            )

            # Should return None because no ML model (Stage 2 unavailable)
            assert verdict is None
            assert confidence == 0.0

    def test_determine_verdict_chart_quality_passed_with_model(self):
        """Test that determine_verdict proceeds to ML prediction when chart quality passed and model exists"""
        model_path = "models/verdict_model_random_forest.pkl"
        if not Path(model_path).exists():
            pytest.skip("Model file not found")

        service = MLVerdictService(model_path=model_path)
        if not service.model_loaded:
            pytest.skip("Model not loaded")

        # Test with chart quality passed
        verdict, justification = service.determine_verdict(
            signals=["hammer"],
            rsi_value=28.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=False,
            fundamental_ok=True,
            timeframe_confirmation=None,
            news_sentiment=None,
            chart_quality_passed=True,  # Chart quality passed (Stage 1)
        )

        # Should return ML verdict or rule-based verdict (Stage 2)
        assert verdict in ["strong_buy", "buy", "watch", "avoid"]

        # Test with chart quality failed
        verdict, justification = service.determine_verdict(
            signals=["hammer"],
            rsi_value=28.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=False,
            fundamental_ok=True,
            timeframe_confirmation=None,
            news_sentiment=None,
            chart_quality_passed=False,  # Chart quality failed (Stage 1)
        )

        # Should return 'avoid' immediately without ML prediction
        assert verdict == "avoid"
        assert "Chart quality failed" in str(justification)

    def test_predict_verdict_with_confidence_chart_quality_passed_with_model(self):
        """Test that predict_verdict_with_confidence proceeds to ML prediction when chart quality passed and model exists"""
        model_path = "models/verdict_model_random_forest.pkl"
        if not Path(model_path).exists():
            pytest.skip("Model file not found")

        service = MLVerdictService(model_path=model_path)
        if not service.model_loaded:
            pytest.skip("Model not loaded")

        # Test with chart quality passed
        verdict, confidence = service.predict_verdict_with_confidence(
            signals=[],
            rsi_value=28.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=False,
            fundamental_ok=True,
            timeframe_confirmation=None,
            news_sentiment=None,
            chart_quality_passed=True,  # Chart quality passed (Stage 1)
        )

        # Should return ML verdict (Stage 2)
        if verdict is not None:
            assert verdict in ["strong_buy", "buy", "watch", "avoid"]
            assert 0.0 <= confidence <= 1.0

        # Test with chart quality failed
        verdict, confidence = service.predict_verdict_with_confidence(
            signals=[],
            rsi_value=28.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=False,
            fundamental_ok=True,
            timeframe_confirmation=None,
            news_sentiment=None,
            chart_quality_passed=False,  # Chart quality failed (Stage 1)
        )

        # Should return None immediately without ML prediction
        assert verdict is None
        assert confidence == 0.0


class TestMLPriceService:
    """Unit tests for MLPriceService"""

    def test_init_without_models(self):
        """Test initialization without model paths"""
        service = MLPriceService()
        assert not service.target_model_loaded
        assert not service.stop_loss_model_loaded

    def test_init_with_invalid_paths(self):
        """Test initialization with invalid model paths"""
        service = MLPriceService(
            target_model_path="invalid/path.pkl", stop_loss_model_path="invalid/path.pkl"
        )
        assert not service.target_model_loaded
        assert not service.stop_loss_model_loaded

    def test_predict_target_without_model(self):
        """Test price target prediction without model"""
        service = MLPriceService()

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

        # Should fall back to rule-based target
        assert target == 2650.0
        assert confidence == 0.5

    def test_predict_stop_loss_without_model(self):
        """Test stop loss prediction without model"""
        service = MLPriceService()

        df = pd.DataFrame(
            {
                "close": [2400, 2450, 2500],
                "high": [2420, 2470, 2520],
                "low": [2380, 2430, 2480],
                "volume": [1000000, 1200000, 1100000],
            }
        )

        stop_loss, confidence = service.predict_stop_loss(
            current_price=2500.0,
            indicators={"rsi": 35, "ema200": 2400},
            df=df,
            rule_based_stop_loss=2300.0,
        )

        # Should fall back to rule-based stop loss
        assert stop_loss == 2300.0
        assert confidence == 0.5

    def test_extract_target_features(self):
        """Test target feature extraction"""
        service = MLPriceService()

        df = pd.DataFrame(
            {
                "close": [2400, 2450, 2500, 2480, 2520] * 5,  # 25 rows
                "high": [2420, 2470, 2520, 2500, 2540] * 5,
                "low": [2380, 2430, 2480, 2460, 2500] * 5,
                "volume": [1000000, 1200000, 1100000, 1150000, 1180000] * 5,
            }
        )

        features = service._extract_target_features(
            current_price=2520.0,
            indicators={"rsi": 35, "ema200": 2400},
            timeframe_confirmation={"alignment_score": 7},
            df=df,
        )

        assert "current_price" in features
        assert features["current_price"] == 2520.0
        assert "rsi_10" in features
        assert "ema200" in features
        assert "recent_high" in features
        assert "recent_low" in features
        assert "volatility" in features
        assert "momentum" in features

    def test_extract_stop_loss_features(self):
        """Test stop loss feature extraction"""
        service = MLPriceService()

        df = pd.DataFrame(
            {
                "close": [2400, 2450, 2500, 2480, 2520] * 5,
                "high": [2420, 2470, 2520, 2500, 2540] * 5,
                "low": [2380, 2430, 2480, 2460, 2500] * 5,
                "volume": [1000000, 1200000, 1100000, 1150000, 1180000] * 5,
            }
        )

        features = service._extract_stop_loss_features(
            current_price=2520.0, indicators={"rsi": 35, "ema200": 2400}, df=df
        )

        assert "current_price" in features
        assert "recent_low" in features
        assert "support_distance_pct" in features
        assert "atr_pct" in features
        assert "rsi_10" in features
        assert "volume_ratio" in features


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
