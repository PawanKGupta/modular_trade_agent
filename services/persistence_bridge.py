from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.infrastructure.db.session import SessionLocal
from src.infrastructure.persistence.csv_repository import CSVRepository  # legacy optional
from src.infrastructure.persistence.dual_write import DualSignalsWriter


def persist_signals(rows: list[dict[str, Any]], *, db: Session | None = None) -> int:
    owned = False
    if db is None:
        db = SessionLocal()
        owned = True
    try:
        writer = DualSignalsWriter(db, csv_repo=CSVRepository())
        return writer.add_many(rows)
    finally:
        if owned:
            db.close()
