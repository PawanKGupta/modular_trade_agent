"""Unit tests for Phase 1.1 new database models.

Tests cover:
- ServiceStatus
- ServiceTaskExecution
- ServiceLog
- ErrorLog
- UserTradingConfig
- MLTrainingJob
- MLModel
- UserNotificationPreferences
- Notification
- AuditLog

Target: >80% coverage
"""

from datetime import datetime, time

import pytest
from sqlalchemy.exc import IntegrityError

from src.infrastructure.db.models import (
    AuditLog,
    ErrorLog,
    MLModel,
    MLTrainingJob,
    Notification,
    ServiceLog,
    ServiceStatus,
    ServiceTaskExecution,
    UserNotificationPreferences,
    UserRole,
    Users,
    UserTradingConfig,
)


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing"""
    user = Users(
        email="test@example.com",
        name="Test User",
        password_hash="hashed_password",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_admin_user(db_session):
    """Create a sample admin user for testing"""
    user = Users(
        email="admin@example.com",
        name="Admin User",
        password_hash="hashed_password",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestServiceStatus:
    """Tests for ServiceStatus model"""

    def test_create_service_status(self, db_session, sample_user):
        """Test creating a service status record"""
        status = ServiceStatus(
            user_id=sample_user.id,
            service_running=False,
            error_count=0,
        )
        db_session.add(status)
        db_session.commit()
        db_session.refresh(status)

        assert status.id is not None
        assert status.user_id == sample_user.id
        assert status.service_running is False
        assert status.error_count == 0
        assert status.last_heartbeat is None
        assert status.last_task_execution is None
        assert status.last_error is None
        assert status.created_at is not None
        assert status.updated_at is not None

    def test_service_status_unique_per_user(self, db_session, sample_user):
        """Test that each user can only have one service status"""
        status1 = ServiceStatus(user_id=sample_user.id, service_running=False)
        db_session.add(status1)
        db_session.commit()

        status2 = ServiceStatus(user_id=sample_user.id, service_running=True)
        db_session.add(status2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_update_service_status(self, db_session, sample_user):
        """Test updating service status"""
        status = ServiceStatus(
            user_id=sample_user.id,
            service_running=False,
            error_count=0,
        )
        db_session.add(status)
        db_session.commit()

        status.service_running = True
        status.last_heartbeat = datetime.utcnow()
        status.error_count = 1
        status.last_error = "Test error"
        db_session.commit()
        db_session.refresh(status)

        assert status.service_running is True
        assert status.last_heartbeat is not None
        assert status.error_count == 1
        assert status.last_error == "Test error"


class TestServiceTaskExecution:
    """Tests for ServiceTaskExecution model"""

    def test_create_task_execution(self, db_session, sample_user):
        """Test creating a task execution record"""
        task = ServiceTaskExecution(
            user_id=sample_user.id,
            task_name="premarket_retry",
            status="success",
            duration_seconds=5.5,
            details={"symbols_processed": 10},
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        assert task.id is not None
        assert task.user_id == sample_user.id
        assert task.task_name == "premarket_retry"
        assert task.status == "success"
        assert task.duration_seconds == 5.5
        assert task.details == {"symbols_processed": 10}
        assert task.executed_at is not None

    def test_task_execution_without_details(self, db_session, sample_user):
        """Test creating task execution without details"""
        task = ServiceTaskExecution(
            user_id=sample_user.id,
            task_name="sell_monitor",
            status="failed",
            duration_seconds=0.5,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        assert task.details is None

    def test_task_execution_statuses(self, db_session, sample_user):
        """Test different task execution statuses"""
        for status in ["success", "failed", "skipped"]:
            task = ServiceTaskExecution(
                user_id=sample_user.id,
                task_name="test_task",
                status=status,
                duration_seconds=1.0,
            )
            db_session.add(task)
        db_session.commit()

        tasks = db_session.query(ServiceTaskExecution).filter_by(user_id=sample_user.id).all()
        assert len(tasks) == 3
        assert {t.status for t in tasks} == {"success", "failed", "skipped"}


class TestServiceLog:
    """Tests for ServiceLog model"""

    def test_create_service_log(self, db_session, sample_user):
        """Test creating a service log record"""
        log = ServiceLog(
            user_id=sample_user.id,
            level="INFO",
            module="trading_service",
            message="Service started successfully",
            context={"symbol": "RELIANCE", "order_id": 123},
        )
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)

        assert log.id is not None
        assert log.user_id == sample_user.id
        assert log.level == "INFO"
        assert log.module == "trading_service"
        assert log.message == "Service started successfully"
        assert log.context == {"symbol": "RELIANCE", "order_id": 123}
        assert log.timestamp is not None

    def test_service_log_levels(self, db_session, sample_user):
        """Test different log levels"""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in levels:
            log = ServiceLog(
                user_id=sample_user.id,
                level=level,
                module="test",
                message=f"Test {level} message",
            )
            db_session.add(log)
        db_session.commit()

        logs = db_session.query(ServiceLog).filter_by(user_id=sample_user.id).all()
        assert len(logs) == 5
        assert {log.level for log in logs} == set(levels)

    def test_service_log_without_context(self, db_session, sample_user):
        """Test creating log without context"""
        log = ServiceLog(
            user_id=sample_user.id,
            level="INFO",
            module="test",
            message="Simple log message",
        )
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)

        assert log.context is None


class TestErrorLog:
    """Tests for ErrorLog model"""

    def test_create_error_log(self, db_session, sample_user):
        """Test creating an error log record"""
        error = ErrorLog(
            user_id=sample_user.id,
            error_type="ValueError",
            error_message="Invalid input value",
            traceback="Traceback (most recent call last):\n  ...",
            context={"symbol": "RELIANCE", "price": 2500.0},
        )
        db_session.add(error)
        db_session.commit()
        db_session.refresh(error)

        assert error.id is not None
        assert error.user_id == sample_user.id
        assert error.error_type == "ValueError"
        assert error.error_message == "Invalid input value"
        assert "Traceback" in error.traceback
        assert error.context == {"symbol": "RELIANCE", "price": 2500.0}
        assert error.resolved is False
        assert error.resolved_at is None
        assert error.resolved_by is None
        assert error.resolution_notes is None
        assert error.occurred_at is not None

    def test_resolve_error(self, db_session, sample_user, sample_admin_user):
        """Test resolving an error"""
        error = ErrorLog(
            user_id=sample_user.id,
            error_type="ValueError",
            error_message="Test error",
        )
        db_session.add(error)
        db_session.commit()

        error.resolved = True
        error.resolved_at = datetime.utcnow()
        error.resolved_by = sample_admin_user.id
        error.resolution_notes = "Fixed by updating validation logic"
        db_session.commit()
        db_session.refresh(error)

        assert error.resolved is True
        assert error.resolved_at is not None
        assert error.resolved_by == sample_admin_user.id
        assert error.resolution_notes == "Fixed by updating validation logic"

    def test_error_log_without_traceback(self, db_session, sample_user):
        """Test creating error log without traceback"""
        error = ErrorLog(
            user_id=sample_user.id,
            error_type="ValueError",
            error_message="Simple error message",
        )
        db_session.add(error)
        db_session.commit()
        db_session.refresh(error)

        assert error.traceback is None


class TestUserTradingConfig:
    """Tests for UserTradingConfig model"""

    def test_create_trading_config(self, db_session, sample_user):
        """Test creating a user trading config with defaults"""
        config = UserTradingConfig(user_id=sample_user.id)
        db_session.add(config)
        db_session.commit()
        db_session.refresh(config)

        assert config.id is not None
        assert config.user_id == sample_user.id
        # Check defaults
        assert config.rsi_period == 10
        assert config.rsi_oversold == 30.0
        assert config.rsi_extreme_oversold == 20.0
        assert config.rsi_near_oversold == 40.0
        assert config.user_capital == 100000.0
        assert config.max_portfolio_size == 6
        assert config.chart_quality_enabled is True
        assert config.default_target_pct == 0.10
        assert config.ml_enabled is False
        assert config.created_at is not None
        assert config.updated_at is not None

    def test_trading_config_unique_per_user(self, db_session, sample_user):
        """Test that each user can only have one trading config"""
        config1 = UserTradingConfig(user_id=sample_user.id)
        db_session.add(config1)
        db_session.commit()

        config2 = UserTradingConfig(user_id=sample_user.id)
        db_session.add(config2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_trading_config_custom_values(self, db_session, sample_user):
        """Test creating config with custom values"""
        config = UserTradingConfig(
            user_id=sample_user.id,
            rsi_period=14,
            rsi_oversold=25.0,
            user_capital=500000.0,
            max_portfolio_size=10,
            ml_enabled=True,
            ml_model_version="v1.0",
        )
        db_session.add(config)
        db_session.commit()
        db_session.refresh(config)

        assert config.rsi_period == 14
        assert config.rsi_oversold == 25.0
        assert config.user_capital == 500000.0
        assert config.max_portfolio_size == 10
        assert config.ml_enabled is True
        assert config.ml_model_version == "v1.0"

    def test_trading_config_stop_loss_optional(self, db_session, sample_user):
        """Test that stop loss fields are optional"""
        config = UserTradingConfig(user_id=sample_user.id)
        db_session.add(config)
        db_session.commit()
        db_session.refresh(config)

        assert config.default_stop_loss_pct is None
        assert config.tight_stop_loss_pct is None
        assert config.min_stop_loss_pct is None

    def test_trading_config_task_schedule_json(self, db_session, sample_user):
        """Test task_schedule JSON field"""
        schedule = {
            "premarket_retry": "09:00",
            "sell_monitor": "15:00",
        }
        config = UserTradingConfig(
            user_id=sample_user.id,
            task_schedule=schedule,
        )
        db_session.add(config)
        db_session.commit()
        db_session.refresh(config)

        assert config.task_schedule == schedule


class TestMLTrainingJob:
    """Tests for MLTrainingJob model"""

    def test_create_training_job(self, db_session, sample_admin_user):
        """Test creating an ML training job"""
        job = MLTrainingJob(
            started_by=sample_admin_user.id,
            status="pending",
            model_type="verdict_classifier",
            algorithm="random_forest",
            training_data_path="/data/training.csv",
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        assert job.id is not None
        assert job.started_by == sample_admin_user.id
        assert job.status == "pending"
        assert job.model_type == "verdict_classifier"
        assert job.algorithm == "random_forest"
        assert job.training_data_path == "/data/training.csv"
        assert job.started_at is not None
        assert job.completed_at is None
        assert job.model_path is None
        assert job.accuracy is None
        assert job.error_message is None
        assert job.logs is None

    def test_training_job_statuses(self, db_session, sample_admin_user):
        """Test different training job statuses"""
        for status in ["pending", "running", "completed", "failed"]:
            job = MLTrainingJob(
                started_by=sample_admin_user.id,
                status=status,
                model_type="verdict_classifier",
                algorithm="random_forest",
                training_data_path="/data/training.csv",
            )
            db_session.add(job)
        db_session.commit()

        jobs = db_session.query(MLTrainingJob).filter_by(started_by=sample_admin_user.id).all()
        assert len(jobs) == 4
        assert {j.status for j in jobs} == {"pending", "running", "completed", "failed"}

    def test_completed_training_job(self, db_session, sample_admin_user):
        """Test completing a training job"""
        job = MLTrainingJob(
            started_by=sample_admin_user.id,
            status="running",
            model_type="verdict_classifier",
            algorithm="random_forest",
            training_data_path="/data/training.csv",
        )
        db_session.add(job)
        db_session.commit()

        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.model_path = "/models/verdict_classifier_v1.0.pkl"
        job.accuracy = 0.85
        job.logs = "Training completed successfully"
        db_session.commit()
        db_session.refresh(job)

        assert job.status == "completed"
        assert job.completed_at is not None
        assert job.model_path == "/models/verdict_classifier_v1.0.pkl"
        assert job.accuracy == 0.85
        assert job.logs == "Training completed successfully"


class TestMLModel:
    """Tests for MLModel model"""

    def test_create_ml_model(self, db_session, sample_admin_user):
        """Test creating an ML model"""
        # First create a training job
        job = MLTrainingJob(
            started_by=sample_admin_user.id,
            status="completed",
            model_type="verdict_classifier",
            algorithm="random_forest",
            training_data_path="/data/training.csv",
        )
        db_session.add(job)
        db_session.commit()

        model = MLModel(
            model_type="verdict_classifier",
            version="v1.0",
            model_path="/models/verdict_classifier_v1.0.pkl",
            accuracy=0.85,
            training_job_id=job.id,
            is_active=True,
            created_by=sample_admin_user.id,
        )
        db_session.add(model)
        db_session.commit()
        db_session.refresh(model)

        assert model.id is not None
        assert model.model_type == "verdict_classifier"
        assert model.version == "v1.0"
        assert model.model_path == "/models/verdict_classifier_v1.0.pkl"
        assert model.accuracy == 0.85
        assert model.training_job_id == job.id
        assert model.is_active is True
        assert model.created_by == sample_admin_user.id
        assert model.created_at is not None

    def test_ml_model_unique_version_per_type(self, db_session, sample_admin_user):
        """Test that model type and version combination is unique"""
        job = MLTrainingJob(
            started_by=sample_admin_user.id,
            status="completed",
            model_type="verdict_classifier",
            algorithm="random_forest",
            training_data_path="/data/training.csv",
        )
        db_session.add(job)
        db_session.commit()

        model1 = MLModel(
            model_type="verdict_classifier",
            version="v1.0",
            model_path="/models/v1.0.pkl",
            training_job_id=job.id,
            created_by=sample_admin_user.id,
        )
        db_session.add(model1)
        db_session.commit()

        model2 = MLModel(
            model_type="verdict_classifier",
            version="v1.0",  # Same type and version
            model_path="/models/v1.0_duplicate.pkl",
            training_job_id=job.id,
            created_by=sample_admin_user.id,
        )
        db_session.add(model2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_ml_model_different_versions_same_type(self, db_session, sample_admin_user):
        """Test that different versions of same type are allowed"""
        job = MLTrainingJob(
            started_by=sample_admin_user.id,
            status="completed",
            model_type="verdict_classifier",
            algorithm="random_forest",
            training_data_path="/data/training.csv",
        )
        db_session.add(job)
        db_session.commit()

        model1 = MLModel(
            model_type="verdict_classifier",
            version="v1.0",
            model_path="/models/v1.0.pkl",
            training_job_id=job.id,
            created_by=sample_admin_user.id,
        )
        model2 = MLModel(
            model_type="verdict_classifier",
            version="v1.1",  # Different version
            model_path="/models/v1.1.pkl",
            training_job_id=job.id,
            created_by=sample_admin_user.id,
        )
        db_session.add_all([model1, model2])
        db_session.commit()

        models = db_session.query(MLModel).filter_by(model_type="verdict_classifier").all()
        assert len(models) == 2


class TestUserNotificationPreferences:
    """Tests for UserNotificationPreferences model"""

    def test_create_notification_preferences(self, db_session, sample_user):
        """Test creating notification preferences with defaults"""
        prefs = UserNotificationPreferences(user_id=sample_user.id)
        db_session.add(prefs)
        db_session.commit()
        db_session.refresh(prefs)

        assert prefs.id is not None
        assert prefs.user_id == sample_user.id
        # Check defaults
        assert prefs.telegram_enabled is False
        assert prefs.email_enabled is False
        assert prefs.in_app_enabled is True
        assert prefs.notify_service_events is True
        assert prefs.notify_trading_events is True
        assert prefs.notify_system_events is True
        assert prefs.notify_errors is True
        assert prefs.quiet_hours_start is None
        assert prefs.quiet_hours_end is None
        assert prefs.created_at is not None
        assert prefs.updated_at is not None

    def test_notification_preferences_unique_per_user(self, db_session, sample_user):
        """Test that each user can only have one notification preferences record"""
        prefs1 = UserNotificationPreferences(user_id=sample_user.id)
        db_session.add(prefs1)
        db_session.commit()

        prefs2 = UserNotificationPreferences(user_id=sample_user.id)
        db_session.add(prefs2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_notification_preferences_with_telegram(self, db_session, sample_user):
        """Test notification preferences with Telegram enabled"""
        prefs = UserNotificationPreferences(
            user_id=sample_user.id,
            telegram_enabled=True,
            telegram_chat_id="123456789",
        )
        db_session.add(prefs)
        db_session.commit()
        db_session.refresh(prefs)

        assert prefs.telegram_enabled is True
        assert prefs.telegram_chat_id == "123456789"

    def test_notification_preferences_quiet_hours(self, db_session, sample_user):
        """Test notification preferences with quiet hours"""
        prefs = UserNotificationPreferences(
            user_id=sample_user.id,
            quiet_hours_start=time(22, 0),  # 10 PM
            quiet_hours_end=time(8, 0),  # 8 AM
        )
        db_session.add(prefs)
        db_session.commit()
        db_session.refresh(prefs)

        assert prefs.quiet_hours_start == time(22, 0)
        assert prefs.quiet_hours_end == time(8, 0)


class TestNotification:
    """Tests for Notification model"""

    def test_create_notification(self, db_session, sample_user):
        """Test creating a notification"""
        notification = Notification(
            user_id=sample_user.id,
            type="service",
            level="info",
            title="Service Started",
            message="Trading service has been started successfully",
        )
        db_session.add(notification)
        db_session.commit()
        db_session.refresh(notification)

        assert notification.id is not None
        assert notification.user_id == sample_user.id
        assert notification.type == "service"
        assert notification.level == "info"
        assert notification.title == "Service Started"
        assert notification.message == "Trading service has been started successfully"
        assert notification.read is False
        assert notification.read_at is None
        assert notification.created_at is not None
        assert notification.telegram_sent is False
        assert notification.email_sent is False
        assert notification.in_app_delivered is True

    def test_notification_types(self, db_session, sample_user):
        """Test different notification types"""
        types = ["service", "trading", "system", "error"]
        for notif_type in types:
            notification = Notification(
                user_id=sample_user.id,
                type=notif_type,
                level="info",
                title=f"{notif_type.title()} Event",
                message=f"Test {notif_type} notification",
            )
            db_session.add(notification)
        db_session.commit()

        notifications = db_session.query(Notification).filter_by(user_id=sample_user.id).all()
        assert len(notifications) == 4
        assert {n.type for n in notifications} == set(types)

    def test_notification_levels(self, db_session, sample_user):
        """Test different notification levels"""
        levels = ["info", "warning", "error", "critical"]
        for level in levels:
            notification = Notification(
                user_id=sample_user.id,
                type="system",
                level=level,
                title=f"{level.title()} Alert",
                message=f"Test {level} notification",
            )
            db_session.add(notification)
        db_session.commit()

        notifications = db_session.query(Notification).filter_by(user_id=sample_user.id).all()
        assert len(notifications) == 4
        assert {n.level for n in notifications} == set(levels)

    def test_mark_notification_as_read(self, db_session, sample_user):
        """Test marking notification as read"""
        notification = Notification(
            user_id=sample_user.id,
            type="trading",
            level="info",
            title="Order Filled",
            message="Order for RELIANCE has been filled",
        )
        db_session.add(notification)
        db_session.commit()

        notification.read = True
        notification.read_at = datetime.utcnow()
        db_session.commit()
        db_session.refresh(notification)

        assert notification.read is True
        assert notification.read_at is not None

    def test_notification_delivery_status(self, db_session, sample_user):
        """Test notification delivery status tracking"""
        notification = Notification(
            user_id=sample_user.id,
            type="trading",
            level="info",
            title="Order Placed",
            message="Order placed successfully",
        )
        db_session.add(notification)
        db_session.commit()

        notification.telegram_sent = True
        notification.email_sent = True
        db_session.commit()
        db_session.refresh(notification)

        assert notification.telegram_sent is True
        assert notification.email_sent is True
        assert notification.in_app_delivered is True


class TestAuditLog:
    """Tests for AuditLog model"""

    def test_create_audit_log(self, db_session, sample_user):
        """Test creating an audit log"""
        audit = AuditLog(
            user_id=sample_user.id,
            action="create",
            resource_type="order",
            resource_id=123,
            changes={"before": None, "after": {"symbol": "RELIANCE", "quantity": 10}},
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )
        db_session.add(audit)
        db_session.commit()
        db_session.refresh(audit)

        assert audit.id is not None
        assert audit.user_id == sample_user.id
        assert audit.action == "create"
        assert audit.resource_type == "order"
        assert audit.resource_id == 123
        assert audit.changes == {"before": None, "after": {"symbol": "RELIANCE", "quantity": 10}}
        assert audit.ip_address == "192.168.1.1"
        assert audit.user_agent == "Mozilla/5.0"
        assert audit.timestamp is not None

    def test_audit_log_actions(self, db_session, sample_user):
        """Test different audit log actions"""
        actions = ["create", "update", "delete", "login", "logout"]
        for action in actions:
            audit = AuditLog(
                user_id=sample_user.id,
                action=action,
                resource_type="user",
            )
            db_session.add(audit)
        db_session.commit()

        audits = db_session.query(AuditLog).filter_by(user_id=sample_user.id).all()
        assert len(audits) == 5
        assert {a.action for a in audits} == set(actions)

    def test_audit_log_resource_types(self, db_session, sample_user):
        """Test different resource types"""
        resource_types = ["order", "config", "user", "service"]
        for resource_type in resource_types:
            audit = AuditLog(
                user_id=sample_user.id,
                action="update",
                resource_type=resource_type,
            )
            db_session.add(audit)
        db_session.commit()

        audits = db_session.query(AuditLog).filter_by(user_id=sample_user.id).all()
        assert len(audits) == 4
        assert {a.resource_type for a in audits} == set(resource_types)

    def test_audit_log_without_optional_fields(self, db_session, sample_user):
        """Test creating audit log without optional fields"""
        audit = AuditLog(
            user_id=sample_user.id,
            action="login",
            resource_type="user",
        )
        db_session.add(audit)
        db_session.commit()
        db_session.refresh(audit)

        assert audit.resource_id is None
        assert audit.changes is None
        assert audit.ip_address is None
        assert audit.user_agent is None

    def test_audit_log_changes_tracking(self, db_session, sample_user):
        """Test tracking changes in audit log"""
        changes = {
            "before": {"rsi_oversold": 30.0, "user_capital": 200000.0},
            "after": {"rsi_oversold": 25.0, "user_capital": 300000.0},
        }
        audit = AuditLog(
            user_id=sample_user.id,
            action="update",
            resource_type="config",
            resource_id=1,
            changes=changes,
        )
        db_session.add(audit)
        db_session.commit()
        db_session.refresh(audit)

        assert audit.changes == changes
        assert audit.changes["before"]["rsi_oversold"] == 30.0
        assert audit.changes["after"]["rsi_oversold"] == 25.0


class TestModelRelationships:
    """Tests for model relationships and foreign keys"""

    def test_service_status_user_relationship(self, db_session, sample_user):
        """Test ServiceStatus foreign key to Users"""
        status = ServiceStatus(user_id=sample_user.id, service_running=False)
        db_session.add(status)
        db_session.commit()

        # Test that foreign key constraint works
        status.user_id = 99999  # Non-existent user
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_error_log_resolved_by_relationship(self, db_session, sample_user, sample_admin_user):
        """Test ErrorLog foreign key to Users for resolved_by"""
        error = ErrorLog(
            user_id=sample_user.id,
            error_type="ValueError",
            error_message="Test error",
        )
        db_session.add(error)
        db_session.commit()

        error.resolved_by = sample_admin_user.id
        db_session.commit()
        db_session.refresh(error)

        assert error.resolved_by == sample_admin_user.id

    def test_ml_model_training_job_relationship(self, db_session, sample_admin_user):
        """Test MLModel foreign key to MLTrainingJob"""
        job = MLTrainingJob(
            started_by=sample_admin_user.id,
            status="completed",
            model_type="verdict_classifier",
            algorithm="random_forest",
            training_data_path="/data/training.csv",
        )
        db_session.add(job)
        db_session.commit()

        model = MLModel(
            model_type="verdict_classifier",
            version="v1.0",
            model_path="/models/v1.0.pkl",
            training_job_id=job.id,
            created_by=sample_admin_user.id,
        )
        db_session.add(model)
        db_session.commit()

        # Test that foreign key constraint works
        model.training_job_id = 99999  # Non-existent job
        with pytest.raises(IntegrityError):
            db_session.commit()
