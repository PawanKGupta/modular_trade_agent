"""
ML Training Service

Service for training ML models from historical backtest data.
"""

from pathlib import Path
from typing import Any, cast

import joblib
import numpy as np
import pandas as pd

from services.ml_dip_feature_manifest import write_dip_feature_manifest
from services.ml_training_metadata import (
    dip_classifier_exclude_columns,
    price_regressor_exclude_columns,
    select_training_feature_columns,
    verdict_classifier_exclude_columns,
)
from services.ml_verdict_feature_manifest import write_verdict_feature_manifest
from utils.logger import logger

try:
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.metrics import accuracy_score, classification_report, mean_squared_error, r2_score
    from sklearn.model_selection import GroupKFold, train_test_split

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


def _coerce_hp(raw: dict | None, key: str, caster, default):  # noqa: ANN001
    if not raw or key not in raw:
        return default
    try:
        return caster(raw[key])
    except (TypeError, ValueError):
        return default


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
        training_data_path: str | None = None,
        test_size: float = 0.2,
        model_type: str = "random_forest",
        random_state: int = 42,
        *,
        df: pd.DataFrame | None = None,
        model_save_path: str | Path | None = None,
        hyperparameters: dict[str, Any] | None = None,
    ) -> tuple[str, float]:
        """
        Train verdict classification model.

        Args:
            training_data_path: Path to training CSV (required if df is omitted).
            test_size: Holdout fraction when not using positional group splitting.
            model_type: Algorithm key: random_forest, xgboost, logistic_regression.
            random_state: RNG seed for sklearn estimators.
            df: Optional in-memory dataframe (skips CSV read).
            model_save_path: Target ``.pkl`` path (defaults to legacy ``models/`` layout).
            hyperparameters: Optional overrides (e.g. n_estimators, max_depth).

        Returns:
            Tuple of filesystem path to the saved pickled model and accuracy on held-out rows.
        """
        src = training_data_path or "(dataframe)"
        logger.info(f"Training {model_type} verdict classifier from {src}...")

        hp = hyperparameters or {}
        # Load training data
        if df is not None:
            frame = df.copy()
        elif training_data_path:
            frame = pd.read_csv(training_data_path)
        else:
            raise ValueError("train_verdict_classifier requires training_data_path or df")

        if frame.empty:
            raise ValueError("Training data is empty")

        df = cast(pd.DataFrame, frame)
        logger.info(f"Loaded {len(df)} training examples")

        exclude_cols = verdict_classifier_exclude_columns()
        feature_cols = select_training_feature_columns(df, exclude_cols)

        # Extract features and labels
        X = df[feature_cols].copy()
        y = df["label"].values

        # Check for re-entry support (Phase 5)
        has_position_id = "position_id" in df.columns
        has_sample_weight = "sample_weight" in df.columns
        groups = df["position_id"].values if has_position_id else None
        sample_weights = df["sample_weight"].values if has_sample_weight else None

        if has_position_id:
            logger.info("   Re-entry support detected:")
            logger.info(f"      Unique positions: {df['position_id'].nunique()}")
            logger.info(f"      Re-entries: {(df.get('is_reentry', False) == True).sum()}")
            if has_sample_weight:
                logger.info("      Using quantity-based sample weights")

        # Handle missing values
        X = X.fillna(0)  # Simple fill with 0 (can be improved)

        # PHASE 5 + TimeSeriesSplit: Use GroupKFold + temporal ordering
        if has_position_id and groups is not None:
            logger.info("   Using GroupKFold + TimeSeriesSplit cross-validation")
            logger.info("   - GroupKFold prevents position leakage (all fills together)")
            logger.info("   - TimeSeriesSplit ensures train on past, test on future")

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
                logger.warning("   'entry_date' not found - using unsorted data")

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
            logger.info("   Using traditional train/test split")

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
                n_estimators=_coerce_hp(hp, "n_estimators", int, 100),
                max_depth=_coerce_hp(hp, "max_depth", int, 10),
                min_samples_split=_coerce_hp(hp, "min_samples_split", int, 5),
                min_samples_leaf=_coerce_hp(hp, "min_samples_leaf", int, 2),
                class_weight="balanced",  # Handle class imbalance
                random_state=random_state,
                n_jobs=-1,
            )
        elif model_type == "xgboost" and XGBOOST_AVAILABLE:
            from xgboost import XGBClassifier

            model = XGBClassifier(
                n_estimators=_coerce_hp(hp, "n_estimators", int, 100),
                max_depth=_coerce_hp(hp, "max_depth", int, 6),
                learning_rate=_coerce_hp(hp, "learning_rate", float, 0.1),
                random_state=random_state,
                eval_metric="mlogloss",
            )
        elif model_type == "logistic_regression":
            from sklearn.linear_model import LogisticRegression

            model = LogisticRegression(
                C=_coerce_hp(hp, "C", float, 1.0),
                max_iter=_coerce_hp(hp, "max_iter", int, 500),
                class_weight="balanced",
                solver="lbfgs",
                random_state=random_state,
                n_jobs=-1,
                multi_class="auto",
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        logger.info(f"Training {model_type} model...")

        # PHASE 5: Use sample weights if available (quantity-based weighting)
        if sample_weights_train is not None:
            logger.info("   Applying quantity-based sample weights to training")
            model.fit(X_train, y_train, sample_weight=sample_weights_train)
        else:
            model.fit(X_train, y_train)

        # Evaluate
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        logger.info("\n? Model Evaluation:")
        logger.info(f"   Accuracy: {accuracy:.2%}")
        logger.info(f"\n{classification_report(y_test, y_pred)}")

        # Feature importance
        if hasattr(model, "feature_importances_"):
            feature_importance = pd.DataFrame(
                {"feature": feature_cols, "importance": model.feature_importances_}
            ).sort_values("importance", ascending=False)

            logger.info("\n? Top 10 Features:")
            for _, row in feature_importance.head(10).iterrows():
                logger.info(f"   {row['feature']}: {row['importance']:.4f}")

        # Save model + feature manifest (paired by pickle stem).
        model_path = (
            Path(model_save_path).resolve()
            if model_save_path
            else self.models_dir / f"verdict_model_{model_type}.pkl"
        )
        model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, model_path)
        logger.info(f"\n? Model saved to: {model_path}")

        feature_cols_path = model_path.parent / f"{model_path.stem}_features.txt"
        feature_cols_path.write_text("\n".join(feature_cols), encoding="utf-8")
        logger.info(f"   Feature columns saved to: {feature_cols_path}")

        write_verdict_feature_manifest(model_path, feature_cols)

        return str(model_path), float(accuracy)

    def train_dip_success_classifier(
        self,
        training_data_path: str | None = None,
        *,
        df: pd.DataFrame | None = None,
        label_column: str = "net_win",
        test_size: float = 0.2,
        random_state: int = 42,
        model_save_path: str | Path | None = None,
        hyperparameters: dict[str, Any] | None = None,
        calibrate: bool = True,
    ) -> tuple[str, float]:
        """
        Train a pooled dip-success binary classifier and (optionally) calibrate probabilities.

        The training dataset should be generated from dip episodes (see
        :mod:`services.dip_episode_dataset`) and contain:

        - metadata columns (ticker, entry_date, exit_date, n_adds, pnl_pct)
        - a binary label column (default: ``net_win``)
        - numeric feature columns (e.g. rsi_10, dip_depth_from_20d_high_pct, volume_ratio...)

        Args:
            training_data_path: CSV path (required if df is omitted).
            df: Optional in-memory dataframe (skips CSV read).
            label_column: Binary label in {0,1}. Recommended: net_win (>= +1% PnL after costs).
            test_size: Holdout fraction (time-split when entry_date exists; otherwise random split).
            random_state: RNG seed.
            model_save_path: Target ``.pkl`` path (defaults to models/dip_success_model.pkl).
            hyperparameters: Optional RandomForest overrides.
            calibrate: If True, wrap the fitted estimator in CalibratedClassifierCV (sigmoid).

        Returns:
            Tuple of pickled model filesystem path and accuracy on held-out samples.
        """
        src = training_data_path or "(dataframe)"
        logger.info("Training dip success classifier from %s (label=%s)...", src, label_column)

        hp = hyperparameters or {}
        if df is not None:
            frame = df.copy()
        elif training_data_path:
            frame = pd.read_csv(training_data_path)
        else:
            raise ValueError("train_dip_success_classifier requires training_data_path or df")

        if frame.empty:
            raise ValueError("Training data is empty")
        if label_column not in frame.columns:
            raise ValueError(f"Missing label column '{label_column}'")

        df = cast(pd.DataFrame, frame)
        logger.info("Loaded %s dip episode rows", len(df))

        exclude_cols = dip_classifier_exclude_columns()
        feature_cols = select_training_feature_columns(df, exclude_cols)

        X = df[feature_cols].copy().fillna(0.0)
        y = df[label_column].astype(int).values

        # Time-aware holdout when entry_date exists.
        if "entry_date" in df.columns:
            order = pd.to_datetime(df["entry_date"], errors="coerce")
            valid = order.notna()
            df_ord = df.loc[valid].copy()
            X = df_ord[feature_cols].copy().fillna(0.0)
            y = df_ord[label_column].astype(int).values
            order = pd.to_datetime(df_ord["entry_date"])
            idx = np.argsort(order.values)
            X = X.iloc[idx].reset_index(drop=True)
            y = y[idx]
            split = int((1.0 - test_size) * len(X))
            X_train, X_test = X.iloc[:split], X.iloc[split:]
            y_train, y_test = y[:split], y[split:]
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X,
                y,
                test_size=test_size,
                random_state=random_state,
                stratify=y if len(set(y)) > 1 else None,
            )

        rf = RandomForestClassifier(
            n_estimators=_coerce_hp(hp, "n_estimators", int, 400),
            max_depth=_coerce_hp(hp, "max_depth", int, None),
            min_samples_split=_coerce_hp(hp, "min_samples_split", int, 2),
            min_samples_leaf=_coerce_hp(hp, "min_samples_leaf", int, 1),
            class_weight=_coerce_hp(hp, "class_weight", str, "balanced"),
            random_state=random_state,
            n_jobs=-1,
        )
        rf.fit(X_train, y_train)

        model = rf
        if calibrate:
            from sklearn.calibration import CalibratedClassifierCV  # noqa: PLC0415

            model = CalibratedClassifierCV(rf, method="sigmoid", cv=3)
            model.fit(X_train, y_train)

        preds = model.predict(X_test) if len(X_test) else []
        acc = accuracy_score(y_test, preds) if len(y_test) else 0.0
        logger.info("Dip success holdout accuracy: %.3f (%s rows)", acc, len(y_test))

        model_path = (
            Path(model_save_path).resolve()
            if model_save_path
            else self.models_dir / "dip_success_model.pkl"
        )
        model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, model_path)
        logger.info("Dip model saved to: %s", model_path)

        write_dip_feature_manifest(model_path, feature_cols)
        return str(model_path), float(acc)

    def train_price_regressor(
        self,
        training_data_path: str | None = None,
        target_column: str = "actual_pnl_pct",
        test_size: float = 0.2,
        model_type: str = "random_forest",
        random_state: int = 42,
        *,
        df: pd.DataFrame | None = None,
        model_save_path: str | Path | None = None,
        hyperparameters: dict[str, Any] | None = None,
    ) -> tuple[str, float]:
        """
        Train price target prediction model (regression).

        Returns:
            Tuple of pickled model filesystem path and R² on held-out samples.
        """
        src = training_data_path or "(dataframe)"
        logger.info(f"Training {model_type} price regressor from {src}...")

        hp = hyperparameters or {}
        # Load training data
        if df is not None:
            frame = df.copy()
        elif training_data_path:
            frame = pd.read_csv(training_data_path)
        else:
            raise ValueError("train_price_regressor requires training_data_path or df")

        if frame.empty:
            raise ValueError("Training data is empty")

        df = cast(pd.DataFrame, frame)

        exclude_cols = price_regressor_exclude_columns(target_column=target_column)
        feature_cols = select_training_feature_columns(df, exclude_cols)

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
            logger.info("   Using GroupKFold cross-validation")

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
                n_estimators=_coerce_hp(hp, "n_estimators", int, 100),
                max_depth=_coerce_hp(hp, "max_depth", int, 10),
                min_samples_split=_coerce_hp(hp, "min_samples_split", int, 5),
                min_samples_leaf=_coerce_hp(hp, "min_samples_leaf", int, 2),
                random_state=random_state,
                n_jobs=-1,
            )
        elif model_type == "xgboost" and XGBOOST_AVAILABLE:
            from xgboost import XGBRegressor

            model = XGBRegressor(
                n_estimators=_coerce_hp(hp, "n_estimators", int, 100),
                max_depth=_coerce_hp(hp, "max_depth", int, 6),
                learning_rate=_coerce_hp(hp, "learning_rate", float, 0.1),
                random_state=random_state,
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        logger.info(f"Training {model_type} model...")

        # PHASE 5: Use sample weights if available
        if sample_weights_train is not None:
            logger.info("   Applying quantity-based sample weights")
            model.fit(X_train, y_train, sample_weight=sample_weights_train)
        else:
            model.fit(X_train, y_train)

        # Evaluate
        y_pred = model.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        logger.info("\n? Model Evaluation:")
        logger.info(f"   MSE: {mse:.4f}")
        logger.info(f"   R2: {r2:.4f}")
        logger.info(f"   RMSE: {np.sqrt(mse):.4f}")

        model_path = (
            Path(model_save_path).resolve()
            if model_save_path
            else self.models_dir / f"price_model_{model_type}_{target_column}.pkl"
        )
        model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, model_path)
        logger.info(f"\n? Model saved to: {model_path}")

        return str(model_path), float(r2)
