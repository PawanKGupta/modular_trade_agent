from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from src.infrastructure.db.models import Orders as OrdersModel
from src.infrastructure.db.models import Signals as SignalsModel
from src.infrastructure.persistence.activity_repository import ActivityRepository
from src.infrastructure.persistence.orders_repository import OrdersRepository
from src.infrastructure.persistence.signals_repository import SignalsRepository

# Optional legacy writers (CSV/JSON). These are optional to keep compatibility during cutover.
try:
    from src.infrastructure.persistence.csv_repository import CSVRepository  # type: ignore
except Exception:
    CSVRepository = None  # type: ignore

try:
    from src.infrastructure.persistence.trade_history_repository import (
        TradeHistoryRepository,  # type: ignore
    )
except Exception:
    TradeHistoryRepository = None  # type: ignore


class DualOrdersWriter:
    def __init__(self, db: Session, *, csv_repo: Any | None = None):
        self.db_repo = OrdersRepository(db)
        self.csv_repo = csv_repo

    def create_amo(
        self,
        *,
        user_id: int,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None,
    ) -> OrdersModel:
        # Write to DB
        order = self.db_repo.create_amo(
            user_id=user_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
        )
        # Best-effort legacy write
        if self.csv_repo and hasattr(self.csv_repo, "append_to_master"):
            try:
                self.csv_repo.append_to_master(
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "ticker": symbol,
                        "side": side,
                        "quantity": quantity,
                        "price": price or "",
                        "order_id": order.id,
                        "verdict": "",
                        "combined_score": "",
                    }
                )
            except Exception:
                pass
        return order

    def cancel(self, order: OrdersModel) -> None:
        self.db_repo.cancel(order)
        # No-op for legacy by default


class DualActivityWriter:
    def __init__(self, db: Session, *, trade_history_repo: Any | None = None):
        self.db_repo = ActivityRepository(db)
        self.trade_history_repo = trade_history_repo

    def append(
        self, *, user_id: int | None, type: str, ref_id: str | None, details: dict[str, Any] | None
    ) -> None:
        self.db_repo.append(user_id=user_id, type=type, ref_id=ref_id, details=details)
        if self.trade_history_repo and type == "trade_history":
            try:
                self.trade_history_repo.record_trade(
                    {
                        "timestamp": (
                            details.get("timestamp") if details else datetime.utcnow().isoformat()
                        ),
                        "ticker": details.get("ticker") if details else "",
                        "side": details.get("side") if details else "",
                        "quantity": details.get("quantity") if details else "",
                        "price": details.get("price") if details else "",
                        "order_id": ref_id or "",
                        "verdict": details.get("verdict") if details else "",
                        "combined_score": details.get("combined_score") if details else "",
                    }
                )
            except Exception:
                pass


class DualSignalsWriter:
    def __init__(self, db: Session, *, csv_repo: Any | None = None):
        self.db_repo = SignalsRepository(db)
        self.csv_repo = csv_repo

    def add_many(self, rows: list[dict[str, Any]]) -> int:
        # DB
        models = []
        for s in rows:
            models.append(
                SignalsModel(
                    symbol=s.get("symbol") or s.get("ticker"),
                    rsi10=s.get("rsi10"),
                    ema9=s.get("ema9"),
                    ema200=s.get("ema200"),
                    distance_to_ema9=s.get("distance_to_ema9"),
                    clean_chart=s.get("clean_chart"),
                    monthly_support_dist=s.get("monthly_support_dist"),
                    confidence=s.get("confidence"),
                )
            )
        db_count = self.db_repo.add_many(models) if models else 0

        # Legacy best-effort
        if self.csv_repo and hasattr(self.csv_repo, "save_bulk_analysis"):
            try:
                self.csv_repo.save_bulk_analysis(rows)
            except Exception:
                pass
        return db_count
