"""TargetsRepository tests aligned with current model and repository behavior."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Positions, Targets, TradeMode, Users, UserSettings
from src.infrastructure.persistence.targets_repository import TargetsRepository


@pytest.fixture
def repository(db_session: Session) -> TargetsRepository:
    return TargetsRepository(db_session)


@pytest.fixture
def test_user(db_session: Session) -> Users:
    user = Users(
        email="test@example.com",
        name="Test User",
        password_hash="hash",
        role="user",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    settings = UserSettings(
        user_id=user.id,
        trade_mode=TradeMode.PAPER,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(settings)
    db_session.commit()
    return user


class TestTargetsRepository:
    def _make_target(self, user_id: int, symbol: str, **overrides) -> Targets:
        base = dict(
            user_id=user_id,
            symbol=symbol,
            quantity=10.0,
            target_price=100.0,
            entry_price=90.0,
            trade_mode=TradeMode.PAPER,
        )
        base.update(overrides)
        return Targets(**base)

    def test_create_and_get_by_symbol(self, repository: TargetsRepository, test_user: Users):
        created = repository.create(self._make_target(test_user.id, "RELIANCE", quantity=5.0))

        fetched = repository.get_by_symbol(test_user.id, "RELIANCE")
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.quantity == 5.0
        assert fetched.entry_price == 90.0

    def test_get_by_symbol_inactive_filtering(
        self, repository: TargetsRepository, test_user: Users
    ):
        created = repository.create(self._make_target(test_user.id, "INFY"))
        repository.mark_achieved(created.id)

        active_only = repository.get_by_symbol(test_user.id, "INFY")
        inactive_too = repository.get_by_symbol(test_user.id, "INFY", active_only=False)

        assert active_only is None
        assert inactive_too is not None
        assert inactive_too.is_active is False

    def test_get_active_by_user(self, repository: TargetsRepository, test_user: Users):
        repository.create(self._make_target(test_user.id, "SYM1"))
        repository.create(self._make_target(test_user.id, "SYM2"))
        inactive = repository.create(self._make_target(test_user.id, "SYM3"))
        repository.deactivate(inactive.id)

        active = repository.get_active_by_user(test_user.id)
        assert {t.symbol for t in active} == {"SYM1", "SYM2"}
        assert all(t.is_active for t in active)

    def test_update_target_price(self, repository: TargetsRepository, test_user: Users):
        target = repository.create(self._make_target(test_user.id, "UPD", target_price=50.0))

        updated = repository.update_target_price(target.id, 55.5)
        assert updated is not None
        assert updated.target_price == 55.5

    def test_mark_achieved_sets_flags(self, repository: TargetsRepository, test_user: Users):
        target = repository.create(self._make_target(test_user.id, "ACHIEVE"))

        marked = repository.mark_achieved(target.id)
        assert marked is not None
        assert marked.is_active is False
        assert marked.achieved_at is not None

    def test_deactivate_sets_inactive(self, repository: TargetsRepository, test_user: Users):
        target = repository.create(self._make_target(test_user.id, "DEACT"))

        deactivated = repository.deactivate(target.id)
        assert deactivated is not None
        assert deactivated.is_active is False
        assert repository.db.get(Targets, target.id).is_active is False

    def test_upsert_by_symbol_creates_and_updates(
        self, repository: TargetsRepository, test_user: Users
    ):
        created = repository.upsert_by_symbol(
            user_id=test_user.id,
            symbol="TCS",
            target_data={"target_price": 500.0, "entry_price": 450.0, "quantity": 2.0},
            trade_mode=TradeMode.PAPER,
        )
        assert created.target_price == 500.0
        assert created.entry_price == 450.0
        assert created.quantity == 2.0

        updated = repository.upsert_by_symbol(
            user_id=test_user.id,
            symbol="TCS",
            target_data={"target_price": 520.0, "quantity": 3.0, "current_price": 480.0},
            trade_mode=TradeMode.PAPER,
        )
        assert updated.id == created.id
        assert updated.target_price == 520.0
        assert updated.quantity == 3.0
        assert updated.current_price == 480.0

    def test_get_by_position(
        self, repository: TargetsRepository, test_user: Users, db_session: Session
    ):
        pos1 = Positions(
            user_id=test_user.id,
            symbol="POS1",
            quantity=5.0,
            avg_price=100.0,
            unrealized_pnl=0.0,
        )
        pos2 = Positions(
            user_id=test_user.id,
            symbol="POS2",
            quantity=5.0,
            avg_price=100.0,
            unrealized_pnl=0.0,
        )
        db_session.add_all([pos1, pos2])
        db_session.commit()

        first = repository.create(self._make_target(test_user.id, "POS1", position_id=pos1.id))
        repository.create(self._make_target(test_user.id, "POS2", position_id=pos2.id))
        repository.deactivate(first.id)

        still_active = repository.get_by_position(pos2.id)
        inactive = repository.get_by_position(pos1.id)

        assert still_active is not None and still_active.position_id == pos2.id
        assert inactive is None
