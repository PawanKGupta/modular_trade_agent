"""Shared calibrated RF wrapper used by both training and inference.

Kept in a stable importable module so that joblib-pickled models can be
deserialized by any process (uvicorn, cron, CLI) without requiring the
training script to be importable as __main__.
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression


class ProductionCalibratedRF:
    """RF + Platt scaling wrapper compatible with MLVerdictService.

    classes_ = ["avoid", "buy"] so MLVerdictService maps index 0 → "avoid",
    index 1 → "buy".
    """

    def __init__(self, rf: RandomForestClassifier, platt: LogisticRegression) -> None:
        self.rf = rf
        self.platt = platt
        self.classes_ = np.array(["avoid", "buy"])

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        raw = self.rf.predict_proba(X)[:, 1].reshape(-1, 1)
        p_buy = self.platt.predict_proba(raw)[:, 1]
        return np.column_stack([1 - p_buy, p_buy])
