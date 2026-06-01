"""
Dip-success scoring service.

Loads a trained pooled classifier and returns calibrated P(net_win) style scores for
current RSI<30 dip setups.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from services.dip_episode_dataset import DipEpisodeParams, _basic_features, _ensure_indicators
from services.ml_dip_feature_manifest import load_dip_feature_manifest
from utils.logger import logger


class MLDipSuccessService:
    """Score current dip setups using a trained dip success classifier."""

    def __init__(self, model_path: str | Path = "models/dip_success_model.pkl") -> None:
        self.model_path = Path(model_path).resolve()
        self.model = None
        self.model_loaded = False
        self.feature_cols: list[str] = []

        if not self.model_path.is_file():
            logger.warning("Dip success model file not found: %s", self.model_path)
            return

        try:
            self.model = joblib.load(self.model_path)
            payload = load_dip_feature_manifest(self.model_path)
            if payload:
                self.feature_cols = list(payload["feature_names"])
            self.model_loaded = True
            logger.info("Dip success model loaded from %s", self.model_path)
        except Exception as e:
            logger.warning("Failed to load dip success model: %s", e)
            self.model = None
            self.model_loaded = False

    def score_current_setup(
        self, df: pd.DataFrame, *, params: DipEpisodeParams | None = None
    ) -> float | None:
        """
        Score the *current* dip setup for a single ticker.

        Args:
            df: Daily candles up to today (must include close; high/low/volume optional).
                Must be sorted ascending by date (or have a sortable date column).
            params: Optional indicator params (RSI period/EMA length).

        Returns:
            Calibrated probability of net win (class 1), or None if model unavailable or
            setup isn't currently RSI<30.
        """
        if not self.model_loaded or self.model is None:
            return None

        p = params or DipEpisodeParams()
        frame = _ensure_indicators(df, params=p)
        frame = frame.copy()
        if "date" in frame.columns:
            frame["__date"] = pd.to_datetime(frame["date"])
            frame = frame.sort_values("__date").reset_index(drop=True)
        else:
            frame = frame.sort_index().reset_index(drop=True)

        if frame.empty:
            return None

        last = frame.iloc[-1]
        rsi = last.get("rsi_10")
        if rsi is None or pd.isna(rsi) or float(rsi) >= p.rsi_entry:
            return None

        features: dict[str, Any] = _basic_features(frame, len(frame) - 1)
        if self.feature_cols:
            vec = [float(features.get(c, 0.0)) for c in self.feature_cols]
        else:
            # Fallback: stable-ish order but prefer manifests.
            vec = [float(v) for v in features.values()]

        try:
            proba = self.model.predict_proba([vec])[0]
            # Binary classifier: class 1 is "success".
            return float(proba[1]) if len(proba) > 1 else float(proba[0])
        except Exception as e:
            logger.warning("Dip success scoring failed: %s", e)
            return None
