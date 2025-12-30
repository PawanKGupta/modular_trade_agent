import csv
import io
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from src.infrastructure.db.models import PnlDaily, TradeMode, Users
from src.infrastructure.persistence.orders_repository import OrdersRepository


def _signup_and_headers(
    client: TestClient, email: str = "exporter@example.com"
) -> tuple[dict, int]:
    resp = client.post("/api/v1/auth/signup", json={"email": email, "password": "secret123"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers, token


def test_export_pnl_csv_uses_db_data(client: TestClient, db_session):
    # Arrange: create user and seed P&L rows directly in DB
    headers, _ = _signup_and_headers(client, email="pnl_csv@example.com")
    user = db_session.query(Users).filter(Users.email == "pnl_csv@example.com").one()

    db_session.add_all(
        [
            PnlDaily(
                user_id=user.id,
                date=date.today() - timedelta(days=1),
                realized_pnl=100.0,
                unrealized_pnl=50.0,
                fees=10.0,
            ),
            PnlDaily(
                user_id=user.id,
                date=date.today(),
                realized_pnl=-20.0,
                unrealized_pnl=30.0,
                fees=5.0,
            ),
        ]
    )
    db_session.commit()

    start = (date.today() - timedelta(days=2)).isoformat()
    end = date.today().isoformat()

    # Act: request CSV with include_unrealized=false to assert computed totals
    resp = client.get(
        "/api/v1/user/export/pnl/csv",
        params={
            "start_date": start,
            "end_date": end,
            "trade_mode": TradeMode.PAPER.value,
            "include_unrealized": False,
        },
        headers=headers,
    )

    # Assert
    assert resp.status_code == 200, resp.text
    assert resp.headers.get("content-type", "").startswith("text/csv")

    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    assert len(rows) == 2
    # Totals should exclude unrealized when include_unrealized=false
    first = rows[0]
    assert first["total_pnl"] == "90.00"  # 100 - 10
    second = rows[1]
    assert second["total_pnl"] == "-25.00"  # -20 - 5
    # trade_mode column comes from request param
    assert {r["trade_mode"] for r in rows} == {TradeMode.PAPER.value}


def test_export_orders_csv_filters_by_trade_mode_and_dates(client: TestClient, db_session):
    headers, _ = _signup_and_headers(client, email="orders_csv@example.com")
    user = db_session.query(Users).filter(Users.email == "orders_csv@example.com").one()

    repo = OrdersRepository(db_session)
    older = repo.create_amo(
        user_id=user.id,
        symbol="OLD",
        side="buy",
        order_type="market",
        quantity=1.0,
        price=None,
    )
    older.trade_mode = TradeMode.PAPER
    older.placed_at = datetime.utcnow() - timedelta(days=40)

    recent = repo.create_amo(
        user_id=user.id,
        symbol="RECENT",
        side="buy",
        order_type="market",
        quantity=2.0,
        price=None,
    )
    recent.trade_mode = TradeMode.BROKER
    recent.placed_at = datetime.utcnow() - timedelta(days=1)

    db_session.commit()

    start = (date.today() - timedelta(days=7)).isoformat()
    end = date.today().isoformat()

    resp = client.get(
        "/api/v1/user/export/orders/csv",
        params={
            "start_date": start,
            "end_date": end,
            "trade_mode": TradeMode.BROKER.value,
        },
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    # Only the broker-mode recent order should be included
    assert len(rows) == 1
    assert rows[0]["symbol"] == "RECENT"
    assert rows[0]["trade_mode"] == TradeMode.BROKER.value


def test_export_pnl_pdf_returns_pdf(client: TestClient, db_session):
    headers, _ = _signup_and_headers(client, email="pnl_pdf@example.com")
    user = db_session.query(Users).filter(Users.email == "pnl_pdf@example.com").one()

    db_session.add(
        PnlDaily(
            user_id=user.id,
            date=date.today(),
            realized_pnl=25.0,
            unrealized_pnl=5.0,
            fees=1.0,
        )
    )
    db_session.commit()

    resp = client.get(
        "/api/v1/user/reports/pnl/pdf",
        params={
            "period": "custom",
            "start_date": date.today().isoformat(),
            "end_date": date.today().isoformat(),
            "trade_mode": TradeMode.PAPER.value,
            "include_unrealized": False,
        },
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    assert resp.headers.get("content-type", "").startswith("application/pdf")
    # Basic PDF signature check
    assert resp.content.startswith(b"%PDF")


def test_export_signals_csv_filters_and_empty_case(client: TestClient, db_session):
    headers, _ = _signup_and_headers(client, email="signals_csv@example.com")
    db_session.query(Users).filter(Users.email == "signals_csv@example.com").one()

    from src.infrastructure.db.models import Signals, SignalStatus
    from src.infrastructure.db.timezone_utils import ist_now

    # Seed one recent BUY signal and one older AVOID
    recent = Signals(
        symbol="RECENT",
        status=SignalStatus.ACTIVE,
        verdict="buy",
        buy_range={"low": 100.0, "high": 110.0},
        target=120.0,
        stop=95.0,
        last_close=105.0,
        rsi10=45.0,
        signals=["RSI near oversold"],
        justification=["Strong support"],
        ml_verdict="buy",
        ml_confidence=0.8,
        ts=ist_now(),
    )
    older = Signals(
        symbol="OLDER",
        status=SignalStatus.ACTIVE,
        verdict="avoid",
        ts=ist_now().replace(day=max(1, ist_now().day - 20)),
    )
    db_session.add_all([recent, older])
    db_session.commit()

    start = (date.today() - timedelta(days=7)).isoformat()
    end = date.today().isoformat()

    # Filter by verdict=buy within last 7 days
    resp = client.get(
        "/api/v1/user/export/signals/csv",
        params={"start_date": start, "end_date": end, "verdict": "buy"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    assert len(rows) == 1
    assert rows[0]["symbol"] == "RECENT"
    assert rows[0]["verdict"] == "buy"

    # Empty date range should still return header-only CSV
    resp2 = client.get(
        "/api/v1/user/export/signals/csv",
        params={
            "start_date": (date.today() - timedelta(days=60)).isoformat(),
            "end_date": (date.today() - timedelta(days=50)).isoformat(),
            "verdict": "strong_buy",
        },
        headers=headers,
    )
    assert resp2.status_code == 200, resp2.text
    rows2 = list(csv.DictReader(io.StringIO(resp2.text)))
    assert rows2 == []


def test_export_trades_csv_uses_closed_at_and_fields(client: TestClient, db_session):
    # Arrange
    headers, _ = _signup_and_headers(client, email="trades_csv@example.com")
    user = db_session.query(Users).filter(Users.email == "trades_csv@example.com").one()

    from src.infrastructure.db.models import Positions

    opened = datetime.utcnow() - timedelta(days=10)
    closed = datetime.utcnow() - timedelta(days=1)

    pos = Positions(
        user_id=user.id,
        symbol="TST",
        quantity=1.0,
        avg_price=100.0,
        opened_at=opened,
        closed_at=closed,
        exit_price=120.0,
        realized_pnl=20.0,
    )
    db_session.add(pos)
    db_session.commit()

    start = (date.today() - timedelta(days=7)).isoformat()
    end = date.today().isoformat()

    # Act
    resp = client.get(
        "/api/v1/user/export/trades/csv",
        params={
            "start_date": start,
            "end_date": end,
            "trade_mode": TradeMode.PAPER.value,
        },
        headers=headers,
    )

    # Assert
    assert resp.status_code == 200, resp.text
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    assert len(rows) == 1
    row = rows[0]
    assert row["symbol"] == "TST"
    # Dates present and ISO formatted
    assert row["entry_date"]
    assert row["exit_date"]
    # Prices and PnL formatting
    assert row["entry_price"] == "100.00"
    assert row["exit_price"] == "120.00"
    assert row["realized_pnl"] == "20.00"
    # Fees are 0.00 (not stored on Positions)
    assert row["fees"] == "0.00"
    # Trade mode column is echoed from request param
    assert row["trade_mode"] == TradeMode.PAPER.value


def test_export_signals_csv_handles_buy_range_dict(client: TestClient, db_session):
    headers, _ = _signup_and_headers(client, email="signals_dict@example.com")
    db_session.query(Users).filter(Users.email == "signals_dict@example.com").one()

    from src.infrastructure.db.models import Signals, SignalStatus
    from src.infrastructure.db.timezone_utils import ist_now

    sig = Signals(
        symbol="DICT",
        status=SignalStatus.ACTIVE,
        verdict="buy",
        buy_range={"low": 150.0, "high": 155.0},
        target=170.0,
        stop=145.0,
        last_close=152.0,
        rsi10=48.0,
        signals=["Support bounce"],
        justification=["Volume increase"],
        ml_verdict="buy",
        ml_confidence=0.7,
        ts=ist_now(),
    )
    db_session.add(sig)
    db_session.commit()

    start = (date.today() - timedelta(days=2)).isoformat()
    end = date.today().isoformat()

    resp = client.get(
        "/api/v1/user/export/signals/csv",
        params={"start_date": start, "end_date": end, "verdict": "buy"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    assert len(rows) == 1
    row = rows[0]
    assert row["symbol"] == "DICT"
    assert row["buy_range_low"] == "150.00"
    assert row["buy_range_high"] == "155.00"
