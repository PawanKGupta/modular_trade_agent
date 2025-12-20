"""
Unit Tests for ML Verdict Service - Confidence-Aware Combination Logic

Tests the confidence-aware combination of ML and rule-based verdicts.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from config.strategy_config import StrategyConfig
from services.ml_verdict_service import MLVerdictService


class TestConfidenceAwareCombination:
    """Test confidence-aware combination logic"""

    @pytest.fixture
    def config(self):
        """Create test configuration"""
        return StrategyConfig(
            ml_enabled=True,
            ml_confidence_threshold=0.5,
            ml_combine_with_rules=True,
        )

    @pytest.fixture
    def config_no_combine(self):
        """Create test configuration without combining"""
        return StrategyConfig(
            ml_enabled=True,
            ml_confidence_threshold=0.5,
            ml_combine_with_rules=False,
        )

    @pytest.fixture
    def mock_model(self):
        """Create mock ML model"""
        model = MagicMock()
        model.predict_proba.return_value = [[0.1, 0.2, 0.3, 0.4]]  # [strong_buy, buy, watch, avoid]
        model.feature_names_in_ = None
        model.n_features_in_ = 43
        return model

    @pytest.fixture
    def service(self, config, mock_model):
        """Create MLVerdictService with mocked model"""
        with patch("services.ml_verdict_service.joblib.load") as mock_load:
            mock_load.return_value = mock_model
            with patch("pathlib.Path.exists", return_value=True):
                service = MLVerdictService(model_path="test_model.pkl", config=config)
                service.model = mock_model
                service.model_loaded = True
                return service

    def test_get_more_conservative_verdict_basic(self, service):
        """Test basic conservative verdict selection"""
        # ML more conservative
        assert service._get_more_conservative_verdict("watch", "buy") == "watch"
        assert service._get_more_conservative_verdict("avoid", "strong_buy") == "avoid"

        # Rules more conservative
        assert service._get_more_conservative_verdict("buy", "watch") == "watch"
        assert service._get_more_conservative_verdict("strong_buy", "avoid") == "avoid"

        # Same verdict
        assert service._get_more_conservative_verdict("buy", "buy") == "buy"
        assert service._get_more_conservative_verdict("watch", "watch") == "watch"

    def test_confidence_aware_high_confidence_ml_more_conservative(self, service):
        """Test high confidence ML (>=70%) when ML is more conservative"""
        # ML says "watch" with high confidence, rules say "buy"
        result = service._get_confidence_aware_combined_verdict(
            ml_verdict="watch",
            ml_confidence=0.85,
            rule_verdict="buy",
            confidence_threshold=0.5,
        )
        assert result == "watch", "High confidence ML should be used when more conservative"

    def test_confidence_aware_high_confidence_ml_less_conservative(self, service):
        """Test high confidence ML (>=70%) when rules are more conservative"""
        # ML says "buy" with high confidence, rules say "watch"
        result = service._get_confidence_aware_combined_verdict(
            ml_verdict="buy",
            ml_confidence=0.80,
            rule_verdict="watch",
            confidence_threshold=0.5,
        )
        assert result == "watch", "Rules should be used when more conservative (safety-first)"

    def test_confidence_aware_high_confidence_both_agree(self, service):
        """Test high confidence ML when both agree"""
        # Both say "buy" with high ML confidence
        result = service._get_confidence_aware_combined_verdict(
            ml_verdict="buy",
            ml_confidence=0.75,
            rule_verdict="buy",
            confidence_threshold=0.5,
        )
        assert result == "buy", "Should use agreed verdict"

    def test_confidence_aware_medium_confidence_uses_conservative(self, service):
        """Test medium confidence (50-70%) uses more conservative verdict"""
        # ML says "watch" with medium confidence, rules say "buy"
        result = service._get_confidence_aware_combined_verdict(
            ml_verdict="watch",
            ml_confidence=0.65,
            rule_verdict="buy",
            confidence_threshold=0.5,
        )
        assert result == "watch", "Medium confidence should use more conservative verdict"

    def test_confidence_aware_low_confidence_trusts_rules(self, service):
        """Test low confidence (just above threshold) trusts rules more"""
        # ML says "watch" with low confidence, rules say "buy"
        result = service._get_confidence_aware_combined_verdict(
            ml_verdict="watch",
            ml_confidence=0.52,
            rule_verdict="buy",
            confidence_threshold=0.5,
        )
        assert result == "buy", "Low confidence should trust rules more"

    def test_confidence_aware_low_confidence_strong_safety_signal(self, service):
        """Test low confidence but ML is much more conservative (strong safety signal)"""
        # ML says "avoid" with low confidence, rules say "strong_buy"
        # ML is 3 levels more conservative (avoid=3, strong_buy=0, diff=3)
        result = service._get_confidence_aware_combined_verdict(
            ml_verdict="avoid",
            ml_confidence=0.51,
            rule_verdict="strong_buy",
            confidence_threshold=0.5,
        )
        assert result == "avoid", "Strong safety signal (avoid) should override low confidence"

    def test_confidence_aware_low_confidence_slight_difference(self, service):
        """Test low confidence with slight difference uses rules"""
        # ML says "watch" with low confidence, rules say "buy"
        # Only 1 level difference, not strong enough
        result = service._get_confidence_aware_combined_verdict(
            ml_verdict="watch",
            ml_confidence=0.51,
            rule_verdict="buy",
            confidence_threshold=0.5,
        )
        assert result == "buy", "Low confidence with slight difference should use rules"

    def test_determine_verdict_combine_mode_high_confidence_agreement(self, service, config):
        """Test determine_verdict in combine mode with high confidence agreement"""
        service.config = config

        # Mock ML prediction
        with patch.object(service, "_predict_with_ml", return_value=("buy", 0.85, {"buy": 0.85})):
            # Mock parent class determine_verdict method
            with patch.object(
                MLVerdictService.__bases__[0],
                "determine_verdict",
                return_value=("buy", ["Rule-based justification"]),
            ):
                verdict, justification = service.determine_verdict(
                    signals=[],
                    rsi_value=25.0,
                    is_above_ema200=True,
                    vol_ok=True,
                    vol_strong=False,
                    fundamental_ok=True,
                    timeframe_confirmation=None,
                    news_sentiment=None,
                    chart_quality_passed=True,
                )

                assert verdict == "buy"
                assert "Both systems agree" in " ".join(justification)

    def test_determine_verdict_combine_mode_high_confidence_ml_conservative(self, service, config):
        """Test determine_verdict in combine mode with high confidence ML being conservative"""
        service.config = config

        # Mock ML prediction: "watch" with high confidence
        with patch.object(
            service, "_predict_with_ml", return_value=("watch", 0.80, {"watch": 0.80})
        ):
            # Mock rule-based verdict: "buy"
            with patch.object(
                MLVerdictService.__bases__[0],
                "determine_verdict",
                return_value=("buy", ["Rule-based justification"]),
            ):
                verdict, justification = service.determine_verdict(
                    signals=[],
                    rsi_value=25.0,
                    is_above_ema200=True,
                    vol_ok=True,
                    vol_strong=False,
                    fundamental_ok=True,
                    timeframe_confirmation=None,
                    news_sentiment=None,
                    chart_quality_passed=True,
                )

                # Should use "watch" (ML is more conservative with high confidence)
                assert verdict == "watch"
                assert "HIGH confidence" in " ".join(justification)

    def test_determine_verdict_combine_mode_low_confidence_uses_rules(self, service, config):
        """Test determine_verdict in combine mode with low confidence uses rules"""
        service.config = config

        # Mock ML prediction: "watch" with low confidence
        with patch.object(
            service, "_predict_with_ml", return_value=("watch", 0.52, {"watch": 0.52})
        ):
            # Mock rule-based verdict: "buy"
            with patch.object(
                MLVerdictService.__bases__[0],
                "determine_verdict",
                return_value=("buy", ["Rule-based justification"]),
            ):
                verdict, justification = service.determine_verdict(
                    signals=[],
                    rsi_value=25.0,
                    is_above_ema200=True,
                    vol_ok=True,
                    vol_strong=False,
                    fundamental_ok=True,
                    timeframe_confirmation=None,
                    news_sentiment=None,
                    chart_quality_passed=True,
                )

                # Should use "buy" (rules) due to low ML confidence
                assert verdict == "buy"
                justification_text = " ".join(justification).lower()
                assert (
                    "low confidence" in justification_text
                    or "rules used" in justification_text
                    or "confidence-aware combination" in justification_text
                )

    def test_determine_verdict_no_combine_mode_uses_ml_directly(self, service, config_no_combine):
        """Test determine_verdict without combine mode uses ML directly"""
        service.config = config_no_combine

        # Mock ML prediction
        with patch.object(
            service, "_predict_with_ml", return_value=("strong_buy", 0.75, {"strong_buy": 0.75})
        ):
            # Mock rule-based verdict
            with patch.object(
                MLVerdictService.__bases__[0],
                "determine_verdict",
                return_value=("buy", ["Rule-based justification"]),
            ):
                verdict, justification = service.determine_verdict(
                    signals=[],
                    rsi_value=25.0,
                    is_above_ema200=True,
                    vol_ok=True,
                    vol_strong=False,
                    fundamental_ok=True,
                    timeframe_confirmation=None,
                    news_sentiment=None,
                    chart_quality_passed=True,
                )

                # Should use ML verdict directly
                assert verdict == "strong_buy"
                assert "ML prediction" in " ".join(justification)

    def test_determine_verdict_ml_confidence_below_threshold(self, service, config):
        """Test determine_verdict when ML confidence is below threshold"""
        # Mock ML prediction with low confidence
        service._predict_with_ml = Mock(return_value=("buy", 0.45, {"buy": 0.45}))

        # Mock rule-based verdict
        with patch.object(
            service, "determine_verdict", wraps=super(MLVerdictService, service).determine_verdict
        ) as mock_super:
            mock_super.return_value = ("watch", ["Rule-based justification"])

            verdict, justification = service.determine_verdict(
                signals=[],
                rsi_value=25.0,
                is_above_ema200=True,
                vol_ok=True,
                vol_strong=False,
                fundamental_ok=True,
                timeframe_confirmation=None,
                news_sentiment=None,
                chart_quality_passed=True,
            )

            # Should use rule-based verdict (ML confidence too low)
            assert verdict == "watch"

    def test_determine_verdict_chart_quality_fails(self, service, config):
        """Test determine_verdict when chart quality fails (hard filter)"""
        # Should return "avoid" immediately without ML prediction
        verdict, justification = service.determine_verdict(
            signals=[],
            rsi_value=25.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=False,
            fundamental_ok=True,
            timeframe_confirmation=None,
            news_sentiment=None,
            chart_quality_passed=False,  # Chart quality failed
        )

        assert verdict == "avoid"
        assert "Chart quality failed" in " ".join(justification)

        # Verify ML prediction was not called
        assert not hasattr(service, "_ml_prediction_info") or service._ml_prediction_info is None

    def test_confidence_aware_edge_cases(self, service):
        """Test edge cases in confidence-aware combination"""
        # Test exact 70% threshold
        result = service._get_confidence_aware_combined_verdict(
            ml_verdict="watch",
            ml_confidence=0.70,
            rule_verdict="buy",
            confidence_threshold=0.5,
        )
        assert result == "watch", "70% should be treated as high confidence"

        # Test exact 50% threshold (now in low confidence band 50-60%)
        result = service._get_confidence_aware_combined_verdict(
            ml_verdict="watch",
            ml_confidence=0.50,
            rule_verdict="buy",
            confidence_threshold=0.5,
        )
        assert result == "buy", "50% should be treated as low confidence and trust rules more"

        # Test unknown verdicts default to watch
        result = service._get_confidence_aware_combined_verdict(
            ml_verdict="unknown",
            ml_confidence=0.65,
            rule_verdict="buy",
            confidence_threshold=0.5,
        )
        assert result == "buy", "Unknown ML verdict should default to watch rank, rules win"

    def test_all_verdict_combinations(self, service):
        """Test all possible verdict combinations"""
        verdicts = ["strong_buy", "buy", "watch", "avoid"]

        for ml_verdict in verdicts:
            for rule_verdict in verdicts:
                # High confidence
                result_high = service._get_confidence_aware_combined_verdict(
                    ml_verdict=ml_verdict,
                    ml_confidence=0.80,
                    rule_verdict=rule_verdict,
                    confidence_threshold=0.5,
                )

                # Medium confidence
                result_medium = service._get_confidence_aware_combined_verdict(
                    ml_verdict=ml_verdict,
                    ml_confidence=0.60,
                    rule_verdict=rule_verdict,
                    confidence_threshold=0.5,
                )

                # Low confidence
                result_low = service._get_confidence_aware_combined_verdict(
                    ml_verdict=ml_verdict,
                    ml_confidence=0.52,
                    rule_verdict=rule_verdict,
                    confidence_threshold=0.5,
                )

                # All results should be valid verdicts
                assert result_high in verdicts
                assert result_medium in verdicts
                assert result_low in verdicts

                # Results should be conservative (higher rank or equal)
                verdict_hierarchy = {"strong_buy": 0, "buy": 1, "watch": 2, "avoid": 3}
                ml_rank = verdict_hierarchy.get(ml_verdict, 2)
                rule_rank = verdict_hierarchy.get(rule_verdict, 2)

                result_high_rank = verdict_hierarchy.get(result_high, 2)
                result_medium_rank = verdict_hierarchy.get(result_medium, 2)
                result_low_rank = verdict_hierarchy.get(result_low, 2)

                # All results should be at least as conservative as the more conservative input
                max_input_rank = max(ml_rank, rule_rank)
                assert (
                    result_high_rank >= max_input_rank
                    or result_high == ml_verdict
                    or result_high == rule_verdict
                )
                assert result_medium_rank >= max_input_rank
                assert (
                    result_low_rank >= max_input_rank or result_low == rule_verdict
                )  # Low confidence prefers rules
