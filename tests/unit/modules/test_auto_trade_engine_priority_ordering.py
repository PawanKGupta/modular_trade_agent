"""
Tests for priority-based order placement in AutoTradeEngine

Tests verify that recommendations are sorted by priority_score, with ML confidence boost
when ML is enabled.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine, Recommendation
from src.infrastructure.db.models import Signals, SignalStatus, Users
from src.infrastructure.db.timezone_utils import ist_now


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = Users(
        email="priority_test@example.com",
        password_hash="test_hash",
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def mock_auth():
    """Mock KotakNeoAuth"""
    auth = MagicMock()
    auth.is_authenticated.return_value = True
    auth.login.return_value = True
    return auth


@pytest.fixture
def auto_trade_engine_with_db(mock_auth, db_session, test_user):
    """Create AutoTradeEngine with database session"""
    with patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth") as mock_auth_class:
        mock_auth_class.return_value = mock_auth

        engine = AutoTradeEngine(
            env_file="test.env",
            auth=mock_auth,
            user_id=test_user.id,
            db_session=db_session,
            enable_verifier=False,
            enable_telegram=False,
            enable_eod_cleanup=False,
        )
        yield engine


class TestPriorityOrderingWithoutML:
    """Test priority-based ordering when ML is NOT enabled (no ML confidence boost)"""

    def test_csv_loading_sorts_by_priority_score_descending(
        self, auto_trade_engine_with_db, tmp_path
    ):
        """Test that CSV recommendations are sorted by priority_score (descending)"""
        # Create CSV with recommendations in random order
        csv_path = tmp_path / "recommendations.csv"
        df = pd.DataFrame(
            {
                "ticker": ["STOCK1.NS", "STOCK2.NS", "STOCK3.NS"],
                "final_verdict": ["buy", "strong_buy", "buy"],
                "last_close": [100.0, 200.0, 300.0],
                "priority_score": [30.0, 80.0, 50.0],  # Should be sorted: 80, 50, 30
                "combined_score": [25.0, 75.0, 45.0],
                "status": ["success", "success", "success"],
            }
        )
        df.to_csv(csv_path, index=False)

        recs = auto_trade_engine_with_db.load_latest_recommendations_from_csv(str(csv_path))

        # Should be sorted by priority_score (descending)
        assert len(recs) == 3
        assert recs[0].ticker == "STOCK2.NS"  # Highest priority (80)
        assert recs[0].priority_score == 80.0
        assert recs[1].ticker == "STOCK3.NS"  # Medium priority (50)
        assert recs[1].priority_score == 50.0
        assert recs[2].ticker == "STOCK1.NS"  # Lowest priority (30)
        assert recs[2].priority_score == 30.0

    def test_csv_loading_fallback_to_combined_score_when_priority_missing(
        self, auto_trade_engine_with_db, tmp_path
    ):
        """Test that CSV falls back to combined_score when priority_score is missing"""
        csv_path = tmp_path / "recommendations.csv"
        df = pd.DataFrame(
            {
                "ticker": ["STOCK1.NS", "STOCK2.NS"],
                "final_verdict": ["buy", "strong_buy"],
                "last_close": [100.0, 200.0],
                "combined_score": [40.0, 70.0],  # Used as fallback
                "status": ["success", "success"],
            }
        )
        df.to_csv(csv_path, index=False)

        recs = auto_trade_engine_with_db.load_latest_recommendations_from_csv(str(csv_path))

        # Should use combined_score and sort descending
        assert len(recs) == 2
        assert recs[0].ticker == "STOCK2.NS"  # Higher combined_score (70)
        assert recs[0].priority_score == 70.0
        assert recs[1].ticker == "STOCK1.NS"  # Lower combined_score (40)
        assert recs[1].priority_score == 40.0

    def test_database_loading_sorts_by_priority_score_descending(
        self, auto_trade_engine_with_db, db_session, test_user
    ):
        """Test that database recommendations are sorted by priority_score (descending)"""
        # Create signals with different priority scores
        signal1 = Signals(
            symbol="STOCK1",
            verdict="buy",
            final_verdict="buy",
            last_close=100.0,
            status=SignalStatus.ACTIVE,
            priority_score=30.0,
            combined_score=25.0,
            ts=ist_now(),
        )
        signal2 = Signals(
            symbol="STOCK2",
            verdict="strong_buy",
            final_verdict="strong_buy",
            last_close=200.0,
            status=SignalStatus.ACTIVE,
            priority_score=80.0,
            combined_score=75.0,
            ts=ist_now(),
        )
        signal3 = Signals(
            symbol="STOCK3",
            verdict="buy",
            final_verdict="buy",
            last_close=300.0,
            status=SignalStatus.ACTIVE,
            priority_score=50.0,
            combined_score=45.0,
            ts=ist_now(),
        )
        db_session.add_all([signal1, signal2, signal3])
        db_session.commit()

        recs = auto_trade_engine_with_db.load_latest_recommendations()

        # Should be sorted by priority_score (descending)
        assert len(recs) == 3
        assert recs[0].ticker == "STOCK2.NS"  # Highest priority (80)
        assert recs[0].priority_score == 80.0
        assert recs[1].ticker == "STOCK3.NS"  # Medium priority (50)
        assert recs[1].priority_score == 50.0
        assert recs[2].ticker == "STOCK1.NS"  # Lowest priority (30)
        assert recs[2].priority_score == 30.0

    def test_database_loading_fallback_to_combined_score_when_priority_missing(
        self, auto_trade_engine_with_db, db_session, test_user
    ):
        """Test that database falls back to combined_score when priority_score is missing"""
        signal1 = Signals(
            symbol="STOCK1",
            verdict="buy",
            final_verdict="buy",
            last_close=100.0,
            status=SignalStatus.ACTIVE,
            priority_score=None,  # Missing
            combined_score=40.0,  # Used as fallback
            ts=ist_now(),
        )
        signal2 = Signals(
            symbol="STOCK2",
            verdict="strong_buy",
            final_verdict="strong_buy",
            last_close=200.0,
            status=SignalStatus.ACTIVE,
            priority_score=None,  # Missing
            combined_score=70.0,  # Used as fallback
            ts=ist_now(),
        )
        db_session.add_all([signal1, signal2])
        db_session.commit()

        recs = auto_trade_engine_with_db.load_latest_recommendations()

        # Should use combined_score and sort descending
        assert len(recs) == 2
        assert recs[0].ticker == "STOCK2.NS"  # Higher combined_score (70)
        assert recs[0].priority_score == 70.0
        assert recs[1].ticker == "STOCK1.NS"  # Lower combined_score (40)
        assert recs[1].priority_score == 40.0

    def test_csv_loading_no_ml_confidence_boost_when_missing(
        self, auto_trade_engine_with_db, tmp_path
    ):
        """Test that no ML confidence boost is applied when ml_confidence is missing"""
        csv_path = tmp_path / "recommendations.csv"
        df = pd.DataFrame(
            {
                "ticker": ["STOCK1.NS", "STOCK2.NS"],
                "final_verdict": ["buy", "strong_buy"],
                "last_close": [100.0, 200.0],
                "priority_score": [50.0, 50.0],  # Same base score
                "combined_score": [45.0, 45.0],
                "status": ["success", "success"],
                # ml_confidence column missing (ML not enabled)
            }
        )
        df.to_csv(csv_path, index=False)

        recs = auto_trade_engine_with_db.load_latest_recommendations_from_csv(str(csv_path))

        # Should have same priority_score (no boost)
        assert len(recs) == 2
        assert recs[0].priority_score == 50.0
        assert recs[1].priority_score == 50.0


class TestPriorityOrderingWithML:
    """Test priority-based ordering when ML IS enabled (with ML confidence boost)"""

    def test_csv_loading_high_ml_confidence_boost(self, auto_trade_engine_with_db, tmp_path):
        """Test that high ML confidence (>=70%) adds +20 points boost"""
        csv_path = tmp_path / "recommendations.csv"
        df = pd.DataFrame(
            {
                "ticker": ["STOCK1.NS", "STOCK2.NS"],
                "final_verdict": ["buy", "strong_buy"],
                "last_close": [100.0, 200.0],
                "priority_score": [50.0, 60.0],  # STOCK2 has higher base score
                "combined_score": [45.0, 55.0],
                "ml_confidence": [0.85, 0.0],  # STOCK1 has high ML confidence
                "status": ["success", "success"],
            }
        )
        df.to_csv(csv_path, index=False)

        recs = auto_trade_engine_with_db.load_latest_recommendations_from_csv(str(csv_path))

        # STOCK1 should be first due to ML boost (50 + 20 = 70 > 60)
        assert len(recs) == 2
        assert recs[0].ticker == "STOCK1.NS"
        assert recs[0].priority_score == 70.0  # 50 + 20 (high confidence boost)
        assert recs[1].ticker == "STOCK2.NS"
        assert recs[1].priority_score == 60.0  # No boost (ml_confidence = 0)

    def test_csv_loading_medium_ml_confidence_boost(self, auto_trade_engine_with_db, tmp_path):
        """Test that medium ML confidence (60-70%) adds +10 points boost"""
        csv_path = tmp_path / "recommendations.csv"
        df = pd.DataFrame(
            {
                "ticker": ["STOCK1.NS", "STOCK2.NS"],
                "final_verdict": ["buy", "strong_buy"],
                "last_close": [100.0, 200.0],
                "priority_score": [50.0, 55.0],  # STOCK2 has slightly higher base score
                "combined_score": [45.0, 50.0],
                "ml_confidence": [0.65, 0.0],  # STOCK1 has medium ML confidence
                "status": ["success", "success"],
            }
        )
        df.to_csv(csv_path, index=False)

        recs = auto_trade_engine_with_db.load_latest_recommendations_from_csv(str(csv_path))

        # STOCK1 should be first due to ML boost (50 + 10 = 60 > 55)
        assert len(recs) == 2
        assert recs[0].ticker == "STOCK1.NS"
        assert recs[0].priority_score == 60.0  # 50 + 10 (medium confidence boost)
        assert recs[1].ticker == "STOCK2.NS"
        assert recs[1].priority_score == 55.0  # No boost

    def test_csv_loading_low_ml_confidence_boost(self, auto_trade_engine_with_db, tmp_path):
        """Test that low ML confidence (50-60%) adds +5 points boost"""
        csv_path = tmp_path / "recommendations.csv"
        df = pd.DataFrame(
            {
                "ticker": ["STOCK1.NS", "STOCK2.NS"],
                "final_verdict": ["buy", "strong_buy"],
                "last_close": [100.0, 200.0],
                "priority_score": [50.0, 52.0],  # STOCK2 has slightly higher base score
                "combined_score": [45.0, 47.0],
                "ml_confidence": [0.55, 0.0],  # STOCK1 has low ML confidence
                "status": ["success", "success"],
            }
        )
        df.to_csv(csv_path, index=False)

        recs = auto_trade_engine_with_db.load_latest_recommendations_from_csv(str(csv_path))

        # STOCK1 should be first due to ML boost (50 + 5 = 55 > 52)
        assert len(recs) == 2
        assert recs[0].ticker == "STOCK1.NS"
        assert recs[0].priority_score == 55.0  # 50 + 5 (low confidence boost)
        assert recs[1].ticker == "STOCK2.NS"
        assert recs[1].priority_score == 52.0  # No boost

    def test_csv_loading_no_boost_below_threshold(self, auto_trade_engine_with_db, tmp_path):
        """Test that ML confidence below 50% threshold gets no boost"""
        csv_path = tmp_path / "recommendations.csv"
        df = pd.DataFrame(
            {
                "ticker": ["STOCK1.NS", "STOCK2.NS"],
                "final_verdict": ["buy", "strong_buy"],
                "last_close": [100.0, 200.0],
                "priority_score": [50.0, 60.0],
                "combined_score": [45.0, 55.0],
                "ml_confidence": [0.45, 0.0],  # STOCK1 has ML confidence below threshold
                "status": ["success", "success"],
            }
        )
        df.to_csv(csv_path, index=False)

        recs = auto_trade_engine_with_db.load_latest_recommendations_from_csv(str(csv_path))

        # STOCK2 should be first (no boost for STOCK1 since ml_confidence < 50%)
        assert len(recs) == 2
        assert recs[0].ticker == "STOCK2.NS"
        assert recs[0].priority_score == 60.0  # Higher base score
        assert recs[1].ticker == "STOCK1.NS"
        assert recs[1].priority_score == 50.0  # No boost (below threshold)

    def test_csv_loading_ml_confidence_bands_edge_cases(
        self, auto_trade_engine_with_db, tmp_path
    ):
        """Test ML confidence boost at exact threshold boundaries"""
        csv_path = tmp_path / "recommendations.csv"
        df = pd.DataFrame(
            {
                "ticker": ["STOCK1.NS", "STOCK2.NS", "STOCK3.NS", "STOCK4.NS"],
                "final_verdict": ["buy", "buy", "buy", "buy"],
                "last_close": [100.0, 200.0, 300.0, 400.0],
                "priority_score": [50.0, 50.0, 50.0, 50.0],  # All same base score
                "combined_score": [45.0, 45.0, 45.0, 45.0],
                "ml_confidence": [0.70, 0.60, 0.50, 0.49],  # Edge cases
                "status": ["success", "success", "success", "success"],
            }
        )
        df.to_csv(csv_path, index=False)

        recs = auto_trade_engine_with_db.load_latest_recommendations_from_csv(str(csv_path))

        # Should be sorted by final priority (with boosts)
        assert len(recs) == 4
        assert recs[0].ticker == "STOCK1.NS"  # 50 + 20 = 70 (high confidence)
        assert recs[0].priority_score == 70.0
        assert recs[1].ticker == "STOCK2.NS"  # 50 + 10 = 60 (medium confidence)
        assert recs[1].priority_score == 60.0
        assert recs[2].ticker == "STOCK3.NS"  # 50 + 5 = 55 (low confidence)
        assert recs[2].priority_score == 55.0
        assert recs[3].ticker == "STOCK4.NS"  # 50 + 0 = 50 (below threshold)
        assert recs[3].priority_score == 50.0

    def test_database_loading_high_ml_confidence_boost(
        self, auto_trade_engine_with_db, db_session, test_user
    ):
        """Test that high ML confidence (>=70%) adds +20 points boost in database loading"""
        signal1 = Signals(
            symbol="STOCK1",
            verdict="buy",
            final_verdict="buy",
            last_close=100.0,
            status=SignalStatus.ACTIVE,
            priority_score=50.0,
            combined_score=45.0,
            ml_confidence=0.85,  # High ML confidence
            ts=ist_now(),
        )
        signal2 = Signals(
            symbol="STOCK2",
            verdict="strong_buy",
            final_verdict="strong_buy",
            last_close=200.0,
            status=SignalStatus.ACTIVE,
            priority_score=60.0,
            combined_score=55.0,
            ml_confidence=None,  # No ML confidence
            ts=ist_now(),
        )
        db_session.add_all([signal1, signal2])
        db_session.commit()

        recs = auto_trade_engine_with_db.load_latest_recommendations()

        # STOCK1 should be first due to ML boost (50 + 20 = 70 > 60)
        assert len(recs) == 2
        assert recs[0].ticker == "STOCK1.NS"
        assert recs[0].priority_score == 70.0  # 50 + 20 (high confidence boost)
        assert recs[1].ticker == "STOCK2.NS"
        assert recs[1].priority_score == 60.0  # No boost

    def test_database_loading_medium_ml_confidence_boost(
        self, auto_trade_engine_with_db, db_session, test_user
    ):
        """Test that medium ML confidence (60-70%) adds +10 points boost in database loading"""
        signal1 = Signals(
            symbol="STOCK1",
            verdict="buy",
            final_verdict="buy",
            last_close=100.0,
            status=SignalStatus.ACTIVE,
            priority_score=50.0,
            combined_score=45.0,
            ml_confidence=0.65,  # Medium ML confidence
            ts=ist_now(),
        )
        signal2 = Signals(
            symbol="STOCK2",
            verdict="strong_buy",
            final_verdict="strong_buy",
            last_close=200.0,
            status=SignalStatus.ACTIVE,
            priority_score=55.0,
            combined_score=50.0,
            ml_confidence=None,  # No ML confidence
            ts=ist_now(),
        )
        db_session.add_all([signal1, signal2])
        db_session.commit()

        recs = auto_trade_engine_with_db.load_latest_recommendations()

        # STOCK1 should be first due to ML boost (50 + 10 = 60 > 55)
        assert len(recs) == 2
        assert recs[0].ticker == "STOCK1.NS"
        assert recs[0].priority_score == 60.0  # 50 + 10 (medium confidence boost)
        assert recs[1].ticker == "STOCK2.NS"
        assert recs[1].priority_score == 55.0  # No boost

    def test_database_loading_low_ml_confidence_boost(
        self, auto_trade_engine_with_db, db_session, test_user
    ):
        """Test that low ML confidence (50-60%) adds +5 points boost in database loading"""
        signal1 = Signals(
            symbol="STOCK1",
            verdict="buy",
            final_verdict="buy",
            last_close=100.0,
            status=SignalStatus.ACTIVE,
            priority_score=50.0,
            combined_score=45.0,
            ml_confidence=0.55,  # Low ML confidence
            ts=ist_now(),
        )
        signal2 = Signals(
            symbol="STOCK2",
            verdict="strong_buy",
            final_verdict="strong_buy",
            last_close=200.0,
            status=SignalStatus.ACTIVE,
            priority_score=52.0,
            combined_score=47.0,
            ml_confidence=None,  # No ML confidence
            ts=ist_now(),
        )
        db_session.add_all([signal1, signal2])
        db_session.commit()

        recs = auto_trade_engine_with_db.load_latest_recommendations()

        # STOCK1 should be first due to ML boost (50 + 5 = 55 > 52)
        assert len(recs) == 2
        assert recs[0].ticker == "STOCK1.NS"
        assert recs[0].priority_score == 55.0  # 50 + 5 (low confidence boost)
        assert recs[1].ticker == "STOCK2.NS"
        assert recs[1].priority_score == 52.0  # No boost

    def test_database_loading_no_boost_when_ml_confidence_zero(
        self, auto_trade_engine_with_db, db_session, test_user
    ):
        """Test that ML confidence of 0.0 gets no boost"""
        signal1 = Signals(
            symbol="STOCK1",
            verdict="buy",
            final_verdict="buy",
            last_close=100.0,
            status=SignalStatus.ACTIVE,
            priority_score=50.0,
            combined_score=45.0,
            ml_confidence=0.0,  # Zero ML confidence (no boost)
            ts=ist_now(),
        )
        signal2 = Signals(
            symbol="STOCK2",
            verdict="strong_buy",
            final_verdict="strong_buy",
            last_close=200.0,
            status=SignalStatus.ACTIVE,
            priority_score=60.0,
            combined_score=55.0,
            ml_confidence=None,  # No ML confidence
            ts=ist_now(),
        )
        db_session.add_all([signal1, signal2])
        db_session.commit()

        recs = auto_trade_engine_with_db.load_latest_recommendations()

        # STOCK2 should be first (no boost for STOCK1 since ml_confidence = 0.0)
        assert len(recs) == 2
        assert recs[0].ticker == "STOCK2.NS"
        assert recs[0].priority_score == 60.0  # Higher base score
        assert recs[1].ticker == "STOCK1.NS"
        assert recs[1].priority_score == 50.0  # No boost (ml_confidence = 0.0)

    def test_database_loading_complex_ml_confidence_scenario(
        self, auto_trade_engine_with_db, db_session, test_user
    ):
        """Test complex scenario with multiple ML confidence levels"""
        signals = [
            Signals(
                symbol="STOCK1",
                verdict="buy",
                final_verdict="buy",
                last_close=100.0,
                status=SignalStatus.ACTIVE,
                priority_score=40.0,
                combined_score=35.0,
                ml_confidence=0.75,  # High: 40 + 20 = 60
                ts=ist_now(),
            ),
            Signals(
                symbol="STOCK2",
                verdict="strong_buy",
                final_verdict="strong_buy",
                last_close=200.0,
                status=SignalStatus.ACTIVE,
                priority_score=55.0,
                combined_score=50.0,
                ml_confidence=0.65,  # Medium: 55 + 10 = 65
                ts=ist_now(),
            ),
            Signals(
                symbol="STOCK3",
                verdict="buy",
                final_verdict="buy",
                last_close=300.0,
                status=SignalStatus.ACTIVE,
                priority_score=50.0,
                combined_score=45.0,
                ml_confidence=0.55,  # Low: 50 + 5 = 55
                ts=ist_now(),
            ),
            Signals(
                symbol="STOCK4",
                verdict="strong_buy",
                final_verdict="strong_buy",
                last_close=400.0,
                status=SignalStatus.ACTIVE,
                priority_score=60.0,
                combined_score=55.0,
                ml_confidence=None,  # No ML: 60 + 0 = 60
                ts=ist_now(),
            ),
        ]
        db_session.add_all(signals)
        db_session.commit()

        recs = auto_trade_engine_with_db.load_latest_recommendations()

        # Should be sorted by final priority (with ML boosts):
        # STOCK2: 55 + 10 = 65 (highest)
        # STOCK4: 60 + 0 = 60
        # STOCK1: 40 + 20 = 60 (tie with STOCK4, but STOCK4 comes first due to original order)
        # STOCK3: 50 + 5 = 55 (lowest)
        assert len(recs) == 4
        assert recs[0].ticker == "STOCK2.NS"  # 65 (highest)
        assert recs[0].priority_score == 65.0
        # STOCK4 and STOCK1 both have 60, but STOCK4 should come first (original order)
        assert recs[1].ticker == "STOCK4.NS"  # 60
        assert recs[1].priority_score == 60.0
        assert recs[2].ticker == "STOCK1.NS"  # 60
        assert recs[2].priority_score == 60.0
        assert recs[3].ticker == "STOCK3.NS"  # 55 (lowest)
        assert recs[3].priority_score == 55.0

    def test_csv_loading_with_verdict_column_no_final_verdict(
        self, auto_trade_engine_with_db, tmp_path
    ):
        """Test CSV loading with 'verdict' column (no 'final_verdict') and ML confidence"""
        csv_path = tmp_path / "recommendations.csv"
        df = pd.DataFrame(
            {
                "ticker": ["STOCK1.NS", "STOCK2.NS"],
                "verdict": ["buy", "strong_buy"],  # Using 'verdict' instead of 'final_verdict'
                "last_close": [100.0, 200.0],
                "priority_score": [50.0, 60.0],
                "combined_score": [45.0, 55.0],
                "ml_confidence": [0.80, 0.0],  # STOCK1 has high ML confidence
                "status": ["success", "success"],
            }
        )
        df.to_csv(csv_path, index=False)

        recs = auto_trade_engine_with_db.load_latest_recommendations_from_csv(str(csv_path))

        # STOCK1 should be first due to ML boost (50 + 20 = 70 > 60)
        assert len(recs) == 2
        assert recs[0].ticker == "STOCK1.NS"
        assert recs[0].priority_score == 70.0  # 50 + 20 (high confidence boost)
        assert recs[0].verdict == "buy"
        assert recs[1].ticker == "STOCK2.NS"
        assert recs[1].priority_score == 60.0  # No boost
        assert recs[1].verdict == "strong_buy"

