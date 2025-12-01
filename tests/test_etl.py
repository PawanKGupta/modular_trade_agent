import csv
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scripts.etl_import_files import import_pending_orders, import_signals, import_trades_history
from src.infrastructure.db.base import Base
from src.infrastructure.db.models import Activity, Orders, Signals


def make_temp_file(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_etl_imports(tmp_path):
    # Prepare temp files
    pending = make_temp_file(
        tmp_path,
        "pending_orders.json",
        json.dumps(
            [
                {
                    "user_id": 1,
                    "symbol": "TCS",
                    "side": "buy",
                    "order_type": "limit",
                    "quantity": 10,
                    "price": 3500,
                }
            ]
        ),
    )
    trades_csv = tmp_path / "trades_history.csv"
    with trades_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp",
                "ticker",
                "side",
                "quantity",
                "price",
                "order_id",
                "verdict",
                "combined_score",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "timestamp": "2025-01-01T00:00:00",
                "ticker": "TCS",
                "side": "buy",
                "quantity": "10",
                "price": "3500",
                "order_id": "1",
                "verdict": "",
                "combined_score": "",
            }
        )
    signals_json = make_temp_file(
        tmp_path,
        "system_recommended_symbols.json",
        json.dumps([{"symbol": "INFY", "rsi10": 25.0, "ema9": 100.0, "ema200": 120.0}]),
    )

    # Create in-memory DB
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    db: Session = Session()

    try:
        assert import_pending_orders(db, pending) == 1
        assert import_trades_history(db, trades_csv) == 1
        assert import_signals(db, signals_json) == 1

        assert db.query(Orders).count() == 1
        assert db.query(Activity).count() == 1
        assert db.query(Signals).count() == 1
    finally:
        db.close()
