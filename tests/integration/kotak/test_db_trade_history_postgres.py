"""Postgres-backed integration test for the failed-order ON CONFLICT create path.

The new-failed-order branch of ``AutoTradeEngine._add_failed_order`` uses
``OrdersRepository.create_amo()``, which relies on Postgres-only
``INSERT ... ON CONFLICT`` against a partial unique index. In-memory SQLite (the
default unit-test DB) cannot execute that, so this case is characterized here
against real Postgres.

Runs in the ``integration-concurrency-postgres`` CI job
(``DB_URL=postgresql://...``); skipped on the SQLite unit pass.
"""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.pool import StaticPool

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
from src.infrastructure.db.models import Users
from src.infrastructure.db.session import SessionLocal
from src.infrastructure.db.session import engine as _engine

pytestmark = pytest.mark.skipif(
    _engine.dialect.name == "sqlite" and isinstance(_engine.pool, StaticPool),
    reason="Requires real Postgres (ON CONFLICT partial-index upsert); set DB_URL=postgresql://...",
)


@pytest.fixture
def user_id():
    # Schema is (re)created per test by the autouse clean_db_after_test fixture.
    # Use a short-lived session and don't leak an open transaction, or the autouse
    # teardown's drop_all would block on a held lock.
    db = SessionLocal()
    try:
        user = Users(email=f"dbhist_{uuid4().hex}@example.com", name="t", password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


@pytest.fixture
def engine(user_id):
    session = SessionLocal()
    with patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"):
        auth = Mock()
        auth.is_authenticated.return_value = True
        eng = AutoTradeEngine(auth=auth, user_id=user_id, db_session=session)
    try:
        yield eng
    finally:
        session.close()


@pytest.mark.integration
def test_db_add_failed_order_creates_new_via_on_conflict(engine):
    engine._add_failed_order(
        {"symbol": "NEWFAIL", "qty": 3, "close": 12.5, "reason": "insufficient_balance"}
    )

    failed = engine._get_failed_orders()
    assert any(f["symbol"] == "NEWFAIL" and f["qty"] == 3 for f in failed)
