from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, status

from server.app.routers import ml
from server.app.schemas.ml import MLTrainingRequest
from src.infrastructure.db.models import UserRole


class DummyUser(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            email=kwargs.get("email", "admin@example.com"),
            name=kwargs.get("name", "Admin"),
            role=kwargs.get("role", UserRole.ADMIN),
        )


class DummyTrainingJob(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            started_by=kwargs.get("started_by", 1),
            status=kwargs.get("status", "pending"),
            model_type=kwargs.get("model_type", "verdict_classifier"),
            algorithm=kwargs.get("algorithm", "random_forest"),
            training_data_path=kwargs.get("training_data_path", "/data/train.csv"),
            started_at=kwargs.get("started_at", datetime.now()),
            completed_at=kwargs.get("completed_at", None),
            model_path=kwargs.get("model_path", None),
            accuracy=kwargs.get("accuracy", None),
            error_message=kwargs.get("error_message", None),
            logs=kwargs.get("logs", None),
        )


class DummyMLModel(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            model_type=kwargs.get("model_type", "verdict_classifier"),
            version=kwargs.get("version", "v1.0"),
            model_path=kwargs.get("model_path", "/models/model.pkl"),
            accuracy=kwargs.get("accuracy", 0.85),
            training_job_id=kwargs.get("training_job_id", 1),
            is_active=kwargs.get("is_active", False),
            created_at=kwargs.get("created_at", datetime.now()),
            created_by=kwargs.get("created_by", 1),
        )


class DummyJobRepo:
    def __init__(self):
        self.jobs_by_id = {}
        self.list_called = []
        self.create_called = []

    def get(self, job_id):
        return self.jobs_by_id.get(job_id)

    def list(self, status=None, model_type=None, limit=100):
        self.list_called.append({"status": status, "model_type": model_type, "limit": limit})
        return list(self.jobs_by_id.values())[:limit]

    def create(self, started_by, model_type, algorithm, training_data_path):
        self.create_called.append(
            {
                "started_by": started_by,
                "model_type": model_type,
                "algorithm": algorithm,
                "training_data_path": training_data_path,
            }
        )
        job = DummyTrainingJob(
            id=len(self.jobs_by_id) + 1,
            started_by=started_by,
            model_type=model_type,
            algorithm=algorithm,
            training_data_path=training_data_path,
        )
        self.jobs_by_id[job.id] = job
        return job


class DummyModelRepo:
    def __init__(self):
        self.models_by_id = {}
        self.list_called = []

    def get(self, model_id):
        return self.models_by_id.get(model_id)

    def list(self, model_type=None, is_active=None):
        self.list_called.append({"model_type": model_type, "is_active": is_active})
        return list(self.models_by_id.values())

    def set_active(self, model_id):
        model = self.models_by_id.get(model_id)
        if model:
            # Deactivate all other models of the same type
            for m in self.models_by_id.values():
                if m.model_type == model.model_type:
                    m.is_active = False
            model.is_active = True
        return model


class DummyMLTrainingService:
    def __init__(self, db):
        self.db = db
        self.job_repo = DummyJobRepo()
        self.model_repo = DummyModelRepo()
        self.start_training_job_called = []

    def start_training_job(self, started_by, config):
        self.start_training_job_called.append({"started_by": started_by, "config": config})
        return self.job_repo.create(
            started_by=started_by,
            model_type=config.model_type,
            algorithm=config.algorithm,
            training_data_path=config.training_data_path,
        )


@pytest.fixture
def ml_service(monkeypatch):
    service = DummyMLTrainingService(db=None)
    monkeypatch.setattr(ml, "MLTrainingService", lambda db: service)
    monkeypatch.setattr(ml, "get_ml_training_service", lambda db: service)
    return service


@pytest.fixture
def admin_user():
    return DummyUser(id=99, email="admin@example.com", role=UserRole.ADMIN)


@pytest.fixture
def background_tasks():
    tasks = MagicMock()
    tasks.add_task = MagicMock()
    return tasks


# Helper function tests
def test_to_config():
    """Test _to_config helper function"""
    request = MLTrainingRequest(
        model_type="verdict_classifier",
        algorithm="random_forest",
        training_data_path="/data/train.csv",
        hyperparameters={"n_estimators": 100},
        notes="Test training",
        auto_activate=True,
    )

    config = ml._to_config(request)

    assert config.model_type == "verdict_classifier"
    assert config.algorithm == "random_forest"
    assert config.training_data_path == "/data/train.csv"
    assert config.hyperparameters == {"n_estimators": 100}
    assert config.notes == "Test training"
    assert config.auto_activate is True


def test_to_config_defaults():
    """Test _to_config with default values"""
    request = MLTrainingRequest(
        model_type="price_regressor",
        algorithm="xgboost",
        training_data_path="/data/train.csv",
    )

    config = ml._to_config(request)

    assert config.model_type == "price_regressor"
    assert config.hyperparameters == {}
    assert config.notes is None
    assert config.auto_activate is False


# POST /admin/ml/train tests
def test_start_ml_training_success(ml_service, admin_user, background_tasks):
    """Test start_ml_training successfully creates a job"""
    request = MLTrainingRequest(
        model_type="verdict_classifier",
        algorithm="random_forest",
        training_data_path="/data/train.csv",
        hyperparameters={"n_estimators": 100},
        notes="Test notes",
        auto_activate=False,
    )

    result = ml.start_ml_training(
        request=request,
        background_tasks=background_tasks,
        admin=admin_user,
        service=ml_service,
    )

    assert result.id is not None
    assert result.model_type == "verdict_classifier"
    assert result.algorithm == "random_forest"
    assert result.status == "pending"
    assert result.started_by == admin_user.id
    assert len(ml_service.start_training_job_called) == 1
    assert background_tasks.add_task.called
    # Verify background task was added with correct args
    call_args = background_tasks.add_task.call_args
    assert call_args[0][0] == ml._run_training_job_async
    assert call_args[0][1] == result.id


def test_start_ml_training_with_auto_activate(ml_service, admin_user, background_tasks):
    """Test start_ml_training with auto_activate=True"""
    request = MLTrainingRequest(
        model_type="price_regressor",
        algorithm="xgboost",
        training_data_path="/data/train.csv",
        auto_activate=True,
    )

    result = ml.start_ml_training(
        request=request,
        background_tasks=background_tasks,
        admin=admin_user,
        service=ml_service,
    )

    assert result.model_type == "price_regressor"
    assert result.algorithm == "xgboost"
    assert background_tasks.add_task.called


def test_start_ml_training_minimal_request(ml_service, admin_user, background_tasks):
    """Test start_ml_training with minimal request (no optional fields)"""
    request = MLTrainingRequest(
        model_type="verdict_classifier",
        algorithm="logistic_regression",
        training_data_path="/data/train.csv",
    )

    result = ml.start_ml_training(
        request=request,
        background_tasks=background_tasks,
        admin=admin_user,
        service=ml_service,
    )

    assert result is not None
    assert result.training_data_path == "/data/train.csv"


# GET /admin/ml/jobs tests
def test_list_training_jobs_no_filters(ml_service, admin_user):
    """Test list_training_jobs with no filters"""
    job1 = DummyTrainingJob(id=1, model_type="verdict_classifier")
    job2 = DummyTrainingJob(id=2, model_type="price_regressor")
    ml_service.job_repo.jobs_by_id = {1: job1, 2: job2}

    result = ml.list_training_jobs(
        status_filter=None,
        model_type=None,
        limit=100,
        admin=admin_user,
        service=ml_service,
    )

    assert len(result.jobs) == 2
    assert len(ml_service.job_repo.list_called) == 1
    call_args = ml_service.job_repo.list_called[0]
    assert call_args["status"] is None
    assert call_args["model_type"] is None
    assert call_args["limit"] == 100


def test_list_training_jobs_with_status_filter(ml_service, admin_user):
    """Test list_training_jobs with status filter"""
    job1 = DummyTrainingJob(id=1, status="completed")
    ml_service.job_repo.jobs_by_id = {1: job1}

    ml.list_training_jobs(
        status_filter="completed",
        model_type=None,
        limit=100,
        admin=admin_user,
        service=ml_service,
    )

    call_args = ml_service.job_repo.list_called[0]
    assert call_args["status"] == "completed"


def test_list_training_jobs_with_model_type_filter(ml_service, admin_user):
    """Test list_training_jobs with model_type filter"""
    ml.list_training_jobs(
        status_filter=None,
        model_type="verdict_classifier",
        limit=100,
        admin=admin_user,
        service=ml_service,
    )

    call_args = ml_service.job_repo.list_called[0]
    assert call_args["model_type"] == "verdict_classifier"


def test_list_training_jobs_with_all_filters(ml_service, admin_user):
    """Test list_training_jobs with all filters"""
    ml.list_training_jobs(
        status_filter="running",
        model_type="price_regressor",
        limit=50,
        admin=admin_user,
        service=ml_service,
    )

    call_args = ml_service.job_repo.list_called[0]
    assert call_args["status"] == "running"
    assert call_args["model_type"] == "price_regressor"
    assert call_args["limit"] == 50


def test_list_training_jobs_custom_limit(ml_service, admin_user):
    """Test list_training_jobs with custom limit"""
    ml.list_training_jobs(
        status_filter=None,
        model_type=None,
        limit=200,
        admin=admin_user,
        service=ml_service,
    )

    call_args = ml_service.job_repo.list_called[0]
    assert call_args["limit"] == 200


def test_list_training_jobs_empty_result(ml_service, admin_user):
    """Test list_training_jobs with empty result"""
    ml_service.job_repo.jobs_by_id = {}

    result = ml.list_training_jobs(
        status_filter=None,
        model_type=None,
        limit=100,
        admin=admin_user,
        service=ml_service,
    )

    assert len(result.jobs) == 0


# GET /admin/ml/jobs/{job_id} tests
def test_get_training_job_success(ml_service, admin_user):
    """Test get_training_job successfully retrieves a job"""
    job = DummyTrainingJob(id=123, model_type="verdict_classifier", status="completed")
    ml_service.job_repo.jobs_by_id[123] = job

    result = ml.get_training_job(job_id=123, admin=admin_user, service=ml_service)

    assert result.id == 123
    assert result.model_type == "verdict_classifier"
    assert result.status == "completed"


def test_get_training_job_not_found(ml_service, admin_user):
    """Test get_training_job with non-existent job_id"""
    with pytest.raises(HTTPException) as exc:
        ml.get_training_job(job_id=999, admin=admin_user, service=ml_service)

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert "Training job not found" in exc.value.detail


# GET /admin/ml/models tests
def test_list_models_no_filters(ml_service, admin_user):
    """Test list_models with no filters"""
    model1 = DummyMLModel(id=1, model_type="verdict_classifier")
    model2 = DummyMLModel(id=2, model_type="price_regressor")
    ml_service.model_repo.models_by_id = {1: model1, 2: model2}

    result = ml.list_models(
        model_type=None,
        active_only=None,
        admin=admin_user,
        service=ml_service,
    )

    assert len(result.models) == 2
    assert len(ml_service.model_repo.list_called) == 1
    call_args = ml_service.model_repo.list_called[0]
    assert call_args["model_type"] is None
    assert call_args["is_active"] is None


def test_list_models_with_model_type_filter(ml_service, admin_user):
    """Test list_models with model_type filter"""
    ml.list_models(
        model_type="verdict_classifier",
        active_only=None,
        admin=admin_user,
        service=ml_service,
    )

    call_args = ml_service.model_repo.list_called[0]
    assert call_args["model_type"] == "verdict_classifier"
    assert call_args["is_active"] is None


def test_list_models_with_active_only_filter(ml_service, admin_user):
    """Test list_models with active_only filter"""
    model1 = DummyMLModel(id=1, is_active=True)
    model2 = DummyMLModel(id=2, is_active=False)
    ml_service.model_repo.models_by_id = {1: model1, 2: model2}

    ml.list_models(
        model_type=None,
        active_only=True,
        admin=admin_user,
        service=ml_service,
    )

    call_args = ml_service.model_repo.list_called[0]
    assert call_args["is_active"] is True


def test_list_models_with_all_filters(ml_service, admin_user):
    """Test list_models with all filters"""
    ml.list_models(
        model_type="price_regressor",
        active_only=False,
        admin=admin_user,
        service=ml_service,
    )

    call_args = ml_service.model_repo.list_called[0]
    assert call_args["model_type"] == "price_regressor"
    assert call_args["is_active"] is False


def test_list_models_empty_result(ml_service, admin_user):
    """Test list_models with empty result"""
    ml_service.model_repo.models_by_id = {}

    result = ml.list_models(
        model_type=None,
        active_only=None,
        admin=admin_user,
        service=ml_service,
    )

    assert len(result.models) == 0


# POST /admin/ml/models/{model_id}/activate tests
def test_activate_model_success(ml_service, admin_user):
    """Test activate_model successfully activates a model"""
    model = DummyMLModel(
        id=123,
        model_type="verdict_classifier",
        version="v2.0",
        is_active=False,
    )
    ml_service.model_repo.models_by_id[123] = model

    result = ml.activate_model(model_id=123, admin=admin_user, service=ml_service)

    assert result.message == "Model v2.0 activated for verdict_classifier"
    assert result.model.id == 123
    assert result.model.is_active is True
    assert model.is_active is True


def test_activate_model_not_found(ml_service, admin_user):
    """Test activate_model with non-existent model_id"""
    with pytest.raises(HTTPException) as exc:
        ml.activate_model(model_id=999, admin=admin_user, service=ml_service)

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert "Model not found" in exc.value.detail


def test_activate_model_deactivates_others(ml_service, admin_user):
    """Test activate_model deactivates other models of same type"""
    model1 = DummyMLModel(
        id=1,
        model_type="verdict_classifier",
        version="v1.0",
        is_active=True,
    )
    model2 = DummyMLModel(
        id=2,
        model_type="verdict_classifier",
        version="v2.0",
        is_active=False,
    )
    model3 = DummyMLModel(
        id=3,
        model_type="price_regressor",
        version="v1.0",
        is_active=True,
    )
    ml_service.model_repo.models_by_id = {1: model1, 2: model2, 3: model3}

    result = ml.activate_model(model_id=2, admin=admin_user, service=ml_service)

    assert result.model.is_active is True
    assert model2.is_active is True
    # model1 should be deactivated (same type)
    assert model1.is_active is False
    # model3 should remain active (different type)
    assert model3.is_active is True


def test_activate_model_different_types(ml_service, admin_user):
    """Test activate_model doesn't affect models of different types"""
    model1 = DummyMLModel(
        id=1,
        model_type="verdict_classifier",
        version="v1.0",
        is_active=True,
    )
    model2 = DummyMLModel(
        id=2,
        model_type="price_regressor",
        version="v1.0",
        is_active=False,
    )
    ml_service.model_repo.models_by_id = {1: model1, 2: model2}

    result = ml.activate_model(model_id=2, admin=admin_user, service=ml_service)

    assert result.model.is_active is True
    # model1 should remain active (different type)
    assert model1.is_active is True


# Edge cases
def test_start_ml_training_background_task_args(ml_service, admin_user, background_tasks):
    """Test that background task receives correct arguments"""
    request = MLTrainingRequest(
        model_type="verdict_classifier",
        algorithm="random_forest",
        training_data_path="/data/train.csv",
        hyperparameters={"max_depth": 10},
        notes="Test",
        auto_activate=True,
    )

    result = ml.start_ml_training(
        request=request,
        background_tasks=background_tasks,
        admin=admin_user,
        service=ml_service,
    )

    # Verify background task was added
    assert background_tasks.add_task.called
    call_args = background_tasks.add_task.call_args[0]

    # First arg should be the function
    assert call_args[0] == ml._run_training_job_async
    # Second arg should be job_id
    assert call_args[1] == result.id
    # Third arg should be config dict
    assert isinstance(call_args[2], dict)
    assert call_args[2]["model_type"] == "verdict_classifier"
    assert call_args[2]["algorithm"] == "random_forest"
    assert call_args[2]["hyperparameters"] == {"max_depth": 10}


def test_list_training_jobs_respects_limit(ml_service, admin_user):
    """Test list_training_jobs respects limit parameter"""
    # Create more jobs than limit
    for i in range(10):
        ml_service.job_repo.jobs_by_id[i + 1] = DummyTrainingJob(id=i + 1)

    ml.list_training_jobs(
        status_filter=None,
        model_type=None,
        limit=5,
        admin=admin_user,
        service=ml_service,
    )

    # The result should respect the limit (though our dummy repo just returns all)
    call_args = ml_service.job_repo.list_called[0]
    assert call_args["limit"] == 5


def test_run_training_job_async(monkeypatch):
    """Test _run_training_job_async background task function"""
    from src.application.services.ml_training_service import TrainingJobConfig  # noqa: PLC0415

    mock_db = MagicMock()
    mock_service = MagicMock()
    mock_service.run_training_job = MagicMock()

    # Mock SessionLocal to return our mock_db
    mock_session_local = MagicMock(return_value=mock_db)
    monkeypatch.setattr(ml, "SessionLocal", mock_session_local)
    monkeypatch.setattr(ml, "MLTrainingService", lambda db: mock_service)

    job_id = 123
    config_data = {
        "model_type": "verdict_classifier",
        "algorithm": "random_forest",
        "training_data_path": "/data/train.csv",
        "hyperparameters": {},
        "notes": None,
        "auto_activate": False,
    }

    # Call the async function
    ml._run_training_job_async(job_id, config_data)

    # Verify SessionLocal was called
    mock_session_local.assert_called_once()

    # Verify service was created with the db
    assert mock_service.run_training_job.called
    call_args = mock_service.run_training_job.call_args
    assert call_args[1]["job_id"] == job_id
    assert isinstance(call_args[1]["config"], TrainingJobConfig)
    assert call_args[1]["config"].model_type == "verdict_classifier"

    # Verify db.close() was called (in finally block)
    mock_db.close.assert_called_once()


def test_get_ml_training_service(monkeypatch):
    """Test get_ml_training_service dependency function"""
    mock_db = MagicMock()
    mock_service_instance = MagicMock()
    mock_service_class = MagicMock(return_value=mock_service_instance)
    monkeypatch.setattr(ml, "MLTrainingService", mock_service_class)

    result = ml.get_ml_training_service(db=mock_db)

    assert result == mock_service_instance
    mock_service_class.assert_called_once_with(mock_db)
