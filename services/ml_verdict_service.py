"""
ML Verdict Service

ML-enhanced verdict service that uses trained models to predict verdicts.
Falls back to rule-based logic if ML model is unavailable.
"""

from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from services.verdict_service import VerdictService
from utils.logger import logger


class MLVerdictService(VerdictService):
    """
    ML-enhanced verdict service

    Uses ML model to predict verdict probabilities,
    falls back to rule-based logic if ML unavailable.
    """

    def __init__(self, model_path: str | None = None, config=None):
        """
        Initialize ML verdict service

        Args:
            model_path: Path to trained ML model (if None, will try to find based on config)
            config: Strategy configuration (uses default if None)
        """
        super().__init__(config)

        self.model = None
        self.model_loaded = False
        self.feature_cols = []

        # If no model_path provided, try to find model based on configuration
        if model_path is None:
            try:
                from utils.model_versioning import get_model_path

                model_path = get_model_path(self.config, "verdict")
                if model_path:
                    logger.info(f"Found model for config: {model_path}")
            except Exception as e:
                logger.debug(f"Could not find model for config: {e}")

        # Fallback to default model if no config-based model found
        # This provides a sensible default for production use
        if model_path is None:
            default_model = "models/verdict_model_random_forest.pkl"
            if Path(default_model).exists():
                model_path = default_model
                logger.info(f"Using default model: {default_model}")

        if model_path and Path(model_path).exists():
            try:
                self.model = joblib.load(model_path)
                self.model_loaded = True
                logger.info(f"? ML verdict model loaded from {model_path}")

                # Load feature columns if available
                # Try multiple possible filenames for backward compatibility
                model_stem = Path(model_path).stem

                # Extract model type from filename (e.g., "verdict_model_random_forest" -> "random_forest")
                model_type = None
                if "random_forest" in model_stem:
                    model_type = "random_forest"
                elif "xgboost" in model_stem:
                    model_type = "xgboost"

                possible_paths = [
                    # Current format: verdict_model_features_{model_type}.txt (from training service)
                    (
                        Path(model_path).parent / f"verdict_model_features_{model_type}.txt"
                        if model_type
                        else None
                    ),
                    # Alternative format: {stem}_features.txt
                    Path(model_path).parent / f"{model_stem.replace('model_', '')}_features.txt",
                    # Legacy format: verdict_model_features_enhanced.txt
                    Path(model_path).parent / "verdict_model_features_enhanced.txt",
                ]

                feature_cols_path = None
                for path in possible_paths:
                    if path and path.exists():
                        feature_cols_path = path
                        break

                if feature_cols_path:
                    with open(feature_cols_path) as f:
                        self.feature_cols = [line.strip() for line in f if line.strip()]
                    logger.info(
                        f"   Loaded {len(self.feature_cols)} feature columns from {feature_cols_path.name}"
                    )
                # Try to get feature names from the model itself (scikit-learn stores them)
                elif hasattr(self.model, "feature_names_in_"):
                    self.feature_cols = list(self.model.feature_names_in_)
                    logger.info(
                        f"   Loaded {len(self.feature_cols)} feature columns from model (feature_names_in_)"
                    )
                else:
                    logger.warning(
                        "Feature columns file not found and model doesn't have feature_names_in_. Will extract features dynamically."
                    )

            except Exception as e:
                logger.warning(f"[WARN]? Failed to load ML model: {e}, using rule-based logic")
                self.model = None
                self.model_loaded = False
        elif model_path:
            logger.warning(f"[WARN]? Model file not found: {model_path}, using rule-based logic")
        else:
            logger.info("i? No ML model path provided, using rule-based logic")

    def determine_verdict(
        self,
        signals: list[str],
        rsi_value: float | None,
        is_above_ema200: bool,
        vol_ok: bool,
        vol_strong: bool,
        fundamental_ok: bool,
        timeframe_confirmation: dict[str, Any] | None,
        news_sentiment: dict[str, Any] | None,
        chart_quality_passed: bool = True,
        fundamental_assessment: dict[str, Any] | None = None,
        indicators: dict[str, Any] | None = None,
        fundamentals: dict[str, Any] | None = None,
        df: Any | None = None,
    ) -> tuple[str, list[str]]:
        """
        Determine verdict using ML if available, else rule-based

        Two-Stage Approach:
        1. Stage 1: Chart quality filter (hard filter) - MUST pass before ML
        2. Stage 2: ML model prediction (only if chart quality passed)

        Args:
            signals: List of detected signals
            rsi_value: Current RSI value
            is_above_ema200: Whether price is above EMA200
            vol_ok: Whether volume is OK
            vol_strong: Whether volume is strong
            fundamental_ok: Whether fundamentals are OK (backward compatibility)
            timeframe_confirmation: Multi-timeframe confirmation data
            news_sentiment: News sentiment data
            chart_quality_passed: Whether chart quality check passed (hard filter)
            fundamental_assessment: Optional fundamental assessment dict from assess_fundamentals()
                                    If provided, overrides fundamental_ok for more flexible logic
                                    (FLEXIBLE FUNDAMENTAL FILTER - 2025-11-09)

        Returns:
            Tuple of (verdict, justification)
        """
        # Stage 1: Chart quality filter (hard filter)
        # If chart quality fails, immediately return "avoid" without ML prediction
        # This is a CRITICAL filter - ML model should NEVER predict when chart quality fails
        if not chart_quality_passed:
            logger.info(
                "ML verdict service: Chart quality FAILED - returning 'avoid' immediately (hard filter)"
            )
            logger.info("ML verdict service: Skipping ML prediction (chart quality is mandatory)")
            return "avoid", ["Chart quality failed - too many gaps/extreme candles/flat movement"]

        # FLEXIBLE FUNDAMENTAL FILTER (2025-11-09): Check fundamental_avoid flag
        # If fundamental_avoid is True, force "avoid" verdict (expensive loss-making company)
        if fundamental_assessment is not None:
            fundamental_avoid = fundamental_assessment.get("fundamental_avoid", False)
            if fundamental_avoid:
                fundamental_reason = fundamental_assessment.get(
                    "fundamental_reason", "loss_making_expensive"
                )
                logger.info(
                    "ML verdict service: Fundamental filter FAILED - returning 'avoid' immediately (hard filter)"
                )
                logger.info(
                    f"ML verdict service: Skipping ML prediction (fundamental filter: {fundamental_reason})"
                )
                return "avoid", [f"Fundamental filter: {fundamental_reason}"]

        # Stage 2: ML model prediction
        # ML model is fully trained (72.5% accuracy, 8,490 examples)
        # Use ML prediction if confidence meets threshold, otherwise fallback to rule-based

        ml_prediction_info = None  # Store ML prediction for Telegram notification
        verdict_source = "rule_based"  # Track which source was used

        if self.model_loaded:
            try:
                logger.debug("ML verdict service: Chart quality passed - getting ML prediction")

                # Get ML prediction
                ml_result = self._predict_with_ml(
                    signals,
                    rsi_value,
                    is_above_ema200,
                    vol_ok,
                    vol_strong,
                    fundamental_ok,
                    timeframe_confirmation,
                    news_sentiment,
                    indicators,
                    fundamentals,
                    df,
                )

                if ml_result:
                    ml_verdict, ml_confidence, ml_probs = ml_result
                    ml_justification = self._build_ml_justification(ml_verdict)

                    # Get confidence threshold from config (default: 0.5)
                    confidence_threshold = (
                        getattr(self.config, "ml_confidence_threshold", 0.5) if self.config else 0.5
                    )

                    # Check if ML confidence meets threshold
                    if ml_confidence >= confidence_threshold:
                        # Get rule-based verdict for comparison/combination
                        rule_verdict, rule_justification = super().determine_verdict(
                            signals,
                            rsi_value,
                            is_above_ema200,
                            vol_ok,
                            vol_strong,
                            fundamental_ok,
                            timeframe_confirmation,
                            news_sentiment,
                            chart_quality_passed=chart_quality_passed,
                            fundamental_assessment=fundamental_assessment,
                        )

                        # Determine if we should combine verdicts (more conservative approach)
                        combine_with_rules = (
                            self.config
                            and hasattr(self.config, "ml_combine_with_rules")
                            and self.config.ml_combine_with_rules
                        )

                        if combine_with_rules:
                            # COMBINE MODE: Use confidence-aware combination
                            # Consider ML confidence when combining with rules
                            final_verdict = self._get_confidence_aware_combined_verdict(
                                ml_verdict, ml_confidence, rule_verdict, confidence_threshold
                            )

                            # Check if both systems agree (strong signal)
                            if ml_verdict == rule_verdict:
                                verdict_source = "ml_combined"
                                logger.info(
                                    f"ML verdict service: ML+Rules AGREE - both predict '{final_verdict}' "
                                    f"(confidence: {ml_confidence:.1%}) - Strong signal!"
                                )
                                # Build justification highlighting agreement
                                justification = [
                                    f"ML prediction: {ml_verdict} (confidence: {ml_confidence:.1%})",
                                    f"Rule-based verdict: {rule_verdict}",
                                    f"✅ Both systems agree: {final_verdict} (strong confirmation)",
                                ]
                                justification.extend(rule_justification)
                            elif final_verdict == ml_verdict:
                                verdict_source = "ml"
                                # Check if ML is more conservative than rules (important signal)
                                ml_rank = {"strong_buy": 0, "buy": 1, "watch": 2, "avoid": 3}.get(
                                    ml_verdict, 2
                                )
                                rule_rank = {"strong_buy": 0, "buy": 1, "watch": 2, "avoid": 3}.get(
                                    rule_verdict, 2
                                )

                                if ml_rank > rule_rank:
                                    # ML is more cautious - check confidence level
                                    if ml_confidence >= 0.70:
                                        logger.warning(
                                            f"ML verdict service: ML is MORE CONSERVATIVE than rules - "
                                            f"ML: '{ml_verdict}' (HIGH confidence: {ml_confidence:.1%}), Rules: '{rule_verdict}' "
                                            f"- Using ML verdict (high-confidence safety signal)"
                                        )
                                        justification = [
                                            f"ML prediction: {ml_verdict} (HIGH confidence: {ml_confidence:.1%})",
                                            f"Rule-based verdict: {rule_verdict}",
                                            f"⚠️ ML is more cautious with HIGH confidence - using '{final_verdict}' (safety-first)",
                                        ]
                                    elif ml_confidence >= 0.50:
                                        logger.warning(
                                            f"ML verdict service: ML is MORE CONSERVATIVE than rules - "
                                            f"ML: '{ml_verdict}' (confidence: {ml_confidence:.1%}), Rules: '{rule_verdict}' "
                                            f"- Using ML verdict (safety-first approach)"
                                        )
                                        justification = [
                                            f"ML prediction: {ml_verdict} (confidence: {ml_confidence:.1%})",
                                            f"Rule-based verdict: {rule_verdict}",
                                            f"⚠️ ML is more cautious - using '{final_verdict}' (safety-first approach)",
                                        ]
                                    else:
                                        # Low confidence but still using ML because it's much more conservative
                                        logger.warning(
                                            f"ML verdict service: ML is MORE CONSERVATIVE than rules - "
                                            f"ML: '{ml_verdict}' (LOW confidence: {ml_confidence:.1%}), Rules: '{rule_verdict}' "
                                            f"- Using ML verdict (strong safety signal despite low confidence)"
                                        )
                                        justification = [
                                            f"ML prediction: {ml_verdict} (LOW confidence: {ml_confidence:.1%})",
                                            f"Rule-based verdict: {rule_verdict}",
                                            f"⚠️ ML is much more cautious - using '{final_verdict}' (strong safety signal)",
                                        ]
                                else:
                                    # Same conservativeness level (shouldn't happen often, but handle it)
                                    logger.info(
                                        f"ML verdict service: ML+Rules combined - using ML verdict '{ml_verdict}' "
                                        f"(ML: {ml_verdict}, Rules: {rule_verdict}, confidence: {ml_confidence:.1%})"
                                    )
                                    justification = [
                                        f"ML prediction: {ml_verdict} (confidence: {ml_confidence:.1%})",
                                        f"Rule-based verdict: {rule_verdict}",
                                        f"Combined verdict: {final_verdict} (confidence-aware combination - ML used)",
                                    ]
                                justification.extend(rule_justification)
                            elif final_verdict == rule_verdict:
                                verdict_source = "rule_based"
                                # Check why rules were used (ML low confidence or rules more conservative)
                                ml_rank = {"strong_buy": 0, "buy": 1, "watch": 2, "avoid": 3}.get(
                                    ml_verdict, 2
                                )
                                rule_rank = {"strong_buy": 0, "buy": 1, "watch": 2, "avoid": 3}.get(
                                    rule_verdict, 2
                                )

                                if ml_confidence < 0.50:
                                    logger.info(
                                        f"ML verdict service: ML+Rules combined - using rule-based verdict '{rule_verdict}' "
                                        f"(ML: {ml_verdict} with LOW confidence: {ml_confidence:.1%}, Rules: {rule_verdict})"
                                    )
                                    justification = [
                                        f"ML prediction: {ml_verdict} (LOW confidence: {ml_confidence:.1%})",
                                        f"Rule-based verdict: {rule_verdict}",
                                        f"Combined verdict: {final_verdict} (using rules due to low ML confidence)",
                                    ]
                                elif rule_rank > ml_rank:
                                    logger.info(
                                        f"ML verdict service: ML+Rules combined - using rule-based verdict '{rule_verdict}' "
                                        f"(ML: {ml_verdict}, Rules: {rule_verdict} is more conservative, ML confidence: {ml_confidence:.1%})"
                                    )
                                    justification = [
                                        f"ML prediction: {ml_verdict} (confidence: {ml_confidence:.1%})",
                                        f"Rule-based verdict: {rule_verdict}",
                                        f"Combined verdict: {final_verdict} (rules are more conservative - safety-first)",
                                    ]
                                else:
                                    logger.info(
                                        f"ML verdict service: ML+Rules combined - using rule-based verdict '{rule_verdict}' "
                                        f"(ML: {ml_verdict}, Rules: {rule_verdict}, confidence: {ml_confidence:.1%})"
                                    )
                                    justification = [
                                        f"ML prediction: {ml_verdict} (confidence: {ml_confidence:.1%})",
                                        f"Rule-based verdict: {rule_verdict}",
                                        f"Combined verdict: {final_verdict} (confidence-aware combination - Rules used)",
                                    ]
                                justification.extend(rule_justification)
                            else:
                                # Should not happen, but handle edge case
                                verdict_source = "ml_combined"
                                logger.warning(
                                    f"ML verdict service: Unexpected verdict combination - "
                                    f"ML: {ml_verdict}, Rules: {rule_verdict}, Final: {final_verdict}"
                                )
                                justification = [
                                    f"ML prediction: {ml_verdict} (confidence: {ml_confidence:.1%})",
                                    f"Rule-based verdict: {rule_verdict}",
                                    f"Combined verdict: {final_verdict}",
                                ]
                                justification.extend(rule_justification)
                        else:
                            # DIRECT ML MODE: Use ML verdict directly (less conservative)
                            final_verdict = ml_verdict
                            verdict_source = "ml"
                            logger.info(
                                f"ML verdict service: Using ML prediction '{ml_verdict}' "
                                f"({ml_confidence:.1%} confidence, threshold: {confidence_threshold:.1%})"
                            )

                            # Build justification with ML as primary
                            justification = [
                                f"ML prediction: {ml_verdict} (confidence: {ml_confidence:.1%})",
                                f"Rule-based verdict: {rule_verdict} (for comparison)",
                            ]

                        # Store ML prediction info
                        ml_prediction_info = {
                            "ml_verdict": ml_verdict,
                            "ml_confidence": ml_confidence,
                            "ml_probabilities": ml_probs,
                            "ml_justification": ml_justification,
                            "rule_verdict": rule_verdict,
                            "verdict_source": verdict_source,
                        }

                        return final_verdict, justification
                    else:
                        # ML confidence too low - fallback to rule-based
                        logger.info(
                            f"ML verdict service: ML confidence too low "
                            f"({ml_confidence:.1%} < {confidence_threshold:.1%}), using rule-based logic"
                        )

                        # Store ML prediction for monitoring even though we're not using it
                        ml_prediction_info = {
                            "ml_verdict": ml_verdict,
                            "ml_confidence": ml_confidence,
                            "ml_probabilities": ml_probs,
                            "ml_justification": ml_justification,
                        }
                else:
                    logger.debug("ML prediction returned None - using rule-based logic")

            except Exception as e:
                logger.warning(f"ML prediction failed: {e}, using rule-based logic")
                import traceback

                logger.debug(traceback.format_exc())
        else:
            logger.debug("ML verdict service: ML model not loaded - using rule-based logic")

        # Fallback to rule-based logic if ML not available or confidence too low
        logger.debug("ML verdict service: Using rule-based logic for verdict determination")
        verdict, justification = super().determine_verdict(
            signals,
            rsi_value,
            is_above_ema200,
            vol_ok,
            vol_strong,
            fundamental_ok,
            timeframe_confirmation,
            news_sentiment,
            chart_quality_passed=chart_quality_passed,
            fundamental_assessment=fundamental_assessment,
        )

        # Store ML prediction info for monitoring/telegram (even if not used for verdict)
        if ml_prediction_info:
            ml_prediction_info["verdict_source"] = verdict_source
            self._ml_prediction_info = ml_prediction_info  # Store for retrieval
            logger.debug(
                f"Stored ML prediction info: {ml_prediction_info['ml_verdict']} "
                f"({ml_prediction_info['ml_confidence']:.1%}), verdict_source: {verdict_source}"
            )
        else:
            # Clear previous ML prediction if no new one available
            if hasattr(self, "_ml_prediction_info"):
                delattr(self, "_ml_prediction_info")
            logger.debug("No ML prediction info to store")

        return verdict, justification

    def get_last_ml_prediction(self) -> dict[str, Any] | None:
        """
        Get the ML prediction info from the last determine_verdict call.

        Returns:
            Dict with ml_verdict, ml_confidence, ml_probabilities or None
        """
        if hasattr(self, "_ml_prediction_info"):
            return self._ml_prediction_info
        return None

    def _predict_with_ml(
        self,
        signals: list[str],
        rsi_value: float | None,
        is_above_ema200: bool,
        vol_ok: bool,
        vol_strong: bool,
        fundamental_ok: bool,
        timeframe_confirmation: dict[str, Any] | None,
        news_sentiment: dict[str, Any] | None,
        indicators: dict[str, Any] | None = None,
        fundamentals: dict[str, Any] | None = None,
        df: Any | None = None,
    ) -> tuple | None:
        """
        Predict verdict using ML model

        Returns:
            Tuple of (verdict, confidence, probabilities) or None if prediction fails
        """
        try:
            # Extract features with full data for enhanced dip features
            features = self._extract_features(
                signals,
                rsi_value,
                is_above_ema200,
                vol_ok,
                vol_strong,
                fundamental_ok,
                timeframe_confirmation,
                news_sentiment,
                indicators,
                fundamentals,
                df,
            )

            if not features:
                logger.warning("ML prediction: Feature extraction returned empty/None")
                return None

            logger.debug(f"ML prediction: Extracted {len(features)} features")

            # Create feature vector matching model's expected format
            if self.feature_cols:
                # Use saved feature columns order
                feature_vector = [features.get(col, 0) for col in self.feature_cols]
            else:
                # Extract features dynamically (assumes model was trained with same features)
                feature_vector = list(features.values())

            # Predict
            probabilities = self.model.predict_proba([feature_vector])[0]
            verdicts = self.model.classes_  # ['strong_buy', 'buy', 'watch', 'avoid']

            # Get verdict with highest probability
            verdict_idx = probabilities.argmax()
            verdict = verdicts[verdict_idx]
            confidence = probabilities[verdict_idx]

            # Create probabilities dict
            probs_dict = {v: float(p) for v, p in zip(verdicts, probabilities)}

            # Return prediction info (even if confidence is low - for monitoring)
            logger.debug(f"ML verdict: {verdict} (confidence: {confidence:.2%})")
            return (verdict, confidence, probs_dict)

        except Exception as e:
            logger.warning(f"ML prediction error: {e}")
            import traceback

            logger.debug(traceback.format_exc())
            return None

    def _extract_features(
        self,
        signals: list[str],
        rsi_value: float | None,
        is_above_ema200: bool,
        vol_ok: bool,
        vol_strong: bool,
        fundamental_ok: bool,
        timeframe_confirmation: dict[str, Any] | None,
        news_sentiment: dict[str, Any] | None,
        indicators: dict[str, Any] | None = None,
        fundamentals: dict[str, Any] | None = None,
        df: Any | None = None,
    ) -> dict[str, Any]:
        """
        Extract features for ML model matching training data format

        Training features: rsi_10, ema200, price, price_above_ema200, volume,
        avg_volume_20, volume_ratio, vol_strong, recent_high_20, recent_low_20,
        support_distance_pct, has_hammer, has_bullish_engulfing, has_divergence,
        alignment_score, pe, pb, fundamental_ok

        Returns:
            Dict with feature values
        """

        features = {}

        # Get configurable parameters from config (defaults for backward compatibility)
        rsi_period = self.config.rsi_period if self.config else 10
        volume_lookback = self.config.volume_exhaustion_lookback_daily if self.config else 20
        support_lookback = self.config.support_resistance_lookback_daily if self.config else 20

        # Basic indicators - use configurable RSI period
        rsi_feature_name = f"rsi_{rsi_period}"
        features[rsi_feature_name] = float(rsi_value) if rsi_value is not None else 50.0

        # Also keep 'rsi_10' for backward compatibility if period == 10
        if rsi_period == 10:
            features["rsi_10"] = features[rsi_feature_name]

        # REMOVED REDUNDANT FEATURES (Phase 5 cleanup):
        # - ema200: Redundant with price_above_ema200 (boolean is more useful)
        # - price: Absolute price not useful for ML (only relative metrics matter)
        # - volume: Absolute volume redundant with volume_ratio

        # Keep only the useful boolean version
        features["price_above_ema200"] = 1.0 if is_above_ema200 else 0.0

        # Volume features - use configurable volume lookback
        # Note: We calculate volume internally but don't expose absolute volume as feature
        if df is not None and not df.empty:
            try:
                current_volume = float(df["volume"].iloc[-1])  # For calculation only
                avg_volume_feature_name = f"avg_volume_{volume_lookback}"
                avg_volume = (
                    float(df["volume"].tail(volume_lookback).mean())
                    if len(df) >= volume_lookback
                    else current_volume
                )
                features[avg_volume_feature_name] = avg_volume

                # Always keep 'avg_volume_20' for backward compatibility with trained models
                # Model was trained with avg_volume_20, so we must always provide it
                if volume_lookback == 20:
                    features["avg_volume_20"] = avg_volume
                else:
                    # Calculate avg_volume_20 separately if using different lookback
                    avg_volume_20 = (
                        float(df["volume"].tail(20).mean()) if len(df) >= 20 else current_volume
                    )
                    features["avg_volume_20"] = avg_volume_20

                features["volume_ratio"] = current_volume / avg_volume if avg_volume > 0 else 1.0
            except:
                avg_volume_feature_name = f"avg_volume_{volume_lookback}"
                features[avg_volume_feature_name] = 0.0
                # Always create avg_volume_20 for backward compatibility
                features["avg_volume_20"] = 0.0
                features["volume_ratio"] = 1.0
        else:
            avg_volume_feature_name = f"avg_volume_{volume_lookback}"
            features[avg_volume_feature_name] = 0.0
            # Always create avg_volume_20 for backward compatibility
            features["avg_volume_20"] = 0.0
            features["volume_ratio"] = 1.0

        features["vol_strong"] = 1.0 if vol_strong else 0.0

        # Price action features - use configurable support/resistance lookback
        # Use current price from indicators for calculations
        current_price = float(indicators.get("close", 0)) if indicators else 0.0

        if df is not None and not df.empty:
            try:
                recent_high_feature_name = f"recent_high_{support_lookback}"
                recent_low_feature_name = f"recent_low_{support_lookback}"

                features[recent_high_feature_name] = (
                    float(df["high"].tail(support_lookback).max())
                    if len(df) >= support_lookback
                    else current_price
                )
                features[recent_low_feature_name] = (
                    float(df["low"].tail(support_lookback).min())
                    if len(df) >= support_lookback
                    else current_price
                )

                # Also keep 'recent_high_20' and 'recent_low_20' for backward compatibility if lookback == 20
                if support_lookback == 20:
                    features["recent_high_20"] = features[recent_high_feature_name]
                    features["recent_low_20"] = features[recent_low_feature_name]

                if current_price > 0:
                    features["support_distance_pct"] = (
                        (current_price - features[recent_low_feature_name]) / current_price
                    ) * 100
                else:
                    features["support_distance_pct"] = 0.0

                # EMA9 distance (target proximity) - critical for mean reversion strategy
                if df is not None and "ema9" in df.columns:
                    ema9_value = float(df["ema9"].iloc[-1])
                    if current_price > 0:
                        features["ema9_distance_pct"] = (
                            (ema9_value - current_price) / current_price
                        ) * 100
                    else:
                        features["ema9_distance_pct"] = 0.0
                else:
                    features["ema9_distance_pct"] = 0.0
            except:
                recent_high_feature_name = f"recent_high_{support_lookback}"
                recent_low_feature_name = f"recent_low_{support_lookback}"
                features[recent_high_feature_name] = current_price
                features[recent_low_feature_name] = current_price
                if support_lookback == 20:
                    features["recent_high_20"] = current_price
                    features["recent_low_20"] = current_price
                features["support_distance_pct"] = 0.0
                features["ema9_distance_pct"] = 0.0
        else:
            recent_high_feature_name = f"recent_high_{support_lookback}"
            recent_low_feature_name = f"recent_low_{support_lookback}"
            features[recent_high_feature_name] = current_price
            features[recent_low_feature_name] = current_price
            if support_lookback == 20:
                features["recent_high_20"] = current_price
                features["recent_low_20"] = current_price
            features["support_distance_pct"] = 0.0
            features["ema9_distance_pct"] = 0.0

        # Pattern signals
        features["has_hammer"] = 1.0 if "hammer" in signals else 0.0
        features["has_bullish_engulfing"] = 1.0 if "bullish_engulfing" in signals else 0.0
        features["has_divergence"] = 1.0 if "bullish_divergence" in signals else 0.0

        # Multi-timeframe
        features["alignment_score"] = (
            float(timeframe_confirmation.get("alignment_score", 0))
            if timeframe_confirmation
            else 0.0
        )

        # Fundamentals
        if fundamentals:
            features["pe"] = (
                float(fundamentals.get("pe", 0)) if fundamentals.get("pe") is not None else 0.0
            )
            features["pb"] = (
                float(fundamentals.get("pb", 0)) if fundamentals.get("pb") is not None else 0.0
            )
        else:
            features["pe"] = 0.0
            features["pb"] = 0.0

        features["fundamental_ok"] = 1.0 if fundamental_ok else 0.0

        # ML ENHANCED DIP FEATURES (Phase 5): Add new dip-buying features
        # These features must match training data for ML prediction to work
        if indicators:
            features["dip_depth_from_20d_high_pct"] = float(
                indicators.get("dip_depth_from_20d_high_pct", 0.0)
            )
            features["consecutive_red_days"] = float(indicators.get("consecutive_red_days", 0))
            features["dip_speed_pct_per_day"] = float(indicators.get("dip_speed_pct_per_day", 0.0))
            features["decline_rate_slowing"] = (
                1.0 if indicators.get("decline_rate_slowing", False) else 0.0
            )
            features["volume_green_vs_red_ratio"] = float(
                indicators.get("volume_green_vs_red_ratio", 1.0)
            )
            features["support_hold_count"] = float(indicators.get("support_hold_count", 0))
        else:
            # Defaults if indicators not available
            features["dip_depth_from_20d_high_pct"] = 0.0
            features["consecutive_red_days"] = 0.0
            features["dip_speed_pct_per_day"] = 0.0
            features["decline_rate_slowing"] = 0.0
            features["volume_green_vs_red_ratio"] = 1.0
            features["support_hold_count"] = 0.0

        # Re-entry context features (2025-11-11)
        # For live trading, these are set to defaults (initial entry)
        # During backtest, these may be provided in indicators dict
        features["is_reentry"] = (
            float(indicators.get("is_reentry", 0)) if indicators else 0.0
        )  # False = 0
        features["fill_number"] = (
            float(indicators.get("fill_number", 1)) if indicators else 1.0
        )  # First fill
        features["total_fills_in_position"] = (
            float(indicators.get("total_fills_in_position", 1)) if indicators else 1.0
        )
        features["fill_price_vs_initial_pct"] = (
            float(indicators.get("fill_price_vs_initial_pct", 0.0)) if indicators else 0.0
        )

        # Market regime features (2025-11-11)
        # Adds broader market context (Nifty 50, VIX) for improved ML accuracy
        # Expected improvement: +3-5% accuracy based on backtest analysis
        try:
            from services.market_regime_service import get_market_regime_service

            # Get date from indicators if available (for historical analysis)
            # Otherwise use current date (for live trading)
            analysis_date = indicators.get("analysis_date") if indicators else None

            market_regime_service = get_market_regime_service()
            market_features = market_regime_service.get_market_regime_features(
                date=analysis_date, sector=indicators.get("sector") if indicators else None
            )

            # Add market regime features
            features["nifty_trend"] = market_features["nifty_trend"]
            features["nifty_vs_sma20_pct"] = market_features["nifty_vs_sma20_pct"]
            features["nifty_vs_sma50_pct"] = market_features["nifty_vs_sma50_pct"]
            features["india_vix"] = market_features["india_vix"]
            features["sector_strength"] = market_features["sector_strength"]

            logger.debug(
                f"Added market regime features: trend={market_features['nifty_trend']}, "
                f"vs_sma20={market_features['nifty_vs_sma20_pct']:.2f}%, "
                f"vix={market_features['india_vix']:.1f}"
            )
        except Exception as e:
            logger.warning(f"Could not fetch market regime features: {e}, using defaults")
            # Use default/neutral values if market data unavailable
            features["nifty_trend"] = 0.0  # Neutral
            features["nifty_vs_sma20_pct"] = 0.0
            features["nifty_vs_sma50_pct"] = 0.0
            features["india_vix"] = 20.0  # Average VIX
            features["sector_strength"] = 0.0

        # TIME-BASED FEATURES (2025-11-12): Add temporal patterns
        # For live predictions, use current date unless analysis_date provided
        try:
            from datetime import datetime

            # Get analysis date from indicators if available (for historical), otherwise use today
            if indicators and "analysis_date" in indicators:
                analysis_datetime = pd.to_datetime(indicators["analysis_date"])
            else:
                analysis_datetime = datetime.now()

            features["day_of_week"] = analysis_datetime.weekday()  # 0=Monday, 6=Sunday
            features["is_monday"] = 1.0 if analysis_datetime.weekday() == 0 else 0.0
            features["is_friday"] = 1.0 if analysis_datetime.weekday() == 4 else 0.0
            features["month"] = analysis_datetime.month
            features["quarter"] = (analysis_datetime.month - 1) // 3 + 1
            features["is_q4"] = 1.0 if analysis_datetime.month >= 10 else 0.0
            features["is_month_end"] = 1.0 if analysis_datetime.day >= 25 else 0.0
            features["is_quarter_end"] = (
                1.0
                if (analysis_datetime.month in [3, 6, 9, 12] and analysis_datetime.day >= 25)
                else 0.0
            )

            logger.debug(
                f"Added time features: day={features['day_of_week']}, month={features['month']}"
            )
        except Exception as e:
            logger.warning(f"Could not add time features: {e}, using defaults")
            features["day_of_week"] = 0
            features["is_monday"] = 0.0
            features["is_friday"] = 0.0
            features["month"] = 1
            features["quarter"] = 1
            features["is_q4"] = 0.0
            features["is_month_end"] = 0.0
            features["is_quarter_end"] = 0.0

        # FEATURE INTERACTIONS (2025-11-12): Combine features for stronger signals
        try:
            # Interaction 1: RSI + Volume (panic selling with high volume)
            rsi_feature_name = f"rsi_{self.config.rsi_period if self.config else 10}"
            features["rsi_volume_interaction"] = features.get(
                rsi_feature_name, 50.0
            ) * features.get("volume_ratio", 1.0)

            # Interaction 2: Dip depth + Support distance (deep dip near support)
            features["dip_support_interaction"] = features.get(
                "dip_depth_from_20d_high_pct", 0.0
            ) * features.get("support_distance_pct", 0.0)

            # Interaction 3: Extreme dip with high volume (binary flag)
            features["extreme_dip_high_volume"] = (
                1.0
                if (
                    features.get("dip_depth_from_20d_high_pct", 0.0) > 10.0
                    and features.get("volume_ratio", 1.0) > 1.5
                )
                else 0.0
            )

            # Interaction 4: Bearish market + Deep dip (from backtest analysis)
            # Bearish markets show 19.8% success vs 13.4% in bullish
            features["bearish_deep_dip"] = (
                1.0 if features.get("nifty_trend", 0.0) == -1.0 else 0.0
            ) * features.get("dip_depth_from_20d_high_pct", 0.0)

            logger.debug("Added feature interactions")
        except Exception as e:
            logger.warning(f"Could not add feature interactions: {e}, using defaults")
            features["rsi_volume_interaction"] = 0.0
            features["dip_support_interaction"] = 0.0
            features["extreme_dip_high_volume"] = 0.0
            features["bearish_deep_dip"] = 0.0

        return features

    def _build_ml_justification(self, verdict: str) -> list[str]:
        """Build justification for ML verdict"""
        return [f"ML prediction: {verdict}"]

    def _get_more_conservative_verdict(self, ml_verdict: str, rule_verdict: str) -> str:
        """
        Get the more conservative verdict between ML and rule-based.

        Verdict hierarchy (most aggressive to most conservative):
        - strong_buy (most aggressive)
        - buy
        - watch
        - avoid (most conservative)

        Returns the verdict that is lower in the hierarchy (more conservative).

        Args:
            ml_verdict: ML model's verdict
            rule_verdict: Rule-based verdict

        Returns:
            More conservative verdict
        """
        verdict_hierarchy = {
            "strong_buy": 0,
            "buy": 1,
            "watch": 2,
            "avoid": 3,
        }

        ml_rank = verdict_hierarchy.get(ml_verdict, 2)  # Default to "watch" if unknown
        rule_rank = verdict_hierarchy.get(rule_verdict, 2)  # Default to "watch" if unknown

        # Return the verdict with higher rank (more conservative)
        if ml_rank >= rule_rank:
            return ml_verdict
        else:
            return rule_verdict

    def _get_confidence_aware_combined_verdict(
        self,
        ml_verdict: str,
        ml_confidence: float,
        rule_verdict: str,
        confidence_threshold: float,
    ) -> str:
        """
        Get combined verdict considering ML confidence level.

        Logic:
        - High ML confidence (>= 70%): Trust ML more, but still use more conservative verdict
        - Medium ML confidence (50-70%): Weight both equally, use more conservative
        - Low ML confidence (just above threshold): Trust rules more, but still consider ML if it's more conservative

        Args:
            ml_verdict: ML model's verdict
            ml_confidence: ML confidence (0.0 to 1.0)
            rule_verdict: Rule-based verdict
            confidence_threshold: Minimum confidence threshold

        Returns:
            Combined verdict considering confidence
        """
        verdict_hierarchy = {
            "strong_buy": 0,
            "buy": 1,
            "watch": 2,
            "avoid": 3,
        }

        ml_rank = verdict_hierarchy.get(ml_verdict, 2)  # Default to "watch" if unknown
        rule_rank = verdict_hierarchy.get(rule_verdict, 2)  # Default to "watch" if unknown

        # Validate verdicts - if unknown, use default rank but prefer known verdict
        if ml_verdict not in verdict_hierarchy and rule_verdict in verdict_hierarchy:
            # ML verdict is unknown, rule verdict is known - prefer rule verdict
            return rule_verdict
        elif rule_verdict not in verdict_hierarchy and ml_verdict in verdict_hierarchy:
            # Rule verdict is unknown, ML verdict is known - prefer ML verdict
            return ml_verdict

        # Define confidence bands
        high_confidence = 0.70  # 70% - trust ML more
        medium_confidence = 0.60  # 60% - equal weight
        low_confidence_threshold = 0.50  # 50% - just above minimum threshold

        if ml_confidence >= high_confidence:
            # High confidence: Trust ML more, but still prefer conservative if ML is aggressive
            # If ML is more conservative, use it. If rules are more conservative, still consider ML's high confidence.
            if ml_rank > rule_rank:
                # ML is more conservative - use it (high confidence in being cautious is valuable)
                return ml_verdict
            elif ml_rank < rule_rank:
                # Rules are more conservative, but ML has high confidence
                # Use rules (safety-first), but this is a case where high ML confidence suggests it might be okay
                return rule_verdict
            else:
                # Same level - use ML (high confidence)
                return ml_verdict

        elif ml_confidence >= medium_confidence:
            # Medium confidence (60-70%): Equal weight, use more conservative verdict
            return self._get_more_conservative_verdict(ml_verdict, rule_verdict)

        # Low confidence (50-60%, just above threshold): Trust rules more
        # Only use ML if it's significantly more conservative (safety signal)
        elif ml_rank > rule_rank + 1:
            # ML is much more conservative (e.g., ML=avoid, Rules=buy) - use ML (safety signal)
            return ml_verdict
        elif ml_rank > rule_rank:
            # ML is slightly more conservative - use rules (low ML confidence)
            return rule_verdict
        else:
            # Rules are more conservative or equal - use rules (low ML confidence)
            return rule_verdict

    def predict_verdict_with_confidence(
        self,
        signals: list[str],
        rsi_value: float | None,
        is_above_ema200: bool,
        vol_ok: bool,
        vol_strong: bool,
        fundamental_ok: bool,
        timeframe_confirmation: dict[str, Any] | None,
        news_sentiment: dict[str, Any] | None,
        indicators: dict[str, Any] | None = None,
        fundamentals: dict[str, Any] | None = None,
        df: Any | None = None,
        chart_quality_passed: bool = True,
    ) -> tuple[str | None, float]:
        """
        Predict verdict with confidence score (for testing/comparison)

        Two-Stage Approach:
        1. Stage 1: Chart quality filter (hard filter) - MUST pass before ML
        2. Stage 2: ML model prediction (only if chart quality passed)

        Args:
            signals: List of detected signals
            rsi_value: Current RSI value
            is_above_ema200: Whether price is above EMA200
            vol_ok: Whether volume is OK
            vol_strong: Whether volume is strong
            fundamental_ok: Whether fundamentals are OK
            timeframe_confirmation: Multi-timeframe confirmation data
            news_sentiment: News sentiment data
            indicators: Optional indicators dict
            fundamentals: Optional fundamentals dict
            df: Optional DataFrame
            chart_quality_passed: Whether chart quality check passed (hard filter)

        Returns:
            Tuple of (verdict, confidence) or (None, 0.0) if unavailable or chart quality failed
        """
        # Stage 1: Chart quality filter (hard filter)
        # If chart quality fails, return None (skip ML prediction)
        if not chart_quality_passed:
            logger.debug("ML prediction skipped: Chart quality failed (two-stage filter)")
            return None, 0.0

        if not self.model_loaded:
            return None, 0.0

        try:
            features = self._extract_features(
                signals,
                rsi_value,
                is_above_ema200,
                vol_ok,
                vol_strong,
                fundamental_ok,
                timeframe_confirmation,
                news_sentiment,
                indicators,
                fundamentals,
                df,
            )

            if self.feature_cols:
                feature_vector = [features.get(col, 0) for col in self.feature_cols]
            else:
                feature_vector = list(features.values())

            probabilities = self.model.predict_proba([feature_vector])[0]
            verdicts = self.model.classes_

            verdict_idx = probabilities.argmax()
            verdict = verdicts[verdict_idx]
            confidence = probabilities[verdict_idx]

            return verdict, confidence

        except Exception as e:
            logger.debug(f"ML prediction error: {e}")
            return None, 0.0
