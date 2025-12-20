#!/usr/bin/env python3
"""
Test script to verify the feature columns file fix for ML verdict service.

This script:
1. Loads the ML model and checks expected feature count
2. Loads the feature columns file and verifies count
3. Extracts features using the service
4. Creates feature vector and verifies it matches model expectations
5. Attempts a test prediction to confirm it works
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import joblib
import pandas as pd

from services.ml_verdict_service import MLVerdictService


def test_feature_columns_fix():
    """Test that feature columns file matches model expectations"""

    print("=" * 80)
    print("Testing Feature Columns File Fix")
    print("=" * 80)
    print()

    # Step 1: Load the model and check expected features
    model_path = "models/verdict_model_random_forest.pkl"
    if not Path(model_path).exists():
        print(f"❌ ERROR: Model file not found: {model_path}")
        return False

    print(f"✓ Step 1: Loading model from {model_path}")
    try:
        model = joblib.load(model_path)
        print(f"   Model type: {type(model).__name__}")

        # Check model's expected feature count
        if hasattr(model, "n_features_in_"):
            model_expected_count = model.n_features_in_
            print(f"   Model expects {model_expected_count} features")
        else:
            print("   ⚠️  Model doesn't have n_features_in_ attribute")
            model_expected_count = None

        # Check if model has feature names
        if hasattr(model, "feature_names_in_"):
            model_feature_names = list(model.feature_names_in_)
            print(f"   Model has feature_names_in_ with {len(model_feature_names)} features")
            print(f"   First 5 features: {model_feature_names[:5]}")
            print(f"   Last 5 features: {model_feature_names[-5:]}")
        else:
            print("   ⚠️  Model doesn't have feature_names_in_ attribute")
            model_feature_names = None

    except Exception as e:
        print(f"❌ ERROR: Failed to load model: {e}")
        return False

    print()

    # Step 2: Load feature columns file
    feature_file_path = "models/verdict_model_features_enhanced.txt"
    if not Path(feature_file_path).exists():
        print(f"❌ ERROR: Feature columns file not found: {feature_file_path}")
        return False

    print(f"✓ Step 2: Loading feature columns from {feature_file_path}")
    try:
        with open(feature_file_path) as f:
            file_feature_cols = [line.strip() for line in f if line.strip()]
        print(f"   File contains {len(file_feature_cols)} features")
        print(f"   First 5 features: {file_feature_cols[:5]}")
        print(f"   Last 5 features: {file_feature_cols[-5:]}")
    except Exception as e:
        print(f"❌ ERROR: Failed to load feature columns file: {e}")
        return False

    print()

    # Step 3: Verify counts match
    print("✓ Step 3: Verifying feature counts match")
    if model_expected_count is not None:
        if len(file_feature_cols) == model_expected_count:
            print(f"   ✓ Feature count matches: {len(file_feature_cols)} == {model_expected_count}")
        else:
            print(
                f"   ❌ Feature count MISMATCH: file has {len(file_feature_cols)}, model expects {model_expected_count}"
            )
            return False
    else:
        print("   ⚠️  Cannot verify count (model doesn't have n_features_in_)")

    # Verify feature names match if available
    if model_feature_names is not None:
        if len(file_feature_cols) == len(model_feature_names):
            # Check if order matches
            if file_feature_cols == model_feature_names:
                print("   ✓ Feature names and order match perfectly!")
            else:
                # Check which features differ
                file_set = set(file_feature_cols)
                model_set = set(model_feature_names)
                missing_in_file = model_set - file_set
                extra_in_file = file_set - model_set

                if missing_in_file:
                    print(f"   ⚠️  Features in model but not in file: {missing_in_file}")
                if extra_in_file:
                    print(f"   ⚠️  Features in file but not in model: {extra_in_file}")

                # Check order differences
                order_mismatches = []
                for i, (file_feat, model_feat) in enumerate(
                    zip(file_feature_cols, model_feature_names)
                ):
                    if file_feat != model_feat:
                        order_mismatches.append((i, file_feat, model_feat))

                if order_mismatches:
                    print(f"   ⚠️  Feature order differs at {len(order_mismatches)} positions")
                    print(f"   First 3 mismatches: {order_mismatches[:3]}")
                else:
                    print("   ✓ All features present (order may differ but that's OK)")
        else:
            print(
                f"   ❌ Feature count mismatch: file={len(file_feature_cols)}, model={len(model_feature_names)}"
            )
            return False

    print()

    # Step 4: Initialize MLVerdictService and test feature extraction
    print("✓ Step 4: Testing MLVerdictService initialization")
    try:
        service = MLVerdictService(model_path=model_path)
        if not service.model_loaded:
            print("   ❌ ERROR: Service failed to load model")
            return False

        print("   ✓ Service loaded model successfully")
        print(f"   ✓ Service loaded {len(service.feature_cols)} feature columns")

        # Verify service loaded the correct features
        if len(service.feature_cols) == len(file_feature_cols):
            if service.feature_cols == file_feature_cols:
                print("   ✓ Service feature columns match file perfectly")
            else:
                print(
                    "   ⚠️  Service feature columns differ from file (may be using model's feature_names_in_)"
                )

    except Exception as e:
        print(f"   ❌ ERROR: Failed to initialize service: {e}")
        import traceback

        traceback.print_exc()
        return False

    print()

    # Step 5: Test feature extraction
    print("✓ Step 5: Testing feature extraction")
    try:
        # Create sample data for feature extraction (need at least 20 rows for volume calculations)
        import numpy as np

        np.random.seed(42)
        dates = pd.date_range(end=pd.Timestamp.now(), periods=25, freq="D")
        sample_df = pd.DataFrame(
            {
                "close": 100 + np.random.randn(25).cumsum(),
                "high": 102 + np.random.randn(25).cumsum(),
                "low": 98 + np.random.randn(25).cumsum(),
                "volume": 1000000 + np.random.randint(-200000, 200000, 25),
                "ema9": 100 + np.random.randn(25).cumsum() * 0.5,
                "ema200": 95 + np.random.randn(25).cumsum() * 0.3,
            },
            index=dates,
        )

        features = service._extract_features(
            signals=["hammer"],
            rsi_value=25.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=True,
            fundamental_ok=True,
            timeframe_confirmation={"alignment_score": 0.75},
            news_sentiment=None,
            indicators={
                "close": 97.0,
                "dip_depth_from_20d_high_pct": 5.0,
                "consecutive_red_days": 3,
                "dip_speed_pct_per_day": 1.0,
                "decline_rate_slowing": True,
                "volume_green_vs_red_ratio": 0.8,
                "support_hold_count": 2,
            },
            fundamentals={"pe": 20.0, "pb": 3.0},
            df=sample_df,
        )

        print(f"   ✓ Extracted {len(features)} features")

        # Check if all required features are present
        missing_features = set(service.feature_cols) - set(features.keys())
        if missing_features:
            print(f"   ❌ Missing features in extraction: {missing_features}")
            return False
        else:
            print("   ✓ All required features present in extraction")

    except Exception as e:
        print(f"   ❌ ERROR: Feature extraction failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    print()

    # Step 6: Test feature vector creation and prediction
    print("✓ Step 6: Testing feature vector creation and prediction")
    try:
        # Create feature vector
        feature_vector = [features.get(col, 0) for col in service.feature_cols]

        print(f"   ✓ Created feature vector with {len(feature_vector)} values")

        # Verify count matches model expectations
        if model_expected_count is not None:
            if len(feature_vector) == model_expected_count:
                print(
                    f"   ✓ Feature vector count matches model: {len(feature_vector)} == {model_expected_count}"
                )
            else:
                print(
                    f"   ❌ Feature vector count mismatch: {len(feature_vector)} != {model_expected_count}"
                )
                return False

        # Try to make a prediction
        probabilities = service.model.predict_proba([feature_vector])[0]
        verdicts = service.model.classes_
        verdict_idx = probabilities.argmax()
        verdict = verdicts[verdict_idx]
        confidence = probabilities[verdict_idx]

        print("   ✓ Prediction successful!")
        print(f"   ✓ Verdict: {verdict} (confidence: {confidence:.2%})")
        print(f"   ✓ Probabilities: {dict(zip(verdicts, probabilities))}")

    except ValueError as e:
        if "features" in str(e).lower():
            print("   ❌ ERROR: Feature count mismatch during prediction!")
            print(f"   Error: {e}")
            return False
        else:
            raise
    except Exception as e:
        print(f"   ❌ ERROR: Prediction failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    print()
    print("=" * 80)
    print("✅ ALL TESTS PASSED! Feature columns file fix is working correctly.")
    print("=" * 80)
    return True


if __name__ == "__main__":
    success = test_feature_columns_fix()
    sys.exit(0 if success else 1)
