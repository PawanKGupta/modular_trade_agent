# ruff: noqa: E402, PLC0415, E501

import os
import sys

import pytest

# Ensure Unicode logs render on Windows/CI environments
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

# Import models ONCE at module level to ensure they're registered before any fixtures
# This prevents SQLAlchemy registry conflicts when models are imported multiple times
import src.infrastructure.db.models  # noqa: F401


@pytest.fixture(autouse=True)
def clean_db_after_test():
    """
    Ensure each test runs with an isolated in-memory DB schema and cleans up afterward.
    Drops all tables after each test to avoid cross-test contamination.

    CRITICAL: This fixture MUST use a separate test engine, NOT the shared engine from
    session.py, to prevent accidentally dropping tables from the production database.
    """
    # CRITICAL: Force in-memory database BEFORE any imports that might use DB_URL
    # This prevents the shared session.py engine from connecting to the real database
    original_db_url = os.environ.get("DB_URL")
    os.environ["DB_URL"] = "sqlite:///:memory:"

    # Safety guard: prevent tests from using the real app DB path
    db_url = os.environ.get("DB_URL", "")
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "", 1)
        real_db = os.path.abspath(os.path.join(os.getcwd(), "data", "app.db"))
        if os.path.abspath(db_path) == real_db:
            raise RuntimeError(f"Tests must not run against real DB: {db_path}")

    # Make sure project root is importable
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if root not in sys.path:
        sys.path.append(root)

    # Create a SEPARATE test engine - do NOT use the shared engine from session.py
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from src.infrastructure.db.base import Base

    test_engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    try:
        # Create fresh schema for each test using the test engine
        try:
            Base.metadata.drop_all(bind=test_engine)
        except Exception:
            pass
        Base.metadata.create_all(bind=test_engine)
        yield
    finally:
        # Teardown: drop schema from test engine only
        try:
            Base.metadata.drop_all(bind=test_engine)
        except Exception:
            pass
        test_engine.dispose()

        # Restore original DB_URL if it was set
        if original_db_url is not None:
            os.environ["DB_URL"] = original_db_url
        elif "DB_URL" in os.environ:
            del os.environ["DB_URL"]
        # If a file-based SQLite URL was used in a test (e.g., overridden to a tmp file),
        # remove the file to avoid residue. We only remove if path exists and is within a temp directory.
        db_url = os.environ.get("DB_URL", "")
        if db_url.startswith("sqlite:///") and db_url != "sqlite:///:memory:":
            path = db_url.replace("sqlite:///", "", 1)
            # best-effort cleanup for tmp-based dbs
            try:
                import pathlib
                import tempfile

                tmpdir = pathlib.Path(tempfile.gettempdir()).resolve()
                db_path = pathlib.Path(path).resolve()
                if str(db_path).startswith(str(tmpdir)) and db_path.exists():
                    db_path.unlink(missing_ok=True)
            except Exception:
                # ignore cleanup errors
                pass
        # Keep DB_URL env for the next test; default is in-memory anyway.


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.app.core.deps import get_db
from server.app.main import app
from src.infrastructure.db.base import Base


@pytest.fixture(scope="function")
def db_session():
    # In-memory SQLite for tests across threads
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Enable foreign key constraints for SQLite
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Models are already imported at module level
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client(db_session):
    # Override app DB dependency
    def _get_db_override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


"""
Pytest Configuration and Shared Fixtures

Provides common fixtures and configuration for all tests.
"""

from datetime import datetime

# Add project root to path
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.application.dto.analysis_request import AnalysisRequest, BulkAnalysisRequest
from src.application.dto.analysis_response import AnalysisResponse
from src.domain.entities.analysis_result import AnalysisResult, TradingParameters
from src.domain.entities.signal import Signal, SignalType
from src.domain.entities.stock import Stock
from src.domain.value_objects.price import Price
from src.domain.value_objects.volume import Volume

# ==================== Domain Entity Fixtures ====================


@pytest.fixture
def sample_stock():
    """Sample stock entity for testing"""
    return Stock(
        ticker="RELIANCE.NS",
        exchange="NSE",
        last_close=2450.50,
        last_updated=datetime(2025, 10, 26, 10, 0, 0),
    )


@pytest.fixture
def sample_buy_signal():
    """Sample BUY signal for testing"""
    signal = Signal(
        ticker="RELIANCE.NS",
        signal_type=SignalType.BUY,
        timestamp=datetime(2025, 10, 26, 10, 0, 0),
        strength_score=75.0,
    )
    signal.add_justification("RSI oversold")
    signal.add_justification("Strong support level")
    return signal


@pytest.fixture
def sample_strong_buy_signal():
    """Sample STRONG_BUY signal for testing"""
    signal = Signal(
        ticker="RELIANCE.NS",
        signal_type=SignalType.STRONG_BUY,
        timestamp=datetime(2025, 10, 26, 10, 0, 0),
        strength_score=90.0,
    )
    signal.add_justification("Multiple bullish patterns")
    signal.add_justification("Volume confirmation")
    return signal


@pytest.fixture
def sample_analysis_result():
    """Sample analysis result for testing"""
    trading_params = TradingParameters(
        buy_range_low=2400.0,
        buy_range_high=2450.0,
        target=2650.0,
        stop_loss=2300.0,
        potential_gain_pct=8.16,
        potential_loss_pct=6.12,
        risk_reward_ratio=1.33,
    )

    sig = Signal(
        ticker="RELIANCE.NS",
        signal_type=SignalType.BUY,
        timestamp=datetime(2025, 10, 26, 10, 0, 0),
        strength_score=75.0,
    )

    return AnalysisResult(
        ticker="RELIANCE.NS",
        status="success",
        timestamp=datetime(2025, 10, 26, 10, 0, 0),
        signal=sig,
        trading_params=trading_params,
        mtf_alignment_score=8.0,
        backtest_score=45.0,
        combined_score=32.5,
        priority_score=75.0,
        metadata={
            "pe": 15.5,
            "volume_multiplier": 2.1,
            "patterns": ["hammer", "bullish_engulfing"],
        },
    )


# ==================== Value Object Fixtures ====================


@pytest.fixture
def sample_price():
    """Sample price for testing"""
    return Price(2450.50, "INR")


@pytest.fixture
def sample_volume():
    """Sample volume for testing"""
    return Volume(value=2000000, average=1500000)


# ==================== DTO Fixtures ====================


@pytest.fixture
def sample_analysis_request():
    """Sample analysis request for testing"""
    return AnalysisRequest(
        ticker="RELIANCE.NS",
        enable_multi_timeframe=True,
        enable_backtest=False,
        export_to_csv=False,
        dip_mode=False,
    )


@pytest.fixture
def sample_bulk_analysis_request():
    """Sample bulk analysis request for testing"""
    return BulkAnalysisRequest(
        tickers=["RELIANCE.NS", "INFY.NS", "TCS.NS"],
        enable_multi_timeframe=True,
        enable_backtest=False,
        export_to_csv=False,
        dip_mode=False,
        min_combined_score=25.0,
    )


@pytest.fixture
def sample_analysis_response():
    """Sample analysis response for testing"""
    return AnalysisResponse(
        ticker="RELIANCE.NS",
        status="success",
        timestamp=datetime(2025, 10, 26, 10, 0, 0),
        verdict="buy",
        final_verdict="buy",
        last_close=2450.50,
        buy_range=(2400.0, 2450.0),
        target=2650.0,
        stop_loss=2300.0,
        rsi=28.5,
        mtf_alignment_score=8.0,
        backtest_score=45.0,
        combined_score=32.5,
        priority_score=75.0,
        metadata={"pe": 15.5},
    )


# ==================== Mock Service Fixtures ====================


@pytest.fixture
def mock_data_service():
    """Mock data service for testing"""
    mock = Mock()
    mock.fetch_stock_data.return_value = {
        "ticker": "RELIANCE.NS",
        "last_close": 2450.50,
        "volume": 2000000,
        "data": [],  # Mock OHLCV data
    }
    return mock


@pytest.fixture
def mock_scoring_service():
    """Mock scoring service for testing"""
    mock = Mock()
    mock.compute_strength_score.return_value = 75.0
    mock.compute_trading_priority_score.return_value = 85.0
    mock.compute_combined_score.return_value = 60.0
    return mock


@pytest.fixture
def mock_notification_service():
    """Mock notification service for testing"""
    mock = Mock()
    mock.send_alert.return_value = True
    mock.is_available.return_value = True
    return mock


# ==================== Test Data Fixtures ====================


@pytest.fixture
def sample_legacy_analysis_result():
    """Sample legacy analysis result dict for testing"""
    return {
        "ticker": "RELIANCE.NS",
        "status": "success",
        "verdict": "buy",
        "last_close": 2450.50,
        "buy_range": [2400.0, 2450.0],
        "target": 2650.0,
        "stop": 2300.0,
        "rsi": 28.5,
        "timeframe_analysis": {"alignment_score": 8.0, "confirmation": "good_uptrend_dip"},
        "patterns": ["hammer", "bullish_engulfing"],
        "pe": 15.5,
        "volume_multiplier": 2.1,
        "justification": ["RSI oversold", "Strong support"],
    }


# ==================== Pytest Hooks ====================


def pytest_configure(config):
    """Configure pytest with custom settings"""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "e2e: mark test as an end-to-end test")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically"""
    for item in items:
        # Auto-mark tests based on file path
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
        else:
            item.add_marker(pytest.mark.unit)


def pytest_configure_node(node):
    """
    Called when a worker node is being set up for parallel execution.
    Ensures models are imported once per worker to avoid SQLAlchemy registry conflicts.
    """
    # Force import models in each worker process to ensure proper registration
    # This prevents "Multiple classes found for path" errors in parallel execution
    try:
        # Clear any existing registry conflicts by ensuring fresh import
        from sqlalchemy.orm import configure_mappers

        import src.infrastructure.db.models  # noqa: F401

        configure_mappers()
    except Exception:
        # If there's an issue, it will be caught in the actual test
        pass
