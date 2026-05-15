"""
ML Price Service

ML service for price target and stop loss prediction.
Falls back to rule-based calculations if ML model is unavailable.

Used in production when ``StrategyConfig.ml_price_enabled`` is True and model files exist;
``AnalysisService`` applies predictions at or above ``ml_confidence_threshold``.

Phase 3 Feature - ML Integration
"""

from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from utils.logger import logger

_RECENT_BAR_LOOKBACK = 20
_ATR_PERIOD = 14


class MLPriceService:
    """
    ML service for price target and stop loss prediction

    Uses trained regression models to predict optimal price targets and stop losses.
    Falls back to rule-based calculations if models are unavailable.
    """

    def __init__(
        self, target_model_path: str | None = None, stop_loss_model_path: str | None = None
    ):
        """
        Initialize ML price service

        Args:
            target_model_path: Path to trained price target model
            stop_loss_model_path: Path to trained stop loss model
        """
        self.target_model = None
        self.stop_loss_model = None
        self.target_model_loaded = False
        self.stop_loss_model_loaded = False

        # Load target model
        if target_model_path and Path(target_model_path).exists():
            try:
                self.target_model = joblib.load(target_model_path)
                self.target_model_loaded = True
                logger.info(f"? ML price target model loaded from {target_model_path}")
            except Exception as e:
                logger.warning(f"[WARN]? Failed to load price target model: {e}")
        elif target_model_path:
            logger.warning(f"[WARN]? Price target model file not found: {target_model_path}")
        else:
            logger.info("i? No price target model path provided")

        # Load stop loss model
        if stop_loss_model_path and Path(stop_loss_model_path).exists():
            try:
                self.stop_loss_model = joblib.load(stop_loss_model_path)
                self.stop_loss_model_loaded = True
                logger.info(f"? ML stop loss model loaded from {stop_loss_model_path}")
            except Exception as e:
                logger.warning(f"[WARN]? Failed to load stop loss model: {e}")
        elif stop_loss_model_path:
            logger.warning(f"[WARN]? Stop loss model file not found: {stop_loss_model_path}")
        else:
            logger.info("i? No stop loss model path provided")

    def predict_target(
        self,
        current_price: float,
        indicators: dict[str, Any],
        timeframe_confirmation: dict[str, Any] | None,
        df: pd.DataFrame,
        rule_based_target: float | None = None,
    ) -> tuple[float, float]:
        """
        Predict price target

        Args:
            current_price: Current stock price
            indicators: Technical indicators dict
            timeframe_confirmation: Multi-timeframe confirmation data
            df: OHLCV DataFrame
            rule_based_target: Fallback rule-based target

        Returns:
            Tuple of (predicted_target, confidence)
            Falls back to rule_based_target if ML unavailable
        """
        if not self.target_model_loaded:
            logger.debug("Target model not loaded, using rule-based target")
            return rule_based_target or current_price * 1.10, 0.5

        try:
            # Extract features for target prediction
            features = self._extract_target_features(
                current_price, indicators, timeframe_confirmation, df
            )

            if not features:
                logger.debug("Failed to extract features for target prediction")
                return rule_based_target or current_price * 1.10, 0.5

            # Create feature vector
            feature_vector = list(features.values())

            # Predict target price
            predicted_target = self.target_model.predict([feature_vector])[0]

            # Calculate confidence (simplified - based on prediction vs rule-based)
            if rule_based_target:
                diff_pct = abs(predicted_target - rule_based_target) / rule_based_target
                confidence = max(0.5, 1.0 - diff_pct)  # Lower confidence if predictions differ
            else:
                confidence = 0.7  # Default confidence

            rule_txt = f"{rule_based_target:.2f}" if rule_based_target is not None else "N/A"
            logger.debug(
                f"ML target prediction: {predicted_target:.2f} "
                f"(rule-based: {rule_txt}, confidence: {confidence:.1%})"
            )

            return predicted_target, confidence

        except Exception as e:
            logger.debug(f"ML target prediction failed: {e}")
            return rule_based_target or current_price * 1.10, 0.5

    def predict_stop_loss(
        self,
        current_price: float,
        indicators: dict[str, Any],
        df: pd.DataFrame,
        rule_based_stop_loss: float | None = None,
    ) -> tuple[float, float]:
        """
        Predict stop loss level

        Args:
            current_price: Current stock price
            indicators: Technical indicators dict
            df: OHLCV DataFrame
            rule_based_stop_loss: Fallback rule-based stop loss

        Returns:
            Tuple of (predicted_stop_loss, confidence)
            Falls back to rule_based_stop_loss if ML unavailable
        """
        if not self.stop_loss_model_loaded:
            logger.debug("Stop loss model not loaded, using rule-based stop loss")
            return rule_based_stop_loss or current_price * 0.92, 0.5

        try:
            # Extract features for stop loss prediction
            features = self._extract_stop_loss_features(current_price, indicators, df)

            if not features:
                logger.debug("Failed to extract features for stop loss prediction")
                return rule_based_stop_loss or current_price * 0.92, 0.5

            # Create feature vector
            feature_vector = list(features.values())

            # Predict stop loss
            predicted_stop_loss = self.stop_loss_model.predict([feature_vector])[0]

            # Calculate confidence
            if rule_based_stop_loss:
                diff_pct = abs(predicted_stop_loss - rule_based_stop_loss) / rule_based_stop_loss
                confidence = max(0.5, 1.0 - diff_pct)
            else:
                confidence = 0.7

            rule_stop_txt = (
                f"{rule_based_stop_loss:.2f}" if rule_based_stop_loss is not None else "N/A"
            )
            logger.debug(
                f"ML stop loss prediction: {predicted_stop_loss:.2f} "
                f"(rule-based: {rule_stop_txt}, confidence: {confidence:.1%})"
            )

            return predicted_stop_loss, confidence

        except Exception as e:
            logger.debug(f"ML stop loss prediction failed: {e}")
            return rule_based_stop_loss or current_price * 0.92, 0.5

    def _extract_target_features(
        self,
        current_price: float,
        indicators: dict[str, Any],
        timeframe_confirmation: dict[str, Any] | None,
        df: pd.DataFrame,
    ) -> dict[str, float]:
        """
        Extract features for price target prediction

        Returns:
            Dict with feature values
        """
        try:
            # Get recent extremes
            lb = _RECENT_BAR_LOOKBACK
            recent_high = float(df["high"].tail(lb).max()) if len(df) >= lb else current_price
            recent_low = float(df["low"].tail(lb).min()) if len(df) >= lb else current_price

            # Calculate volatility (standard deviation of returns)
            if len(df) >= lb:
                returns = df["close"].pct_change().tail(lb)
                volatility = float(returns.std() * 100)  # Percentage
            else:
                volatility = 2.0  # Default

            # Calculate momentum (20-day price change)
            if len(df) >= lb:
                momentum = float(
                    (current_price - df["close"].iloc[-lb]) / df["close"].iloc[-lb] * 100
                )
            else:
                momentum = 0.0

            features = {
                "current_price": current_price,
                "rsi_10": float(indicators.get("rsi", 50.0)),
                "ema200": float(indicators.get("ema200", current_price)),
                "recent_high": recent_high,
                "recent_low": recent_low,
                "volume_ratio": (
                    float(df["volume"].iloc[-1] / df["volume"].tail(lb).mean())
                    if len(df) >= lb
                    else 1.0
                ),
                "alignment_score": (
                    float(timeframe_confirmation.get("alignment_score", 0))
                    if timeframe_confirmation
                    else 0.0
                ),
                "volatility": volatility,
                "momentum": momentum,
                "resistance_distance": float((recent_high - current_price) / current_price * 100),
            }

            return features

        except Exception as e:
            logger.debug(f"Feature extraction failed for target: {e}")
            return {}

    def _extract_stop_loss_features(
        self, current_price: float, indicators: dict[str, Any], df: pd.DataFrame
    ) -> dict[str, float]:
        """
        Extract features for stop loss prediction

        Returns:
            Dict with feature values
        """
        try:
            # Get recent low (support)
            lb = _RECENT_BAR_LOOKBACK
            recent_low = float(df["low"].tail(lb).min()) if len(df) >= lb else current_price

            # Calculate ATR (Average True Range) as volatility measure
            if len(df) >= _ATR_PERIOD:
                high_low = df["high"] - df["low"]
                atr = float(high_low.tail(_ATR_PERIOD).mean())
                atr_pct = (atr / current_price) * 100
            else:
                atr_pct = 2.0

            features = {
                "current_price": current_price,
                "recent_low": recent_low,
                "support_distance_pct": float((current_price - recent_low) / current_price * 100),
                "atr_pct": atr_pct,
                "rsi_10": float(indicators.get("rsi", 50.0)),
                "volume_ratio": (
                    float(df["volume"].iloc[-1] / df["volume"].tail(lb).mean())
                    if len(df) >= lb
                    else 1.0
                ),
            }

            return features

        except Exception as e:
            logger.debug(f"Feature extraction failed for stop loss: {e}")
            return {}
