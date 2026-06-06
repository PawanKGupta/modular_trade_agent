"""Unit tests for bulk analysis job checkpoint repository."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.infrastructure.db.base import Base
from src.infrastructure.persistence.bulk_analysis_job_repository import BulkAnalysisJobRepository


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_job_create_resume_cursor(db_session):
    repo = BulkAnalysisJobRepository(db_session)
    job = repo.create_job(["A", "B", "C"], chunk_size=2, env_snapshot={"k": 1})
    assert job.status == "pending"
    assert json.loads(job.symbols_json) == ["A", "B", "C"]

    repo.mark_running(job.id)
    repo.update_job(job.id, cursor=2)
    updated = repo.get_job(job.id)
    assert updated.cursor == 2
    assert updated.status == "running"

    repo.upsert_symbol_status(job.id, "A", "ok", backtest_mode="integrated")
    statuses = repo.get_symbol_statuses(job.id)
    assert len(statuses) == 1
    assert statuses[0].backtest_mode == "integrated"

    repo.mark_completed(job.id)
    done = repo.get_job(job.id)
    assert done.status == "completed"
    assert done.finished_at is not None
