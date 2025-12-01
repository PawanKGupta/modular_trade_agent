import os
import sys

import pytest


def setup_db():
    os.environ["DB_URL"] = "sqlite:///:memory:"
    root = __import__("os").path.abspath(__file__ + "/../../..")
    if root not in sys.path:
        sys.path.append(root)
    import src.infrastructure.db.models  # noqa
    from src.infrastructure.db.base import Base
    from src.infrastructure.db.session import SessionLocal, engine

    try:
        Base.metadata.drop_all(bind=engine)
    except Exception:
        pass
    Base.metadata.create_all(bind=engine)
    return SessionLocal


@pytest.mark.unit
def test_user_repo_create_and_password_hashing_truncation():
    SessionLocal = setup_db()
    from sqlalchemy.orm import Session

    from server.app.core.security import verify_password
    from src.infrastructure.db.models import UserRole
    from src.infrastructure.db.session import SessionLocal as Sess
    from src.infrastructure.persistence.user_repository import UserRepository

    db: Session = Sess()
    try:
        repo = UserRepository(db)
        long_pw = "x" * 500
        import random

        user = repo.create_user(
            f"long{random.randint(1, 1_000_000)}@example.com", long_pw, name="L", role=UserRole.USER
        )
        assert user.id is not None
        # verify uses bcrypt with truncation, so should succeed
        assert verify_password(long_pw, user.password_hash)
    finally:
        db.close()
