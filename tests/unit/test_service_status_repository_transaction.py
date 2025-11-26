"""
Tests for ServiceStatusRepository transaction handling.

Ensures that repository methods use flush() instead of commit() to avoid
nested transaction conflicts when called from within API endpoints.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.db.base import Base
from src.infrastructure.db.models import ServiceStatus, Users
from src.infrastructure.persistence.service_status_repository import ServiceStatusRepository


@pytest.fixture
def db_session():
    """Create in-memory test database"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Create test user
    user = Users(
        email="test@example.com",
        name="Test User",
        password_hash="dummy_hash"
    )
    session.add(user)
    session.commit()
    
    yield session, user.id
    
    session.close()


def test_update_running_uses_flush_not_commit(db_session):
    """Test that update_running uses flush() and doesn't commit"""
    session, user_id = db_session
    repo = ServiceStatusRepository(session)
    
    # Start a transaction
    session.begin_nested()
    
    # This should work without raising "cannot commit in prepared state"
    status = repo.update_running(user_id=user_id, running=True)
    
    assert status.service_running is True
    assert status.user_id == user_id
    
    # Changes should be flushed but not committed yet
    # Rollback should be possible
    session.rollback()


def test_update_heartbeat_uses_flush_not_commit(db_session):
    """Test that update_heartbeat uses flush() and doesn't commit"""
    session, user_id = db_session
    repo = ServiceStatusRepository(session)
    
    # Start a transaction
    session.begin_nested()
    
    # This should work without raising errors
    status = repo.update_heartbeat(user_id=user_id)
    
    assert status.last_heartbeat is not None
    assert status.user_id == user_id
    
    # Should be able to rollback
    session.rollback()


def test_update_task_execution_uses_flush_not_commit(db_session):
    """Test that update_task_execution uses flush() and doesn't commit"""
    session, user_id = db_session
    repo = ServiceStatusRepository(session)
    
    session.begin_nested()
    
    status = repo.update_task_execution(user_id=user_id)
    
    assert status.last_task_execution is not None
    assert status.user_id == user_id
    
    session.rollback()


def test_increment_error_uses_flush_not_commit(db_session):
    """Test that increment_error uses flush() and doesn't commit"""
    session, user_id = db_session
    repo = ServiceStatusRepository(session)
    
    session.begin_nested()
    
    status = repo.increment_error(user_id=user_id, error_message="Test error")
    
    assert status.error_count == 1
    assert status.last_error == "Test error"
    assert status.user_id == user_id
    
    session.rollback()


def test_reset_errors_uses_flush_not_commit(db_session):
    """Test that reset_errors uses flush() and doesn't commit"""
    session, user_id = db_session
    repo = ServiceStatusRepository(session)
    
    # Set up error state
    repo.increment_error(user_id=user_id, error_message="Test error")
    session.commit()
    
    # Start new transaction
    session.begin_nested()
    
    status = repo.reset_errors(user_id=user_id)
    
    assert status.error_count == 0
    assert status.last_error is None
    
    session.rollback()


def test_multiple_operations_in_single_transaction(db_session):
    """Test that multiple repository operations can be done in one transaction"""
    session, user_id = db_session
    repo = ServiceStatusRepository(session)
    
    # Start transaction
    session.begin_nested()
    
    # Multiple operations should all work
    repo.update_running(user_id=user_id, running=True)
    repo.update_heartbeat(user_id=user_id)
    repo.update_task_execution(user_id=user_id)
    
    # All should be flushed but not committed
    status = repo.get(user_id=user_id)
    assert status.service_running is True
    assert status.last_heartbeat is not None
    assert status.last_task_execution is not None
    
    # Should be able to rollback all changes
    session.rollback()
    
    status = repo.get(user_id=user_id)
    assert status is None or status.service_running is False


def test_get_or_create_commits_when_creating(db_session):
    """Test that get_or_create still commits when creating new record"""
    session, user_id = db_session
    repo = ServiceStatusRepository(session)
    
    # This should create and commit
    status = repo.get_or_create(user_id=user_id)
    
    assert status.user_id == user_id
    assert status.service_running is False
    
    # Should be persisted
    session.rollback()  # Try to rollback
    status = repo.get(user_id=user_id)
    assert status is not None  # Still exists because get_or_create committed


def test_caller_controls_commit(db_session):
    """Test that the caller (API endpoint) controls when to commit"""
    session, user_id = db_session
    repo = ServiceStatusRepository(session)
    
    # Caller starts transaction
    session.begin_nested()
    
    # Repository operations
    repo.update_running(user_id=user_id, running=True)
    repo.update_heartbeat(user_id=user_id)
    
    # Caller decides to commit
    session.commit()
    
    # Changes should be persisted
    status = repo.get(user_id=user_id)
    assert status.service_running is True
    assert status.last_heartbeat is not None

