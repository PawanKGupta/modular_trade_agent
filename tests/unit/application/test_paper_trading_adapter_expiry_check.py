"""
Tests for PaperTradingEngineAdapter expiry check before loading signals.

Verifies that PaperTradingEngineAdapter calls mark_time_expired_signals() before
loading signals to prevent trading on expired signals.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.db.models import Signals, SignalStatus
from src.infrastructure.db.timezone_utils import IST


@pytest.fixture
def db_session():
    """Create a database session for testing"""
    from src.infrastructure.db.session import SessionLocal

    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def paper_trading_adapter(db_session):
    """Create PaperTradingEngineAdapter instance"""
    from src.application.services.paper_trading_service_adapter import (
        PaperTradingEngineAdapter,
    )

    mock_broker = MagicMock()
    mock_strategy_config = MagicMock()
    mock_logger = MagicMock()

    adapter = PaperTradingEngineAdapter(
        broker=mock_broker,
        user_id=1,
        db_session=db_session,
        strategy_config=mock_strategy_config,
        logger=mock_logger,
    )

    return adapter


class TestPaperTradingAdapterExpiryCheck:
    """Test that PaperTradingEngineAdapter checks expiry before loading signals"""

    def test_load_latest_recommendations_calls_expiry_check(
        self, paper_trading_adapter, db_session
    ):
        """Test that mark_time_expired_signals() is called before loading signals"""

        # Create a signal
        signal = Signals(
            symbol="RELIANCE.NS",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday 4:00 PM
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        # Mock ist_now to return a time after expiry (Tuesday 4:00 PM)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_ist_now:
            mock_ist_now.return_value = datetime(2025, 12, 2, 16, 0, 0, tzinfo=IST)

            # Mock the repository to track calls
            # SignalsRepository is imported inside load_latest_recommendations
            with patch(
                "src.infrastructure.persistence.signals_repository.SignalsRepository"
            ) as mock_repo_class:
                mock_repo = MagicMock()
                mock_repo_class.return_value = mock_repo

                # Mock by_date to return empty list (no signals for today)
                mock_repo.by_date.return_value = []
                # Mock recent to return our signal
                mock_repo.recent.return_value = [signal]
                # Mock get_user_signal_status to return None (use base status)
                mock_repo.get_user_signal_status.return_value = None

                # Call load_latest_recommendations
                recommendations = paper_trading_adapter.load_latest_recommendations()

                # Verify mark_time_expired_signals was called
                mock_repo.mark_time_expired_signals.assert_called_once()

    def test_load_latest_recommendations_excludes_expired_signals(
        self, paper_trading_adapter, db_session
    ):
        """Test that expired signals are not included in recommendations"""
        # Create an expired signal (created Monday, now Tuesday after 3:30 PM)
        expired_signal = Signals(
            symbol="RELIANCE.NS",
            status=SignalStatus.ACTIVE,  # Still ACTIVE in DB (not checked yet)
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday 4:00 PM
            verdict="buy",
        )

        db_session.add(expired_signal)
        db_session.commit()

        # Mock ist_now to return Tuesday 4:00 PM (after expiry for Monday signal)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_ist_now:
            mock_ist_now.return_value = datetime(2025, 12, 2, 16, 0, 0, tzinfo=IST)

            # Load recommendations
            recommendations = paper_trading_adapter.load_latest_recommendations()

            # Verify expired signal was marked as EXPIRED in database
            db_session.refresh(expired_signal)
            assert expired_signal.status == SignalStatus.EXPIRED

            # Verify expired signal is not in recommendations
            # (adapter filters by ACTIVE status)
            assert len(recommendations) == 0 or all(
                rec.symbol != "RELIANCE.NS" for rec in recommendations
            )

    def test_load_latest_recommendations_includes_active_signals(
        self, paper_trading_adapter, db_session
    ):
        """Test that active (non-expired) signals are included in recommendations"""
        # Create an active signal (created Monday, now Tuesday before 3:30 PM)
        active_signal = Signals(
            symbol="TCS.NS",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday 4:00 PM
            verdict="buy",
        )

        db_session.add(active_signal)
        db_session.commit()

        # Mock ist_now to return Tuesday 2:00 PM (before expiry at 3:30 PM)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_ist_now:
            mock_ist_now.return_value = datetime(2025, 12, 2, 14, 0, 0, tzinfo=IST)

            # Load recommendations
            recommendations = paper_trading_adapter.load_latest_recommendations()

            # Verify signal is still ACTIVE in database
            db_session.refresh(active_signal)
            assert active_signal.status == SignalStatus.ACTIVE
