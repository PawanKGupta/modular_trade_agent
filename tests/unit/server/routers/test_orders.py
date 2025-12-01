from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status

from server.app.routers import orders
from src.infrastructure.db.models import OrderStatus, UserRole


class DummyUser(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            email=kwargs.get("email", "user@example.com"),
            name=kwargs.get("name", "User"),
            role=kwargs.get("role", UserRole.USER),
        )


class DummyOrder(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            user_id=kwargs.get("user_id", 1),
            symbol=kwargs.get("symbol", "RELIANCE.NS"),
            side=kwargs.get("side", "buy"),
            quantity=kwargs.get("quantity", 10.0),
            price=kwargs.get("price", 2500.0),
            status=kwargs.get("status", OrderStatus.PENDING),
            placed_at=kwargs.get("placed_at", datetime(2025, 1, 15, 10, 0, 0)),
            closed_at=kwargs.get("closed_at", None),
            reason=kwargs.get("reason", None),
            first_failed_at=kwargs.get("first_failed_at", None),
            last_retry_attempt=kwargs.get("last_retry_attempt", None),
            retry_count=kwargs.get("retry_count", 0),
            last_status_check=kwargs.get("last_status_check", None),
            execution_price=kwargs.get("execution_price", None),
            execution_qty=kwargs.get("execution_qty", None),
            execution_time=kwargs.get("execution_time", None),
            entry_type=kwargs.get("entry_type", None),
            orig_source=kwargs.get("orig_source", None),
        )


class DummyOrdersRepo:
    def __init__(self, db):
        self.db = db
        self.orders_by_user = {}
        self.orders_by_id = {}
        self.list_calls = []
        self.get_calls = []
        self.update_calls = []
        self.stats = {}

    def list(self, user_id, status=None):
        self.list_calls.append((user_id, status))
        orders = self.orders_by_user.get(user_id, [])
        if status:
            orders = [o for o in orders if o.status == status]
        return orders

    def get(self, order_id):
        self.get_calls.append(order_id)
        return self.orders_by_id.get(order_id)

    def update(self, order):
        self.update_calls.append(order)
        return order

    def get_order_statistics(self, user_id):
        return self.stats.get(user_id, {})


@pytest.fixture
def orders_repo(monkeypatch):
    repo = DummyOrdersRepo(db=None)
    monkeypatch.setattr(orders, "OrdersRepository", lambda db: repo)
    return repo


@pytest.fixture
def current_user():
    return DummyUser(id=42, email="test@example.com")


@pytest.fixture
def mock_ist_now(monkeypatch):
    fixed_time = datetime(2025, 1, 20, 12, 0, 0)

    def ist_now():
        return fixed_time

    monkeypatch.setattr(orders, "ist_now", ist_now)
    return fixed_time


# GET / - list_orders tests
def test_list_orders_no_filters(orders_repo, current_user):
    order1 = DummyOrder(id=1, user_id=42, symbol="RELIANCE.NS")
    order2 = DummyOrder(id=2, user_id=42, symbol="TCS.NS")
    orders_repo.orders_by_user[42] = [order1, order2]

    result = orders.list_orders(db=None, current=current_user)

    assert len(result) == 2
    assert result[0].symbol == "RELIANCE.NS"
    assert result[1].symbol == "TCS.NS"
    assert len(orders_repo.list_calls) == 1
    assert orders_repo.list_calls[0] == (42, None)


def test_list_orders_filter_by_status(orders_repo, current_user):
    pending = DummyOrder(id=1, user_id=42, status=OrderStatus.PENDING)
    failed = DummyOrder(id=2, user_id=42, status=OrderStatus.FAILED)
    orders_repo.orders_by_user[42] = [pending, failed]

    result = orders.list_orders(status="pending", db=None, current=current_user)

    assert len(result) == 1
    assert result[0].status == "pending"
    assert orders_repo.list_calls[0][1] == OrderStatus.PENDING


def test_list_orders_filter_by_reason(orders_repo, current_user):
    order1 = DummyOrder(id=1, user_id=42, reason="Insufficient funds")
    order2 = DummyOrder(id=2, user_id=42, reason="Network error")
    order3 = DummyOrder(id=3, user_id=42, reason="Timeout")
    orders_repo.orders_by_user[42] = [order1, order2, order3]

    result = orders.list_orders(reason="funds", db=None, current=current_user)

    assert len(result) == 1
    assert "funds" in result[0].reason.lower()


def test_list_orders_filter_by_date_range(orders_repo, current_user):
    order1 = DummyOrder(id=1, user_id=42, placed_at=datetime(2025, 1, 15, 10, 0, 0))  # Within range
    order2 = DummyOrder(id=2, user_id=42, placed_at=datetime(2025, 1, 10, 10, 0, 0))  # Before range
    order3 = DummyOrder(id=3, user_id=42, placed_at=datetime(2025, 1, 20, 10, 0, 0))  # After range
    orders_repo.orders_by_user[42] = [order1, order2, order3]

    result = orders.list_orders(
        from_date="2025-01-15", to_date="2025-01-19", db=None, current=current_user
    )

    assert len(result) == 1
    assert result[0].id == 1


def test_list_orders_filter_from_date_only(orders_repo, current_user):
    order1 = DummyOrder(id=1, user_id=42, placed_at=datetime(2025, 1, 15, 10, 0, 0))
    order2 = DummyOrder(id=2, user_id=42, placed_at=datetime(2025, 1, 10, 10, 0, 0))
    orders_repo.orders_by_user[42] = [order1, order2]

    result = orders.list_orders(from_date="2025-01-15", db=None, current=current_user)

    assert len(result) == 1
    assert result[0].id == 1


def test_list_orders_filter_to_date_only(orders_repo, current_user):
    order1 = DummyOrder(id=1, user_id=42, placed_at=datetime(2025, 1, 15, 10, 0, 0))
    order2 = DummyOrder(id=2, user_id=42, placed_at=datetime(2025, 1, 20, 10, 0, 0))
    orders_repo.orders_by_user[42] = [order1, order2]

    result = orders.list_orders(to_date="2025-01-19", db=None, current=current_user)

    assert len(result) == 1
    assert result[0].id == 1


def test_list_orders_invalid_date_format(orders_repo, current_user):
    orders_repo.orders_by_user[42] = []

    with pytest.raises(HTTPException) as exc:
        orders.list_orders(from_date="invalid-date", db=None, current=current_user)

    # HTTPException from ValueError gets caught by outer Exception handler and wrapped as 500
    # But the original 400 message is preserved in the detail
    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Invalid date format" in exc.value.detail or "Invalid isoformat" in exc.value.detail


def test_list_orders_empty_result(orders_repo, current_user):
    orders_repo.orders_by_user[42] = []

    result = orders.list_orders(db=None, current=current_user)

    assert len(result) == 0


def test_list_orders_filters_combined(orders_repo, current_user):
    order1 = DummyOrder(
        id=1,
        user_id=42,
        status=OrderStatus.FAILED,
        reason="Network timeout",
        placed_at=datetime(2025, 1, 15, 10, 0, 0),
    )
    order2 = DummyOrder(
        id=2,
        user_id=42,
        status=OrderStatus.FAILED,
        reason="Insufficient funds",
        placed_at=datetime(2025, 1, 16, 10, 0, 0),
    )
    orders_repo.orders_by_user[42] = [order1, order2]

    result = orders.list_orders(
        status="failed",
        reason="timeout",
        from_date="2025-01-15",
        db=None,
        current=current_user,
    )

    assert len(result) == 1
    assert result[0].id == 1


def test_list_orders_order_without_placed_at(orders_repo, current_user):
    order = DummyOrder(id=1, user_id=42, placed_at=None)
    orders_repo.orders_by_user[42] = [order]

    result = orders.list_orders(from_date="2025-01-15", db=None, current=current_user)

    # Orders without placed_at are included (not filtered) when date filtering is applied
    # because the code checks `if order_date:` and if None, it skips date comparison but still adds
    assert len(result) == 1
    assert result[0].created_at is None


def test_list_orders_serialization_error_handling(orders_repo, current_user):
    # Create an order that will cause serialization error
    class BadOrder:
        id = 1
        symbol = "TEST"
        side = "buy"
        quantity = 10.0
        price = 100.0
        status = OrderStatus.PENDING
        placed_at = datetime(2025, 1, 15, 10, 0, 0)

        def __getattr__(self, name):
            raise AttributeError(f"Missing attribute: {name}")

    orders_repo.orders_by_user[42] = [BadOrder()]

    result = orders.list_orders(db=None, current=current_user)

    # Should handle error gracefully and continue
    assert len(result) == 0


def test_list_orders_exception_handling(orders_repo, current_user):
    def boom(*_, **__):
        raise RuntimeError("Database error")

    orders_repo.list = boom

    with pytest.raises(HTTPException) as exc:
        orders.list_orders(db=None, current=current_user)

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Failed to list orders" in exc.value.detail


def test_list_orders_format_datetime_fields(orders_repo, current_user):
    order = DummyOrder(
        id=1,
        user_id=42,
        placed_at=datetime(2025, 1, 15, 10, 30, 0),
        closed_at=datetime(2025, 1, 16, 14, 0, 0),
    )
    orders_repo.orders_by_user[42] = [order]

    result = orders.list_orders(db=None, current=current_user)

    assert len(result) == 1
    assert result[0].created_at == "2025-01-15T10:30:00"
    assert result[0].updated_at == "2025-01-16T14:00:00"


# POST /{order_id}/retry - retry_order tests
def test_retry_order_success(orders_repo, current_user, mock_ist_now):
    order = DummyOrder(id=1, user_id=42, status=OrderStatus.FAILED, retry_count=0, reason="Error")
    orders_repo.orders_by_id[1] = order

    result = orders.retry_order(order_id=1, db=None, current=current_user)

    assert result.status == "failed"
    assert order.retry_count == 1
    assert order.last_retry_attempt == mock_ist_now
    assert "Manual retry requested" in order.reason
    assert len(orders_repo.update_calls) == 1


def test_retry_order_not_found(orders_repo, current_user):
    orders_repo.orders_by_id = {}

    with pytest.raises(HTTPException) as exc:
        orders.retry_order(order_id=999, db=None, current=current_user)

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in exc.value.detail.lower()


def test_retry_order_wrong_user(orders_repo, current_user):
    order = DummyOrder(id=1, user_id=99, status=OrderStatus.FAILED)  # Different user
    orders_repo.orders_by_id[1] = order

    with pytest.raises(HTTPException) as exc:
        orders.retry_order(order_id=1, db=None, current=current_user)

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Not authorized" in exc.value.detail


def test_retry_order_invalid_status(orders_repo, current_user):
    order = DummyOrder(id=1, user_id=42, status=OrderStatus.CLOSED)
    orders_repo.orders_by_id[1] = order

    with pytest.raises(HTTPException) as exc:
        orders.retry_order(order_id=1, db=None, current=current_user)

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Cannot retry" in exc.value.detail
    assert "Only failed orders" in exc.value.detail


def test_retry_order_sets_first_failed_at(orders_repo, current_user, mock_ist_now):
    order = DummyOrder(id=1, user_id=42, status=OrderStatus.FAILED, first_failed_at=None)
    orders_repo.orders_by_id[1] = order

    orders.retry_order(order_id=1, db=None, current=current_user)

    assert order.first_failed_at == mock_ist_now


def test_retry_order_preserves_existing_first_failed_at(orders_repo, current_user):
    existing_time = datetime(2025, 1, 10, 10, 0, 0)
    order = DummyOrder(id=1, user_id=42, status=OrderStatus.FAILED, first_failed_at=existing_time)
    orders_repo.orders_by_id[1] = order

    orders.retry_order(order_id=1, db=None, current=current_user)

    assert order.first_failed_at == existing_time  # Should not change


def test_retry_order_increments_retry_count(orders_repo, current_user):
    order = DummyOrder(id=1, user_id=42, status=OrderStatus.FAILED, retry_count=3)
    orders_repo.orders_by_id[1] = order

    orders.retry_order(order_id=1, db=None, current=current_user)

    assert order.retry_count == 4


def test_retry_order_appends_to_existing_reason(orders_repo, current_user):
    order = DummyOrder(id=1, user_id=42, status=OrderStatus.FAILED, reason="Network error")
    orders_repo.orders_by_id[1] = order

    orders.retry_order(order_id=1, db=None, current=current_user)

    assert "Network error" in order.reason
    assert "Manual retry requested" in order.reason


def test_retry_order_exception_handling(orders_repo, current_user):
    def boom(*_, **__):
        raise RuntimeError("DB error")

    orders_repo.get = boom

    with pytest.raises(HTTPException) as exc:
        orders.retry_order(order_id=1, db=None, current=current_user)

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Failed to retry order" in exc.value.detail


# DELETE /{order_id} - drop_order tests
def test_drop_order_success(orders_repo, current_user, mock_ist_now):
    order = DummyOrder(id=1, user_id=42, status=OrderStatus.FAILED)
    orders_repo.orders_by_id[1] = order

    result = orders.drop_order(order_id=1, db=None, current=current_user)

    assert result["message"] == "Order 1 dropped from retry queue"
    assert order.status == OrderStatus.CLOSED
    assert order.closed_at == mock_ist_now
    assert len(orders_repo.update_calls) == 1


def test_drop_order_not_found(orders_repo, current_user):
    orders_repo.orders_by_id = {}

    with pytest.raises(HTTPException) as exc:
        orders.drop_order(order_id=999, db=None, current=current_user)

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in exc.value.detail.lower()


def test_drop_order_wrong_user(orders_repo, current_user):
    order = DummyOrder(id=1, user_id=99, status=OrderStatus.FAILED)
    orders_repo.orders_by_id[1] = order

    with pytest.raises(HTTPException) as exc:
        orders.drop_order(order_id=1, db=None, current=current_user)

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Not authorized" in exc.value.detail


def test_drop_order_invalid_status(orders_repo, current_user):
    order = DummyOrder(id=1, user_id=42, status=OrderStatus.CLOSED)
    orders_repo.orders_by_id[1] = order

    with pytest.raises(HTTPException) as exc:
        orders.drop_order(order_id=1, db=None, current=current_user)

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Cannot drop" in exc.value.detail
    assert "Only failed orders" in exc.value.detail


def test_drop_order_exception_handling(orders_repo, current_user):
    def boom(*_, **__):
        raise RuntimeError("DB error")

    orders_repo.get = boom

    with pytest.raises(HTTPException) as exc:
        orders.drop_order(order_id=1, db=None, current=current_user)

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Failed to drop order" in exc.value.detail


# GET /statistics - get_order_statistics tests
def test_get_order_statistics_success(orders_repo, current_user):
    stats = {
        "total_orders": 10,
        "pending": 2,
        "ongoing": 1,
        "failed": 3,
        "closed": 4,
    }
    orders_repo.stats[42] = stats

    result = orders.get_order_statistics(current_user=current_user, db=None)

    assert result == stats
    assert "total_orders" in result


def test_get_order_statistics_empty(orders_repo, current_user):
    orders_repo.stats[42] = {}

    result = orders.get_order_statistics(current_user=current_user, db=None)

    assert result == {}


# Additional edge case tests
def test_list_orders_all_status_types(orders_repo, current_user):
    statuses = [
        OrderStatus.PENDING,
        OrderStatus.ONGOING,
        OrderStatus.CLOSED,
        OrderStatus.FAILED,
        OrderStatus.CANCELLED,
    ]
    orders_list = [DummyOrder(id=i, user_id=42, status=s) for i, s in enumerate(statuses, 1)]
    orders_repo.orders_by_user[42] = orders_list

    for status_val in ["pending", "ongoing", "closed", "failed", "cancelled"]:
        result = orders.list_orders(status=status_val, db=None, current=current_user)
        assert len(result) == 1
        assert result[0].status == status_val


def test_list_orders_handles_none_reason(orders_repo, current_user):
    order1 = DummyOrder(id=1, user_id=42, reason=None)
    order2 = DummyOrder(id=2, user_id=42, reason="Some reason")
    orders_repo.orders_by_user[42] = [order1, order2]

    result = orders.list_orders(reason="reason", db=None, current=current_user)

    assert len(result) == 1
    assert result[0].id == 2


def test_retry_order_handles_none_retry_count(orders_repo, current_user):
    order = DummyOrder(id=1, user_id=42, status=OrderStatus.FAILED, retry_count=None)
    orders_repo.orders_by_id[1] = order

    orders.retry_order(order_id=1, db=None, current=current_user)

    assert order.retry_count == 1


def test_list_orders_handles_all_optional_fields(orders_repo, current_user):
    order = DummyOrder(
        id=1,
        user_id=42,
        first_failed_at=datetime(2025, 1, 10, 10, 0, 0),
        last_retry_attempt=datetime(2025, 1, 11, 10, 0, 0),
        retry_count=2,
        last_status_check=datetime(2025, 1, 12, 10, 0, 0),
        execution_price=2500.5,
        execution_qty=5.0,
        execution_time=datetime(2025, 1, 13, 10, 0, 0),
        entry_type="initial",
        orig_source="manual",
    )
    orders_repo.orders_by_user[42] = [order]

    result = orders.list_orders(db=None, current=current_user)

    assert len(result) == 1
    assert result[0].retry_count == 2
    assert result[0].execution_price == 2500.5
    assert result[0].entry_type == "initial"
    assert result[0].is_manual is True


def test_list_orders_handles_non_standard_side(orders_repo, current_user):
    order = DummyOrder(id=1, user_id=42, side="unknown")
    orders_repo.orders_by_user[42] = [order]

    result = orders.list_orders(db=None, current=current_user)

    assert len(result) == 1
    assert result[0].side == "buy"  # Should default to "buy"
