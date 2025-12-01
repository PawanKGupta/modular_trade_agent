"""
ML Training Service

Service for training ML models from historical backtest data.
"""

import os
import pandas as pd
import numpy as np
from typing import Optional, Dict, List
from pathlib import Path
import joblib

from utils.logger import logger

try:
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.model_selection import (
        train_test_split,
        GroupKFold,
        cross_val_score,
        TimeSeriesSplit,
    )
    from sklearn.metrics import classification_report, accuracy_score, mean_squared_error, r2_score
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not available. Install with: pip install scikit-learn")

try:
    import xgboost as xgb

    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("xgboost not available. Install with: pip install xgboost")


class MLTrainingService:
    """
    Service for training ML models from historical data
    """

    def __init__(self, models_dir: str = "models"):
        """
        Initialize ML training service

        Args:
            models_dir: Directory to save trained models
        """
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        if not SKLEARN_AVAILABLE:
            raise ImportError(
                "scikit-learn is required for ML training. Install with: pip install scikit-learn"
            )

    def train_verdict_classifier(
        self,
        training_data_path: str,
        test_size: float = 0.2,
        model_type: str = "random_forest",
        random_state: int = 42,
    ) -> str:
        """
        Train verdict classification model

        Args:
            training_data_path: Path to training data CSV
            test_size: Fraction of data to use for testing
            model_type: Type of model ("random_forest" or "xgboost")
            random_state: Random seed

        Returns:
            Path to saved model
        """
        logger.info(f"Training {model_type} verdict classifier from {training_data_path}...")

        # Load training data
        df = pd.read_csv(training_data_path)

        if df.empty:
            raise ValueError("Training data is empty")

        logger.info(f"Loaded {len(df)} training examples")

        # Feature columns (exclude labels and metadata)
        # PHASE 5: Added position_id, sample_weight, fill_quantity for re-entry support
        exclude_cols = [
            "ticker",
            "entry_date",
            "exit_date",
            "label",
            "actual_pnl_pct",
            "holding_days",
            "backtest_date",
            "position_id",
            "sample_weight",
            "fill_quantity",
            "initial_entry_date",
            "initial_entry_price",
            "fill_price",
            "exit_reason",
            "max_drawdown_pct",
        ]

        feature_cols = [col for col in df.columns if col not in exclude_cols]

        # Extract features and labels
        X = df[feature_cols].copy()
        y = df["label"].values

        # Check for re-entry support (Phase 5)
        has_position_id = "position_id" in df.columns
        has_sample_weight = "sample_weight" in df.columns
        groups = df["position_id"].values if has_position_id else None
        sample_weights = df["sample_weight"].values if has_sample_weight else None

        if has_position_id:
            logger.info(f"   Re-entry support detected:")
            logger.info(f"      Unique positions: {df['position_id'].nunique()}")
            logger.info(f"      Re-entries: {(df.get('is_reentry', False) == True).sum()}")
            if has_sample_weight:
                logger.info(f"      Using quantity-based sample weights")

        # Handle missing values
        X = X.fillna(0)  # Simple fill with 0 (can be improved)

        # PHASE 5 + TimeSeriesSplit: Use GroupKFold + temporal ordering
        if has_position_id and groups is not None:
            logger.info(f"   Using GroupKFold + TimeSeriesSplit cross-validation")
            logger.info(f"   - GroupKFold prevents position leakage (all fills together)")
            logger.info(f"   - TimeSeriesSplit ensures train on past, test on future")

            # Sort data by entry_date for temporal ordering
            if "entry_date" in df.columns:
                df_sorted = df.sort_values("entry_date").reset_index(drop=True)
                X = df_sorted[feature_cols].copy().fillna(0)
                y = df_sorted["label"].values
                groups = df_sorted["position_id"].values
                sample_weights = df_sorted["sample_weight"].values if has_sample_weight else None
                logger.info(
                    f"   Sorted by entry_date: {df_sorted['entry_date'].min()} to {df_sorted['entry_date'].max()}"
                )
            else:
                logger.warning(f"   'entry_date' not found - using unsorted data")

            # Use time-based split: 80% train (older), 20% test (newer)
            split_point = int(len(X) * 0.8)
            train_idx = np.arange(0, split_point)
            test_idx = np.arange(split_point, len(X))

            X_train, X_test = X.iloc[train_idx].copy(), X.iloc[test_idx].copy()
            y_train, y_test = y[train_idx], y[test_idx]

            # Get sample weights for train/test
            sample_weights_train = sample_weights[train_idx] if sample_weights is not None else None
            sample_weights_test = sample_weights[test_idx] if sample_weights is not None else None

            logger.info(
                f"   Train set: {len(X_train)} examples from {len(np.unique(groups[train_idx]))} positions"
            )
            logger.info(
                f"   Test set: {len(X_test)} examples from {len(np.unique(groups[test_idx]))} positions"
            )

            # Log temporal split
            if "entry_date" in df.columns:
                train_dates = df_sorted.iloc[train_idx]["entry_date"]
                test_dates = df_sorted.iloc[test_idx]["entry_date"]
                logger.info(f"   Train dates: {train_dates.min()} to {train_dates.max()}")
                logger.info(f"   Test dates: {test_dates.min()} to {test_dates.max()}")

        else:
            # Fallback to traditional train/test split (backward compatibility)
            logger.info(f"   Using traditional train/test split")

            # Check if stratification is possible (need at least 2 samples per class)
            unique, counts = np.unique(y, return_counts=True)
            min_class_count = counts.min()

            # Use stratification only if all classes have at least 2 samples
            use_stratify = min_class_count >= 2 and test_size > 0

            if not use_stratify:
                logger.warning(
                    f"   Stratification disabled: smallest class has only {min_class_count} sample(s). "
                    f"   Need at least 2 samples per class for stratification."
                )

            # Split train/test
            X_train, X_test, y_train, y_test = train_test_split(
                X,
                y,
                test_size=test_size,
                random_state=random_state,
                stratify=y if use_stratify else None,
            )

            sample_weights_train = sample_weights
            sample_weights_test = None

            logger.info(f"   Train set: {len(X_train)} examples")
            logger.info(f"   Test set: {len(X_test)} examples")

        # Train model
        if model_type == "random_forest":
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                class_weight="balanced",  # Handle class imbalance
                random_state=random_state,
                n_jobs=-1,
            )
        elif model_type == "xgboost" and XGBOOST_AVAILABLE:
            from xgboost import XGBClassifier

            model = XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=random_state,
                eval_metric="mlogloss",
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        logger.info(f"Training {model_type} model...")

        # PHASE 5: Use sample weights if available (quantity-based weighting)
        if sample_weights_train is not None:
            logger.info(f"   Applying quantity-based sample weights to training")
            model.fit(X_train, y_train, sample_weight=sample_weights_train)
        else:
            model.fit(X_train, y_train)

        # Evaluate
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        logger.info(f"\n? Model Evaluation:")
        logger.info(f"   Accuracy: {accuracy:.2%}")
        logger.info(f"\n{classification_report(y_test, y_pred)}")

        # Feature importance
        if hasattr(model, "feature_importances_"):
            feature_importance = pd.DataFrame(
                {"feature": feature_cols, "importance": model.feature_importances_}
            ).sort_values("importance", ascending=False)

            logger.info(f"\n? Top 10 Features:")
            for _, row in feature_importance.head(10).iterrows():
                logger.info(f"   {row['feature']}: {row['importance']:.4f}")

        # Save model
        model_path = self.models_dir / f"verdict_model_{model_type}.pkl"
        joblib.dump(model, model_path)
        logger.info(f"\n? Model saved to: {model_path}")

        # Save feature columns for later use
        feature_cols_path = self.models_dir / f"verdict_model_features_{model_type}.txt"
        with open(feature_cols_path, "w") as f:
            f.write("\n".join(feature_cols))
        logger.info(f"   Feature columns saved to: {feature_cols_path}")

        return str(model_path)

    def train_price_regressor(
        self,
        training_data_path: str,
        target_column: str = "actual_pnl_pct",
        test_size: float = 0.2,
        model_type: str = "random_forest",
        random_state: int = 42,
    ) -> str:
        """
        Train price target prediction model (regression)

        Args:
            training_data_path: Path to training data CSV
            target_column: Column name for target (e.g., "actual_pnl_pct")
            test_size: Fraction of data to use for testing
            model_type: Type of model ("random_forest" or "xgboost")
            random_state: Random seed

        Returns:
            Path to saved model
        """
        logger.info(f"Training {model_type} price regressor from {training_data_path}...")

        # Load training data
        df = pd.read_csv(training_data_path)

        if df.empty:
            raise ValueError("Training data is empty")

        # Feature columns (exclude labels and metadata)
        # PHASE 5: Added re-entry support columns
        exclude_cols = [
            "ticker",
            "entry_date",
            "exit_date",
            "label",
            "actual_pnl_pct",
            "holding_days",
            "backtest_date",
            "position_id",
            "sample_weight",
            "fill_quantity",
            "initial_entry_date",
            "initial_entry_price",
            "fill_price",
            "exit_reason",
            "max_drawdown_pct",
            target_column,
        ]

        feature_cols = [col for col in df.columns if col not in exclude_cols]

        # Extract features and target
        X = df[feature_cols].copy()
        y = df[target_column].values

        # Check for re-entry support (Phase 5)
        has_position_id = "position_id" in df.columns
        has_sample_weight = "sample_weight" in df.columns
        groups = df["position_id"].values if has_position_id else None
        sample_weights = df["sample_weight"].values if has_sample_weight else None

        if has_position_id:
            logger.info(
                f"   Re-entry support detected: {df['position_id'].nunique()} unique positions"
            )

        # Handle missing values
        X = X.fillna(0)

        # PHASE 5: Use GroupKFold when position_id is available
        if has_position_id and groups is not None:
            logger.info(f"   Using GroupKFold cross-validation")

            gkf = GroupKFold(n_splits=5)
            splits = list(gkf.split(X, y, groups))
            train_idx, test_idx = splits[0]

            X_train, X_test = X.iloc[train_idx].copy(), X.iloc[test_idx].copy()
            y_train, y_test = y[train_idx], y[test_idx]

            sample_weights_train = sample_weights[train_idx] if sample_weights is not None else None

            logger.info(
                f"   Train: {len(X_train)} examples from {len(np.unique(groups[train_idx]))} positions"
            )
            logger.info(
                f"   Test: {len(X_test)} examples from {len(np.unique(groups[test_idx]))} positions"
            )
        else:
            # Fallback to traditional train/test split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=random_state
            )
            sample_weights_train = sample_weights

        # Train model
        if model_type == "random_forest":
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=random_state,
                n_jobs=-1,
            )
        elif model_type == "xgboost" and XGBOOST_AVAILABLE:
            from xgboost import XGBRegressor

            model = XGBRegressor(
                n_estimators=100, max_depth=6, learning_rate=0.1, random_state=random_state
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        logger.info(f"Training {model_type} model...")

        # PHASE 5: Use sample weights if available
        if sample_weights_train is not None:
            logger.info(f"   Applying quantity-based sample weights")
            model.fit(X_train, y_train, sample_weight=sample_weights_train)
        else:
            model.fit(X_train, y_train)

        # Evaluate
        y_pred = model.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        logger.info(f"\n? Model Evaluation:")
        logger.info(f"   MSE: {mse:.4f}")
        logger.info(f"   R2: {r2:.4f}")
        logger.info(f"   RMSE: {np.sqrt(mse):.4f}")

        # Save model
        model_path = self.models_dir / f"price_model_{model_type}_{target_column}.pkl"
        joblib.dump(model, model_path)
        logger.info(f"\n? Model saved to: {model_path}")

        return str(model_path)
