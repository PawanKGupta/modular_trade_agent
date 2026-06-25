"""
ML Price Service

ML service for price target and stop loss prediction.
Falls back to rule-based calculations if ML model is unavailable.

Used in production when ``StrategyConfig.ml_price_enabled`` is True and model files exist;
``AnalysisService`` applies predictions at or above ``ml_confidence_threshold``.

Phase 3 Feature - ML Integration
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from services.ml_price_feature_manifest import load_price_feature_manifest
from services.ml_training_metadata import PRICE_TARGET_FEATURE_COLUMNS
from utils.logger import logger

_RECENT_BAR_LOOKBACK = 20
_ATR_PERIOD = 14
_EMA9_SPAN = 9
_VGR_WINDOW = 10
_HIST_VOL_BARS = 20
_HIGH_LOOKBACK_BARS = 252

# The model predicts the MAX favorable excursion (a ceiling). Positions rarely reach the
# full ceiling, so the live target is set to this fraction of it (still floored at EMA9).
# Tune via experiments; lower = more conservative / more often hit.
_TARGET_CAPTURE_FRACTION = 0.6

# Fallback feature order when no manifest is present (legacy pkl without sidecar).
_LEGACY_FEATURE_COLS = list(PRICE_TARGET_FEATURE_COLUMNS)


class MLPriceService:
    """
    ML service for price target and stop loss prediction.

    Uses a trained regression model that predicts ``actual_pnl_pct`` (backtest exit
    return %) from entry-time market features.  Inference converts the predicted %
    back to a price: ``target = entry_price * (1 + predicted_pct / 100)``.

    Falls back to rule-based calculations if the model or manifest is unavailable.
    """

    def __init__(
        self, target_model_path: str | None = None, stop_loss_model_path: str | None = None
    ):
        self.target_model = None
        self.stop_loss_model = None
        self.target_model_loaded = False
        self.stop_loss_model_loaded = False
        self.feature_cols: list[str] = []

        if target_model_path and Path(target_model_path).exists():
            try:
                self.target_model = joblib.load(target_model_path)
                self.target_model_loaded = True
                logger.info("ML price target model loaded from %s", target_model_path)

                resolved = Path(target_model_path).resolve()
                manifest = load_price_feature_manifest(resolved)
                if manifest:
                    n_expected = getattr(self.target_model, "n_features_in_", None)
                    if n_expected is not None and int(n_expected) != len(manifest["feature_names"]):
                        logger.error(
                            "Price manifest lists %d features but estimator expects %d; "
                            "disabling ML price for %s.",
                            len(manifest["feature_names"]),
                            int(n_expected),
                            resolved.name,
                        )
                        self.target_model = None
                        self.target_model_loaded = False
                    else:
                        self.feature_cols = manifest["feature_names"]
                        logger.info(
                            "Loaded %d price feature columns from %s.price_features.json "
                            "(schema v%d)",
                            len(self.feature_cols),
                            resolved.stem,
                            manifest["feature_schema_version"],
                        )
                else:
                    self.feature_cols = _LEGACY_FEATURE_COLS
                    logger.warning(
                        "No price feature manifest beside %s; using legacy column order.",
                        Path(target_model_path).name,
                    )
            except Exception as e:
                logger.warning("Failed to load price target model: %s", e)
        elif target_model_path:
            logger.warning("Price target model file not found: %s", target_model_path)
        else:
            logger.info("No price target model path provided")

        if stop_loss_model_path and Path(stop_loss_model_path).exists():
            try:
                self.stop_loss_model = joblib.load(stop_loss_model_path)
                self.stop_loss_model_loaded = True
                logger.info("ML stop loss model loaded from %s", stop_loss_model_path)
            except Exception as e:
                logger.warning("Failed to load stop loss model: %s", e)
        elif stop_loss_model_path:
            logger.warning("Stop loss model file not found: %s", stop_loss_model_path)
        else:
            logger.info("No stop loss model path provided")

    def predict_target(
        self,
        current_price: float,
        indicators: dict[str, Any],
        timeframe_confirmation: dict[str, Any] | None,
        df: pd.DataFrame,
        rule_based_target: float | None = None,
    ) -> tuple[float, float]:
        """
        Predict price target.

        The model predicts ``max_favorable_pct_20d`` — the best achievable upside (%)
        within ~20 trading days, a ceiling rarely fully reached. The live target takes a
        calibrated fraction of it (``_TARGET_CAPTURE_FRACTION``):
        ``target = current_price * (1 + capture * max(0, predicted_pct) / 100)``.

        If that target is below the rule-based EMA9 target, the EMA9 target is returned
        as a conservative floor.

        Args:
            current_price: Current stock price in ₹.
            indicators: Technical indicators dict (keys: rsi, ema9, ema200, …).
            timeframe_confirmation: Multi-timeframe confirmation data (unused for price).
            df: OHLCV DataFrame with columns close/high/low/volume (lowercase).
            rule_based_target: EMA9/rule-based target price (fallback).

        Returns:
            Tuple of (predicted_target_price, confidence).
        """
        fallback_price = rule_based_target or current_price * 1.10
        if not self.target_model_loaded:
            logger.debug("Price target model not loaded; using rule-based target")
            return fallback_price, 0.5

        try:
            features = self._extract_target_features(current_price, indicators, df)
            if not features:
                logger.debug("Failed to extract price target features")
                return fallback_price, 0.5

            vector = [features.get(col, 0.0) for col in self.feature_cols]
            # Model predicts the *max favorable* upside % (a ceiling rarely fully reached),
            # so we target a calibrated fraction of it rather than the full ceiling.
            predicted_ceiling_pct: float = float(self.target_model.predict([vector])[0])
            predicted_pct = max(0.0, predicted_ceiling_pct) * _TARGET_CAPTURE_FRACTION
            predicted_target = current_price * (1.0 + predicted_pct / 100.0)

            # Conservative gate: if model predicts less upside than EMA9, use EMA9.
            if rule_based_target is not None and predicted_target < rule_based_target:
                logger.debug(
                    "ML price target %.2f < EMA9 target %.2f; using rule-based fallback",
                    predicted_target,
                    rule_based_target,
                )
                return rule_based_target, 0.5

            ema9_pct = (
                (rule_based_target / current_price - 1.0) * 100.0
                if rule_based_target is not None
                else None
            )
            # Confidence grows with the gap between ML prediction and EMA9 target,
            # capped at 0.9 to reflect model uncertainty.
            if ema9_pct is not None and predicted_pct > ema9_pct:
                confidence = min(0.9, 0.65 + (predicted_pct - ema9_pct) * 0.02)
            else:
                confidence = 0.65

            logger.debug(
                "ML price target: %.2f (predicted_pct=%.2f%%, rule-based: %s, confidence: %.0f%%)",
                predicted_target,
                predicted_pct,
                f"{rule_based_target:.2f}" if rule_based_target is not None else "N/A",
                confidence * 100,
            )
            return predicted_target, confidence

        except Exception as e:
            logger.debug("ML price target prediction failed: %s", e)
            return fallback_price, 0.5

    def predict_stop_loss(
        self,
        current_price: float,
        indicators: dict[str, Any],
        df: pd.DataFrame,
        rule_based_stop_loss: float | None = None,
    ) -> tuple[float, float]:
        """
        Predict stop loss level.

        Args:
            current_price: Current stock price.
            indicators: Technical indicators dict.
            df: OHLCV DataFrame.
            rule_based_stop_loss: Fallback rule-based stop loss.

        Returns:
            Tuple of (predicted_stop_loss, confidence).
        """
        if not self.stop_loss_model_loaded:
            logger.debug("Stop loss model not loaded; using rule-based stop loss")
            return rule_based_stop_loss or current_price * 0.92, 0.5

        try:
            features = self._extract_stop_loss_features(current_price, indicators, df)
            if not features:
                logger.debug("Failed to extract stop loss features")
                return rule_based_stop_loss or current_price * 0.92, 0.5

            feature_vector = list(features.values())
            predicted_stop_loss = self.stop_loss_model.predict([feature_vector])[0]

            if rule_based_stop_loss:
                diff_pct = abs(predicted_stop_loss - rule_based_stop_loss) / rule_based_stop_loss
                confidence = max(0.5, 1.0 - diff_pct)
            else:
                confidence = 0.7

            logger.debug(
                "ML stop loss: %.2f (rule-based: %s, confidence: %.0f%%)",
                predicted_stop_loss,
                f"{rule_based_stop_loss:.2f}" if rule_based_stop_loss is not None else "N/A",
                confidence * 100,
            )
            return predicted_stop_loss, confidence

        except Exception as e:
            logger.debug("ML stop loss prediction failed: %s", e)
            return rule_based_stop_loss or current_price * 0.92, 0.5

    def _extract_target_features(
        self,
        current_price: float,
        indicators: dict[str, Any],
        df: pd.DataFrame,
    ) -> dict[str, float]:
        """
        Compute price-target features from live market data.

        All features match the columns in ``PRICE_TARGET_FEATURE_COLUMNS`` used at
        training time (``deploy_price_regressor_model.py``).

        Returns:
            Ordered dict aligned with ``self.feature_cols``, or empty dict on failure.
        """
        try:
            lb = _RECENT_BAR_LOOKBACK
            close = df["close"]

            rsi_10 = float(indicators.get("rsi", 50.0))

            # EMA9 distance: positive when EMA9 is above price (stock in dip).
            ema9 = indicators.get("ema9")
            if ema9 is None and len(df) >= _EMA9_SPAN:
                ema9 = float(close.ewm(span=_EMA9_SPAN, adjust=False).mean().iloc[-1])
            ema9 = float(ema9) if ema9 is not None else current_price
            ema9_distance_pct = (ema9 - current_price) / current_price * 100.0

            volume_ratio = (
                float(df["volume"].iloc[-1] / df["volume"].tail(lb).mean())
                if len(df) >= lb
                else 1.0
            )

            recent_low_20 = float(df["low"].tail(lb).min()) if len(df) >= lb else current_price
            support_distance_pct = (current_price - recent_low_20) / current_price * 100.0

            recent_high_20 = float(df["high"].tail(lb).max()) if len(df) >= lb else current_price
            # Negative: price is below its 20-day high (dip).
            dip_depth_from_20d_high_pct = (current_price - recent_high_20) / recent_high_20 * 100.0

            # Count trailing red candles (close-to-close down days).
            closes = close.values
            consecutive_red_days = 0
            for i in range(len(closes) - 1, 0, -1):
                if closes[i] < closes[i - 1]:
                    consecutive_red_days += 1
                else:
                    break

            # Green/red volume ratio over last _VGR_WINDOW bars.
            if len(df) >= _VGR_WINDOW:
                tail10 = df.tail(_VGR_WINDOW)
                if "open" in df.columns:
                    is_green = tail10["close"] >= tail10["open"]
                else:
                    is_green = tail10["close"] >= tail10["close"].shift(1).fillna(tail10["close"])
                green_vol = float(tail10.loc[is_green, "volume"].mean())
                red_vol = float(tail10.loc[~is_green, "volume"].mean())
                volume_green_vs_red_ratio = green_vol / max(red_vol, 1.0)
            else:
                volume_green_vs_red_ratio = 1.0

            day_of_week = float(datetime.date.today().weekday())

            rsi_volume_interaction = rsi_10 * volume_ratio
            dip_support_interaction = abs(dip_depth_from_20d_high_pct) * support_distance_pct

            # Magnitude features — identical logic to build_historical_dataset.py so the
            # trained model sees the same inputs at serve time.
            high = df["high"]
            low = df["low"]

            atr_window = high.tail(_ATR_PERIOD) - low.tail(_ATR_PERIOD)
            atr_pct_14 = (
                float(atr_window.mean()) / current_price * 100.0
                if len(df) >= 1 and current_price > 0
                else 0.0
            )

            hv = close.tail(_HIST_VOL_BARS + 1).pct_change().std()
            hist_vol_20d = float(hv) * 100.0 if not pd.isna(hv) else 0.0

            def _trailing_return(lookback: int) -> float:
                if len(df) <= lookback:
                    return 0.0
                past = float(close.iloc[-(lookback + 1)])
                return (current_price - past) / past * 100.0 if past > 0 else 0.0

            ret_60d = _trailing_return(60)
            ret_120d = _trailing_return(120)

            high_252 = (
                float(high.tail(_HIGH_LOOKBACK_BARS).max()) if len(df) >= 1 else current_price
            )
            dist_from_high_252d_pct = (
                (current_price - high_252) / high_252 * 100.0 if high_252 > 0 else 0.0
            )

            return {
                "rsi_10": rsi_10,
                "ema9_distance_pct": ema9_distance_pct,
                "volume_ratio": volume_ratio,
                "support_distance_pct": support_distance_pct,
                "dip_depth_from_20d_high_pct": dip_depth_from_20d_high_pct,
                "consecutive_red_days": float(consecutive_red_days),
                "volume_green_vs_red_ratio": volume_green_vs_red_ratio,
                "day_of_week": day_of_week,
                "rsi_volume_interaction": rsi_volume_interaction,
                "dip_support_interaction": dip_support_interaction,
                "atr_pct_14": atr_pct_14,
                "hist_vol_20d": hist_vol_20d,
                "ret_60d": ret_60d,
                "ret_120d": ret_120d,
                "dist_from_high_252d_pct": dist_from_high_252d_pct,
            }

        except Exception as e:
            logger.debug("Feature extraction failed for price target: %s", e)
            return {}

    def _extract_stop_loss_features(
        self, current_price: float, indicators: dict[str, Any], df: pd.DataFrame
    ) -> dict[str, float]:
        """Extract features for stop loss prediction (unchanged from original)."""
        try:
            lb = _RECENT_BAR_LOOKBACK
            recent_low = float(df["low"].tail(lb).min()) if len(df) >= lb else current_price

            if len(df) >= _ATR_PERIOD:
                high_low = df["high"] - df["low"]
                atr = float(high_low.tail(_ATR_PERIOD).mean())
                atr_pct = (atr / current_price) * 100
            else:
                atr_pct = 2.0

            return {
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

        except Exception as e:
            logger.debug("Feature extraction failed for stop loss: %s", e)
            return {}
