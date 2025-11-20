#!/usr/bin/env python3
"""
Unit tests for EMA9 distance feature in MLVerdictService

Tests that ema9_distance_pct is correctly extracted during live predictions.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from services.ml_verdict_service import MLVerdictService


class TestEMA9DistanceFeature:
    """Test EMA9 distance feature extraction in ML predictions"""

    def test_ema9_distance_calculated_when_available(self):
        """Test that EMA9 distance is calculated when EMA9 is in dataframe"""
        # Create mock dataframe with EMA9
        df = pd.DataFrame(
            {
                "close": [100.0, 105.0, 110.0],
                "high": [102.0, 107.0, 112.0],
                "low": [98.0, 103.0, 108.0],
                "volume": [1000000, 1100000, 1200000],
                "rsi10": [25.0, 28.0, 30.0],
                "ema9": [108.0, 109.0, 115.0],  # EMA9 present
                "ema200": [95.0, 96.0, 97.0],
            }
        )

        ml_service = MLVerdictService()

        # Extract features
        features = ml_service._extract_features(
            signals=["oversold"],
            rsi_value=30.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=False,
            fundamental_ok=True,
            timeframe_confirmation={"alignment_score": 0},
            news_sentiment=None,
            indicators={"close": 110.0},
            fundamentals={"pe": 15, "pb": 2},
            df=df,
        )

        # Verify EMA9 distance is calculated
        assert "ema9_distance_pct" in features
        # EMA9 = 115.0, Close = 110.0 -> Distance = (115-110)/110 * 100 = 4.545%
        expected_distance = ((115.0 - 110.0) / 110.0) * 100
        assert abs(features["ema9_distance_pct"] - expected_distance) < 0.01

    def test_ema9_distance_defaults_when_not_available(self):
        """Test that EMA9 distance defaults to 0 when EMA9 not in dataframe"""
        # Create dataframe WITHOUT EMA9
        df = pd.DataFrame(
            {
                "close": [100.0, 105.0, 110.0],
                "high": [102.0, 107.0, 112.0],
                "low": [98.0, 103.0, 108.0],
                "volume": [1000000, 1100000, 1200000],
                "rsi10": [25.0, 28.0, 30.0],
                "ema200": [95.0, 96.0, 97.0],
                # NO ema9
            }
        )

        ml_service = MLVerdictService()

        features = ml_service._extract_features(
            signals=["oversold"],
            rsi_value=30.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=False,
            fundamental_ok=True,
            timeframe_confirmation={"alignment_score": 0},
            news_sentiment=None,
            indicators={"close": 110.0},
            fundamentals={"pe": 15, "pb": 2},
            df=df,
        )

        # Should default to 0
        assert "ema9_distance_pct" in features
        assert features["ema9_distance_pct"] == 0.0

    def test_ema9_distance_with_no_dataframe(self):
        """Test that EMA9 distance defaults to 0 when no dataframe provided"""
        ml_service = MLVerdictService()

        features = ml_service._extract_features(
            signals=["oversold"],
            rsi_value=30.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=False,
            fundamental_ok=True,
            timeframe_confirmation={"alignment_score": 0},
            news_sentiment=None,
            indicators={"close": 110.0},
            fundamentals={"pe": 15, "pb": 2},
            df=None,  # No dataframe
        )

        assert "ema9_distance_pct" in features
        assert features["ema9_distance_pct"] == 0.0

    def test_feature_count_matches_training(self):
        """Test that live feature extraction produces 43 features matching training data"""
        # Create complete dataframe
        df = pd.DataFrame(
            {
                "close": [100.0] * 60,
                "high": [102.0] * 60,
                "low": [98.0] * 60,
                "volume": [1000000] * 60,
                "rsi10": [25.0] * 60,
                "ema9": [108.0] * 60,
                "ema200": [95.0] * 60,
            }
        )

        ml_service = MLVerdictService()

        features = ml_service._extract_features(
            signals=["oversold", "hammer"],
            rsi_value=25.0,
            is_above_ema200=True,
            vol_ok=True,
            vol_strong=True,
            fundamental_ok=True,
            timeframe_confirmation={"alignment_score": 2},
            news_sentiment={"sentiment": "positive"},
            indicators={
                "close": 100.0,
                "dip_depth_from_20d_high_pct": 10.0,
                "consecutive_red_days": 5,
                "dip_speed_pct_per_day": 2.0,
                "decline_rate_slowing": True,
                "volume_green_vs_red_ratio": 1.5,
                "support_hold_count": 3,
            },
            fundamentals={"pe": 15, "pb": 2},
            df=df,
        )

        # Should have all 43 features
        assert len(features) == 43, f"Expected 43 features, got {len(features)}"

        # Verify key features present
        assert "ema9_distance_pct" in features
        assert "rsi_10" in features
        assert "dip_depth_from_20d_high_pct" in features
        assert "total_fills_in_position" in features
        assert "nifty_trend" in features


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
