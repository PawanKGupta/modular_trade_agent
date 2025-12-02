"""
Tests for signal status filtering in AutoTradeEngine.load_latest_recommendations

Tests that the engine correctly filters signals by status before placing orders.
"""

from unittest.mock import MagicMock, patch

import pytest

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
from src.infrastructure.db.models import Signals, SignalStatus, Users, UserSignalStatus
from src.infrastructure.db.timezone_utils import ist_now


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = Users(
        email="engine_test@example.com",
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


class TestAutoTradeEngineSignalStatusFiltering:
    """Test that AutoTradeEngine.load_latest_recommendations filters by signal status"""

    def test_load_recommendations_includes_active_signals(
        self, auto_trade_engine_with_db, db_session, test_user
    ):
        """Test that ACTIVE signals are included in recommendations"""
        # Create ACTIVE signals
        signal1 = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        signal2 = Signals(
            symbol="TCS",
            verdict="strong_buy",
            final_verdict="strong_buy",
            last_close=3500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        db_session.add_all([signal1, signal2])
        db_session.commit()

        recs = auto_trade_engine_with_db.load_latest_recommendations()

        # Should return both ACTIVE signals
        assert len(recs) == 2
        tickers = {r.ticker for r in recs}
        assert "RELIANCE.NS" in tickers
        assert "TCS.NS" in tickers

    def test_load_recommendations_excludes_traded_signals(
        self, auto_trade_engine_with_db, db_session, test_user
    ):
        """Test that TRADED signals (per-user) are excluded from recommendations"""
        # Create ACTIVE signal
        signal = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # Mark as TRADED for this user (per-user status)
        user_status = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal.id,
            symbol="RELIANCE",
            status=SignalStatus.TRADED,
        )
        db_session.add(user_status)
        db_session.commit()

        # Mock CSV fallback to return empty list
        with patch.object(
            auto_trade_engine_with_db, "load_latest_recommendations_from_csv", return_value=[]
        ):
            recs = auto_trade_engine_with_db.load_latest_recommendations()

        # Should exclude TRADED signal
        assert len(recs) == 0

    def test_load_recommendations_excludes_rejected_signals(
        self, auto_trade_engine_with_db, db_session, test_user
    ):
        """Test that REJECTED signals (per-user) are excluded from recommendations"""
        # Create ACTIVE signal
        signal = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # Mark as REJECTED for this user (per-user status)
        user_status = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal.id,
            symbol="RELIANCE",
            status=SignalStatus.REJECTED,
        )
        db_session.add(user_status)
        db_session.commit()

        # Mock CSV fallback to return empty list
        with patch.object(
            auto_trade_engine_with_db, "load_latest_recommendations_from_csv", return_value=[]
        ):
            recs = auto_trade_engine_with_db.load_latest_recommendations()

        # Should exclude REJECTED signal
        assert len(recs) == 0

    def test_load_recommendations_excludes_expired_signals(
        self, auto_trade_engine_with_db, db_session, test_user
    ):
        """Test that EXPIRED signals (base status) are excluded from recommendations"""
        # Create EXPIRED signal
        signal = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.EXPIRED,
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()

        # Mock CSV fallback to return empty list
        with patch.object(
            auto_trade_engine_with_db, "load_latest_recommendations_from_csv", return_value=[]
        ):
            recs = auto_trade_engine_with_db.load_latest_recommendations()

        # Should exclude EXPIRED signal
        assert len(recs) == 0

    def test_load_recommendations_per_user_status_takes_precedence(
        self, auto_trade_engine_with_db, db_session, test_user
    ):
        """Test that per-user status takes precedence over base signal status"""
        # Create signal with EXPIRED base status
        signal = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.EXPIRED,  # Base status is EXPIRED
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # But mark as ACTIVE for test_user (per-user status)
        user_status = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal.id,
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,  # Per-user status is ACTIVE
        )
        db_session.add(user_status)
        db_session.commit()

        recs = auto_trade_engine_with_db.load_latest_recommendations()

        # Should include signal because per-user status (ACTIVE) takes precedence
        assert len(recs) == 1
        assert recs[0].ticker == "RELIANCE.NS"

    def test_load_recommendations_mixed_status_signals(
        self, auto_trade_engine_with_db, db_session, test_user
    ):
        """Test filtering with mixed status signals"""
        # Create multiple signals with different statuses
        signal1 = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        signal2 = Signals(
            symbol="TCS",
            verdict="strong_buy",
            final_verdict="strong_buy",
            last_close=3500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        signal3 = Signals(
            symbol="INFY",
            verdict="buy",
            final_verdict="buy",
            last_close=1500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        signal4 = Signals(
            symbol="HDFC",
            verdict="buy",
            final_verdict="buy",
            last_close=2000.0,
            status=SignalStatus.EXPIRED,
            ts=ist_now(),
        )
        db_session.add_all([signal1, signal2, signal3, signal4])
        db_session.commit()
        db_session.refresh(signal2)
        db_session.refresh(signal3)

        # Mark signal2 as TRADED (per-user)
        user_status_traded = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal2.id,
            symbol="TCS",
            status=SignalStatus.TRADED,
        )
        # Mark signal3 as REJECTED (per-user)
        user_status_rejected = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal3.id,
            symbol="INFY",
            status=SignalStatus.REJECTED,
        )
        db_session.add_all([user_status_traded, user_status_rejected])
        db_session.commit()

        recs = auto_trade_engine_with_db.load_latest_recommendations()

        # Should only return signal1 (ACTIVE, no per-user status)
        # signal2 is TRADED (per-user) - excluded
        # signal3 is REJECTED (per-user) - excluded
        # signal4 is EXPIRED (base) - excluded
        assert len(recs) == 1
        assert recs[0].ticker == "RELIANCE.NS"

    def test_load_recommendations_different_users_see_different_signals(
        self, auto_trade_engine_with_db, db_session, test_user
    ):
        """Test that different users see different signals based on their per-user status"""
        # Create another user
        user2 = Users(
            email="user2@test.com",
            password_hash="hash2",
            role="user",
        )
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user2)

        # Create signal
        signal = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # Mark as TRADED for test_user
        user_status1 = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal.id,
            symbol="RELIANCE",
            status=SignalStatus.TRADED,
        )
        # But ACTIVE for user2 (no per-user status, uses base ACTIVE)
        db_session.add(user_status1)
        db_session.commit()

        # Test user should not see the signal
        # Mock CSV fallback to return empty list
        with patch.object(
            auto_trade_engine_with_db, "load_latest_recommendations_from_csv", return_value=[]
        ):
            recs1 = auto_trade_engine_with_db.load_latest_recommendations()
        assert len(recs1) == 0

        # User2 should see the signal (no per-user status, base is ACTIVE)
        auth_patch_path = "modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"
        with patch(auth_patch_path) as mock_auth_class:
            mock_auth = MagicMock()
            mock_auth.is_authenticated.return_value = True
            mock_auth.login.return_value = True
            mock_auth_class.return_value = mock_auth

            engine2 = AutoTradeEngine(
                env_file="test.env",
                auth=mock_auth,
                user_id=user2.id,
                db_session=db_session,
                enable_verifier=False,
                enable_telegram=False,
                enable_eod_cleanup=False,
            )
            recs2 = engine2.load_latest_recommendations()
            assert len(recs2) == 1
            assert recs2[0].ticker == "RELIANCE.NS"
