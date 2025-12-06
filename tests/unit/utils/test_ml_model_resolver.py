"""
Unit tests for ML Model Resolver

Tests for resolving ML model paths from version strings.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.db.models import MLModel, MLTrainingJob, Users  # noqa: E402
from src.infrastructure.db.timezone_utils import ist_now  # noqa: E402
from utils.ml_model_resolver import (  # noqa: E402
    get_active_model_path,
    get_model_path_from_version,
)


@pytest.fixture
def sample_ml_model(db_session):
    """Create a sample MLModel in database"""
    # Create a user for created_by
    user = Users(
        email="ml_admin@example.com",
        password_hash="hash",
        created_at=ist_now(),
    )
    db_session.add(user)
    db_session.commit()

    # Create a training job
    training_job = MLTrainingJob(
        model_type="verdict_classifier",
        status="completed",
        started_by=user.id,
        algorithm="random_forest",
        training_data_path="data/training.csv",
        started_at=ist_now(),
    )
    db_session.add(training_job)
    db_session.commit()

    # Create the model
    model = MLModel(
        model_type="verdict_classifier",
        version="v1.0",
        model_path="models/verdict_model_v1.0.pkl",
        training_job_id=training_job.id,
        is_active=True,
        created_by=user.id,
        created_at=ist_now(),
    )
    db_session.add(model)
    db_session.commit()
    return model


@pytest.fixture
def sample_ml_model_v2(db_session):
    """Create another MLModel in database"""
    # Create a user for created_by
    user = Users(
        email="ml_admin_v2@example.com",
        password_hash="hash",
        created_at=ist_now(),
    )
    db_session.add(user)
    db_session.commit()

    # Create a training job
    training_job = MLTrainingJob(
        model_type="verdict_classifier",
        status="completed",
        started_by=user.id,
        algorithm="random_forest",
        training_data_path="data/training.csv",
        started_at=ist_now(),
    )
    db_session.add(training_job)
    db_session.commit()

    # Create the model
    model = MLModel(
        model_type="verdict_classifier",
        version="v2.0",
        model_path="models/verdict_model_v2.0.pkl",
        training_job_id=training_job.id,
        is_active=False,
        created_by=user.id,
        created_at=ist_now(),
    )
    db_session.add(model)
    db_session.commit()
    return model


@pytest.fixture
def sample_price_model(db_session):
    """Create a price regressor model in database"""
    # Create a user for created_by
    user = Users(
        email="ml_admin_price@example.com",
        password_hash="hash",
        created_at=ist_now(),
    )
    db_session.add(user)
    db_session.commit()

    # Create a training job
    training_job = MLTrainingJob(
        model_type="price_regressor",
        status="completed",
        started_by=user.id,
        algorithm="random_forest",
        training_data_path="data/training.csv",
        started_at=ist_now(),
    )
    db_session.add(training_job)
    db_session.commit()

    # Create the model
    model = MLModel(
        model_type="price_regressor",
        version="v1.0",
        model_path="models/price_model_v1.0.pkl",
        training_job_id=training_job.id,
        is_active=True,
        created_by=user.id,
        created_at=ist_now(),
    )
    db_session.add(model)
    db_session.commit()
    return model


class TestMLModelResolver:
    """Tests for ML model resolver functions"""

    def test_get_model_path_from_version_success(self, db_session, sample_ml_model):
        """Test getting model path from version when model exists"""
        # Create temporary model file
        model_path = Path("models/verdict_model_v1.0.pkl")
        model_path.parent.mkdir(exist_ok=True)
        model_path.touch()

        try:
            result = get_model_path_from_version(db_session, "verdict_classifier", "v1.0")

            # Normalize path separators (Windows vs Unix)
            expected_path = str(Path("models/verdict_model_v1.0.pkl"))
            assert (
                result == expected_path
                or result.replace("\\", "/") == "models/verdict_model_v1.0.pkl"
            )
        finally:
            if model_path.exists():
                model_path.unlink()

    def test_get_model_path_from_version_not_found(self, db_session):
        """Test getting model path when version doesn't exist"""
        result = get_model_path_from_version(db_session, "verdict_classifier", "v999.0")

        assert result is None

    def test_get_model_path_from_version_none(self, db_session):
        """Test getting model path when version is None"""
        result = get_model_path_from_version(db_session, "verdict_classifier", None)

        assert result is None

    def test_get_model_path_from_version_file_not_exists(self, db_session, sample_ml_model):
        """Test getting model path when file doesn't exist"""
        result = get_model_path_from_version(db_session, "verdict_classifier", "v1.0")

        # Should return None when file doesn't exist
        assert result is None

    def test_get_model_path_from_version_wrong_type(self, db_session, sample_ml_model):
        """Test getting model path with wrong model type"""
        result = get_model_path_from_version(db_session, "price_regressor", "v1.0")

        assert result is None

    def test_get_active_model_path_success(self, db_session, sample_ml_model):
        """Test getting active model path when active model exists"""
        # Create temporary model file
        model_path = Path("models/verdict_model_v1.0.pkl")
        model_path.parent.mkdir(exist_ok=True)
        model_path.touch()

        try:
            result = get_active_model_path(db_session, "verdict_classifier")

            # Normalize path separators (Windows vs Unix)
            expected_path = str(Path("models/verdict_model_v1.0.pkl"))
            assert (
                result == expected_path
                or result.replace("\\", "/") == "models/verdict_model_v1.0.pkl"
            )
        finally:
            if model_path.exists():
                model_path.unlink()

    def test_get_active_model_path_not_found(self, db_session):
        """Test getting active model path when no active model exists"""
        result = get_active_model_path(db_session, "verdict_classifier")

        assert result is None

    def test_get_active_model_path_inactive_model(self, db_session, sample_ml_model_v2):
        """Test getting active model path when only inactive model exists"""
        result = get_active_model_path(db_session, "verdict_classifier")

        assert result is None

    def test_get_active_model_path_wrong_type(self, db_session, sample_price_model):
        """Test getting active model path with wrong model type"""
        result = get_active_model_path(db_session, "verdict_classifier")

        assert result is None

    def test_get_model_path_from_version_multiple_models(
        self, db_session, sample_ml_model, sample_ml_model_v2
    ):
        """Test getting model path when multiple models exist"""
        # Create temporary model file
        model_path = Path("models/verdict_model_v1.0.pkl")
        model_path.parent.mkdir(exist_ok=True)
        model_path.touch()

        try:
            # Should get v1.0 when requested
            result_v1 = get_model_path_from_version(db_session, "verdict_classifier", "v1.0")
            assert result_v1 is not None, "v1.0 model path should not be None"
            expected_v1 = str(Path("models/verdict_model_v1.0.pkl"))
            assert (
                result_v1 == expected_v1
                or result_v1.replace("\\", "/") == "models/verdict_model_v1.0.pkl"
            )

            # Should get v2.0 when requested
            model_path_v2 = Path("models/verdict_model_v2.0.pkl")
            model_path_v2.touch()
            try:
                result_v2 = get_model_path_from_version(db_session, "verdict_classifier", "v2.0")
                assert result_v2 is not None, "v2.0 model path should not be None"
                expected_v2 = str(Path("models/verdict_model_v2.0.pkl"))
                assert (
                    result_v2 == expected_v2
                    or result_v2.replace("\\", "/") == "models/verdict_model_v2.0.pkl"
                )
            finally:
                if model_path_v2.exists():
                    model_path_v2.unlink()
        finally:
            if model_path.exists():
                model_path.unlink()

    def test_get_model_path_from_version_database_error(self, db_session):
        """Test handling of database errors"""
        # Mock database execute to raise exception
        with patch.object(db_session, "execute") as mock_execute:
            mock_execute.side_effect = Exception("Database error")

            result = get_model_path_from_version(db_session, "verdict_classifier", "v1.0")

            # Should return None on error
            assert result is None

    def test_get_active_model_path_database_error(self, db_session):
        """Test handling of database errors in get_active_model_path"""
        # Mock database execute to raise exception
        with patch.object(db_session, "execute") as mock_execute:
            mock_execute.side_effect = Exception("Database error")

            result = get_active_model_path(db_session, "verdict_classifier")

            # Should return None on error
            assert result is None
