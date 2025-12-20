"""
Unit tests for Config Converter ML Configuration Enhancements

Tests for ML configuration enhancements:
- ml_enabled from user config
- ml_model_version resolution
- Model path resolution from database
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.application.services.config_converter import (
    _resolve_ml_model_path,
    user_config_to_strategy_config,
)
from src.infrastructure.db.models import (
    MLModel,
    MLTrainingJob,
    Users,
    UserTradingConfig,
)
from src.infrastructure.db.timezone_utils import ist_now
from utils.logger import logger


@pytest.fixture
def sample_user_config(db_session):
    """Create a sample UserTradingConfig with ML settings"""
    user = Users(
        email="test_ml@example.com",
        password_hash="hash",
        created_at=ist_now(),
    )
    db_session.add(user)
    db_session.commit()

    config = UserTradingConfig(
        user_id=user.id,
        rsi_period=14,
        rsi_oversold=25.0,
        user_capital=300000.0,
        # ML Configuration
        ml_enabled=True,
        ml_model_version="v1.0",
        ml_confidence_threshold=0.7,
        ml_combine_with_rules=True,
    )
    db_session.add(config)
    db_session.commit()
    return config


@pytest.fixture
def sample_user_config_ml_disabled(db_session):
    """Create a sample UserTradingConfig with ML disabled"""
    user = Users(
        email="test_ml_disabled@example.com",
        password_hash="hash",
        created_at=ist_now(),
    )
    db_session.add(user)
    db_session.commit()

    config = UserTradingConfig(
        user_id=user.id,
        rsi_period=14,
        rsi_oversold=25.0,
        user_capital=300000.0,
        # ML Configuration - disabled
        ml_enabled=False,
        ml_model_version=None,
        ml_confidence_threshold=0.5,
        ml_combine_with_rules=True,
    )
    db_session.add(config)
    db_session.commit()
    return config


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


class TestMLConfigurationEnhancements:
    """Tests for ML configuration enhancements"""

    def test_ml_enabled_passed_through(self, sample_user_config):
        """Test that ml_enabled from user config is passed through (not hardcoded)"""
        strategy_config = user_config_to_strategy_config(sample_user_config)

        assert strategy_config.ml_enabled is True, "ml_enabled should be True from user config"
        assert strategy_config.ml_enabled == sample_user_config.ml_enabled

    def test_ml_enabled_false_passed_through(self, sample_user_config_ml_disabled):
        """Test that ml_enabled=False from user config is passed through"""
        strategy_config = user_config_to_strategy_config(sample_user_config_ml_disabled)

        assert strategy_config.ml_enabled is False, "ml_enabled should be False from user config"
        assert strategy_config.ml_enabled == sample_user_config_ml_disabled.ml_enabled

    def test_ml_confidence_threshold_passed_through(self, sample_user_config):
        """Test that ml_confidence_threshold is passed through"""
        strategy_config = user_config_to_strategy_config(sample_user_config)

        assert strategy_config.ml_confidence_threshold == 0.7
        assert strategy_config.ml_confidence_threshold == sample_user_config.ml_confidence_threshold

    def test_ml_combine_with_rules_passed_through(self, sample_user_config):
        """Test that ml_combine_with_rules is passed through"""
        strategy_config = user_config_to_strategy_config(sample_user_config)

        assert strategy_config.ml_combine_with_rules is True
        assert strategy_config.ml_combine_with_rules == sample_user_config.ml_combine_with_rules

    def test_ml_model_version_resolution_with_db_session(
        self, sample_user_config, sample_ml_model, db_session
    ):
        """Test that ml_model_version is resolved to model path when db_session provided"""
        # Create a temporary model file
        model_path = Path("models/verdict_model_v1.0.pkl")
        model_path.parent.mkdir(exist_ok=True)
        model_path.touch()

        try:
            strategy_config = user_config_to_strategy_config(
                sample_user_config, db_session=db_session
            )

            # Should resolve to the model path from database (normalize path separators)
            expected_path = str(Path("models/verdict_model_v1.0.pkl"))
            assert (
                strategy_config.ml_verdict_model_path == expected_path
                or strategy_config.ml_verdict_model_path.replace("\\", "/")
                == "models/verdict_model_v1.0.pkl"
            )
        finally:
            # Cleanup
            if model_path.exists():
                model_path.unlink()

    def test_ml_model_version_resolution_without_db_session(self, sample_user_config):
        """Test that default path is used when db_session is not provided"""
        strategy_config = user_config_to_strategy_config(sample_user_config, db_session=None)

        # Should use default path when no db_session
        assert strategy_config.ml_verdict_model_path == "models/verdict_model_random_forest.pkl"

    def test_ml_model_version_resolution_no_version(self, sample_user_config_ml_disabled):
        """Test that default path is used when ml_model_version is None"""
        strategy_config = user_config_to_strategy_config(
            sample_user_config_ml_disabled, db_session=Mock()
        )

        # Should use default path when version is None
        assert strategy_config.ml_verdict_model_path == "models/verdict_model_random_forest.pkl"

    def test_ml_model_version_resolution_version_not_found(self, sample_user_config, db_session):
        """Test that default path is used when version not found in database"""
        # Use a version that doesn't exist
        sample_user_config.ml_model_version = "v999.0"

        strategy_config = user_config_to_strategy_config(sample_user_config, db_session=db_session)

        # Should fallback to default path
        assert strategy_config.ml_verdict_model_path == "models/verdict_model_random_forest.pkl"

    def test_resolve_ml_model_path_with_version(self, db_session, sample_ml_model):
        """Test _resolve_ml_model_path with valid version"""
        # Create a temporary model file
        model_path = Path("models/verdict_model_v1.0.pkl")
        model_path.parent.mkdir(exist_ok=True)
        model_path.touch()

        try:
            resolved_path = _resolve_ml_model_path("v1.0", "verdict_classifier", db_session)

            # Normalize path separators (Windows vs Unix)
            expected_path = str(Path("models/verdict_model_v1.0.pkl"))
            assert (
                resolved_path == expected_path
                or resolved_path.replace("\\", "/") == "models/verdict_model_v1.0.pkl"
            )
        finally:
            if model_path.exists():
                model_path.unlink()

    def test_resolve_ml_model_path_no_version(self, db_session):
        """Test _resolve_ml_model_path with None version"""
        resolved_path = _resolve_ml_model_path(None, "verdict_classifier", db_session)

        assert resolved_path == "models/verdict_model_random_forest.pkl"

    def test_resolve_ml_model_path_no_db_session(self):
        """Test _resolve_ml_model_path without db_session"""
        resolved_path = _resolve_ml_model_path("v1.0", "verdict_classifier", None)

        assert resolved_path == "models/verdict_model_random_forest.pkl"

    def test_resolve_ml_model_path_version_not_found(self, db_session):
        """Test _resolve_ml_model_path with version not in database"""
        resolved_path = _resolve_ml_model_path("v999.0", "verdict_classifier", db_session)

        assert resolved_path == "models/verdict_model_random_forest.pkl"

    def test_resolve_ml_model_path_file_not_exists(self, db_session, sample_ml_model):
        """Test _resolve_ml_model_path when model file doesn't exist"""
        # Model in DB but file doesn't exist
        resolved_path = _resolve_ml_model_path("v1.0", "verdict_classifier", db_session)

        # Should fallback to default
        assert resolved_path == "models/verdict_model_random_forest.pkl"

    def test_all_ml_settings_passed_through(self, sample_user_config):
        """Test that all ML settings are properly passed through"""
        strategy_config = user_config_to_strategy_config(sample_user_config)

        assert strategy_config.ml_enabled == sample_user_config.ml_enabled
        assert strategy_config.ml_confidence_threshold == sample_user_config.ml_confidence_threshold
        assert strategy_config.ml_combine_with_rules == sample_user_config.ml_combine_with_rules
        # ml_verdict_model_path is resolved, so we just check it's set
        assert strategy_config.ml_verdict_model_path is not None
        assert isinstance(strategy_config.ml_verdict_model_path, str)

    def test_resolve_ml_model_path_exception_handling(self, db_session):
        """Test that _resolve_ml_model_path handles exceptions gracefully"""

        # Mock get_model_path_from_version to raise an exception
        with patch("utils.ml_model_resolver.get_model_path_from_version") as mock_resolver:
            mock_resolver.side_effect = Exception("Database connection error")

            # Should return default path on exception
            resolved_path = _resolve_ml_model_path("v1.0", "verdict_classifier", db_session)
            assert resolved_path == "models/verdict_model_random_forest.pkl"

    def test_resolve_ml_model_path_warning_logged(self, db_session):
        """Test that warning is logged when version not found"""
        # Mock get_model_path_from_version to return None (version not found)
        with patch("utils.ml_model_resolver.get_model_path_from_version", return_value=None):
            with patch.object(logger, "warning") as mock_warning:
                resolved_path = _resolve_ml_model_path("v999.0", "verdict_classifier", db_session)

                # Should log warning and return default
                assert resolved_path == "models/verdict_model_random_forest.pkl"
                mock_warning.assert_called_once()
                assert "not found in database" in str(mock_warning.call_args)
