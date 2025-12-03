from types import SimpleNamespace

from server.app.routers import activity


class DummyRepo:
    def __init__(self, db):
        self.db = db
        self.args = None
        self.items = []

    def recent(self, user_id, limit, level):
        self.args = (user_id, limit, level)
        return self.items


def test_list_activity_filters_level(monkeypatch):
    repo = DummyRepo(db_marker := object())
    repo.items = [
        SimpleNamespace(id=1, ts="2025-01-01", type="warn", details_json={"detail": "need review"})
    ]
    monkeypatch.setattr(activity, "ActivityRepository", lambda db: repo)

    user = SimpleNamespace(id=42)
    result = activity.list_activity(level="warn", db=db_marker, current=user)

    assert repo.args == (42, 200, "warn")
    assert len(result) == 1
    assert result[0].detail == "need review"
    assert result[0].level == "warn"


def test_list_activity_defaults_and_detail(monkeypatch):
    repo = DummyRepo(object())
    repo.items = [
        SimpleNamespace(id=1, ts="2025-02-02", type="info", details_json=None),
        SimpleNamespace(id=2, ts="2025-02-03", type="other", details_json={"foo": "bar"}),
    ]
    monkeypatch.setattr(activity, "ActivityRepository", lambda db: repo)

    user = SimpleNamespace(id=5)
    result = activity.list_activity(level="all", db=None, current=user)

    assert repo.args == (5, 200, None)
    assert result[0].detail is None
    assert result[1].level == "info"  # fallback when type not in allowed set

