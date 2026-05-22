"""Repository for chunked bulk analysis jobs."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import BulkAnalysisJob, BulkAnalysisSymbolStatus
from src.infrastructure.db.timezone_utils import ist_now_naive


class BulkAnalysisJobRepository:
    """CRUD for bulk_analysis_jobs and per-symbol status rows."""

    def __init__(self, db: Session):
        self.db = db

    def create_job(
        self,
        symbols: list[str],
        *,
        chunk_size: int = 25,
        env_snapshot: dict | None = None,
        output_csv: str | None = None,
    ) -> BulkAnalysisJob:
        """Create a new bulk job in ``pending`` status."""
        job = BulkAnalysisJob(
            status="pending",
            chunk_size=chunk_size,
            symbols_json=json.dumps(symbols),
            cursor=0,
            output_csv=output_csv,
            env_snapshot_json=json.dumps(env_snapshot or {}),
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_job(self, job_id: int) -> BulkAnalysisJob | None:
        """Load job by id."""
        return self.db.get(BulkAnalysisJob, job_id)

    def update_job(
        self,
        job_id: int,
        *,
        status: str | None = None,
        cursor: int | None = None,
        output_csv: str | None = None,
        finished_at: datetime | None = None,
    ) -> BulkAnalysisJob | None:
        """Patch job fields."""
        job = self.get_job(job_id)
        if job is None:
            return None
        if status is not None:
            job.status = status
        if cursor is not None:
            job.cursor = cursor
        if output_csv is not None:
            job.output_csv = output_csv
        if finished_at is not None:
            job.finished_at = finished_at
        self.db.commit()
        self.db.refresh(job)
        return job

    def list_symbols(self, job: BulkAnalysisJob) -> list[str]:
        """Decode symbols_json from a job."""
        return json.loads(job.symbols_json)

    def upsert_symbol_status(
        self,
        job_id: int,
        symbol: str,
        status: str,
        *,
        error: str | None = None,
        duration_ms: int | None = None,
        backtest_mode: str | None = None,
        cache_health: str | None = None,
    ) -> BulkAnalysisSymbolStatus:
        """Insert or update per-symbol status for a job."""
        existing = self.db.execute(
            select(BulkAnalysisSymbolStatus).where(
                BulkAnalysisSymbolStatus.job_id == job_id,
                BulkAnalysisSymbolStatus.symbol == symbol,
            )
        ).scalar_one_or_none()

        if existing:
            existing.status = status
            existing.error = error
            existing.duration_ms = duration_ms
            existing.backtest_mode = backtest_mode
            existing.cache_health = cache_health
            row = existing
        else:
            row = BulkAnalysisSymbolStatus(
                job_id=job_id,
                symbol=symbol,
                status=status,
                error=error,
                duration_ms=duration_ms,
                backtest_mode=backtest_mode,
                cache_health=cache_health,
            )
            self.db.add(row)

        self.db.commit()
        self.db.refresh(row)
        return row

    def get_symbol_statuses(self, job_id: int) -> list[BulkAnalysisSymbolStatus]:
        """All symbol rows for a job."""
        return list(
            self.db.execute(
                select(BulkAnalysisSymbolStatus).where(BulkAnalysisSymbolStatus.job_id == job_id)
            ).scalars()
        )

    def mark_running(self, job_id: int) -> BulkAnalysisJob | None:
        """Set job status to running."""
        return self.update_job(job_id, status="running")

    def mark_completed(self, job_id: int) -> BulkAnalysisJob | None:
        """Set job status to completed with finish timestamp."""
        return self.update_job(job_id, status="completed", finished_at=ist_now_naive())
