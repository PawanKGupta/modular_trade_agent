import csv
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path so 'src.*' imports work when running this script directly
CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from sqlalchemy.orm import Session

from src.infrastructure.db.models import Activity, Orders, PnlDaily, Signals
from src.infrastructure.db.session import SessionLocal


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def to_float(value) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def import_pending_orders(db: Session, path: Path) -> int:
    if not path.exists():
        return 0
    data = load_json(path)
    count = 0
    for item in data if isinstance(data, list) else []:
        order = Orders(
            user_id=item.get("user_id", 1),
            symbol=item.get("symbol") or item.get("ticker"),
            side=item.get("side", "buy"),
            order_type=item.get("order_type", "limit"),
            quantity=to_float(item.get("quantity") or item.get("qty") or 0),
            price=to_float(item.get("price") or 0),
            status=item.get("status", "amo"),
            placed_at=(
                datetime.fromisoformat(item.get("placed_at"))
                if item.get("placed_at")
                else datetime.utcnow()
            ),
        )
        db.add(order)
        count += 1
    db.commit()
    return count


def import_trades_history(db: Session, path: Path) -> int:
    if not path.exists():
        return 0
    # support both CSV and JSON structures
    count = 0
    if path.suffix.lower() == ".csv":
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                act = Activity(
                    user_id=1,
                    type="trade_history",
                    ref_id=row.get("order_id"),
                    details_json=row,
                    ts=(
                        datetime.fromisoformat(row["timestamp"])
                        if row.get("timestamp")
                        else datetime.utcnow()
                    ),
                )
                db.add(act)
                count += 1
    else:
        data = load_json(path)
        records = data if isinstance(data, list) else []
        for row in records:
            act = Activity(
                user_id=row.get("user_id", 1),
                type="trade_history",
                ref_id=str(row.get("order_id")) if row.get("order_id") is not None else None,
                details_json=row,
                ts=(
                    datetime.fromisoformat(row["timestamp"])
                    if row.get("timestamp")
                    else datetime.utcnow()
                ),
            )
            db.add(act)
            count += 1
    db.commit()
    return count


def import_signals(db: Session, path: Path) -> int:
    if not path.exists():
        return 0
    data = load_json(path)
    items = data if isinstance(data, list) else []
    count = 0
    for s in items:
        try:
            rec = Signals(
                symbol=s.get("symbol") or s.get("ticker") or s.get("Symbol"),
                rsi10=s.get("rsi10") or s.get("RSI10"),
                ema9=s.get("ema9") or s.get("EMA9"),
                ema200=s.get("ema200") or s.get("EMA200"),
                distance_to_ema9=s.get("distance_to_ema9") or s.get("DistanceToEMA9"),
                clean_chart=s.get("clean_chart"),
                monthly_support_dist=s.get("monthly_support_dist"),
                confidence=s.get("confidence"),
            )
            db.add(rec)
            count += 1
        except Exception:
            continue
    db.commit()
    return count


def import_pnl_csv(db: Session, path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            uid = 1
            dt = date.fromisoformat(row["date"])
            existing = (
                db.query(PnlDaily).filter(PnlDaily.user_id == uid, PnlDaily.date == dt).first()
            )
            if existing:
                existing.realized_pnl = to_float(row.get("realized_pnl") or 0)
                existing.unrealized_pnl = to_float(row.get("unrealized_pnl") or 0)
                existing.fees = to_float(row.get("fees") or 0)
            else:
                rec = PnlDaily(
                    user_id=uid,
                    date=dt,
                    realized_pnl=to_float(row.get("realized_pnl") or 0),
                    unrealized_pnl=to_float(row.get("unrealized_pnl") or 0),
                    fees=to_float(row.get("fees") or 0),
                )
                db.add(rec)
            count += 1
        db.commit()
        return count


def main():
    db: Session = SessionLocal()
    try:
        root = Path(".")
        pending_orders = root / "data" / "pending_orders.json"
        trades_history_csv = root / "data" / "trades_history.csv"
        trades_history_json = root / "data" / "trades_history.json"
        pnl_daily = root / "data" / "pnl_daily.csv"
        signals_json = root / "data" / "system_recommended_symbols.json"

        total_orders = import_pending_orders(db, pending_orders)
        total_history = 0
        total_history += import_trades_history(db, trades_history_csv)
        total_history += import_trades_history(db, trades_history_json)
        total_pnl = import_pnl_csv(db, pnl_daily)
        total_signals = import_signals(db, signals_json)

        print(
            f"Imported: orders={total_orders}, trade_history={total_history}, pnl_daily={total_pnl}, signals={total_signals}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
