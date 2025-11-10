"""
Trade History Repository

Simple CSV-based repository for recording executed trades.
"""

import csv
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class TradeHistoryRepository:
    """Persist trades to a CSV file and read them back."""

    def __init__(self, filepath: str = "trade_history.csv"):
        self.path = Path(filepath)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record_trade(self, trade: Dict[str, Any]) -> None:
        """Append a single trade to CSV."""
        write_header = not self.path.exists()
        with self.path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "timestamp", "ticker", "side", "quantity", "price", "order_id", "verdict", "combined_score",
                ],
            )
            if write_header:
                writer.writeheader()
            writer.writerow(trade)

    def record_trades(self, trades: List[Dict[str, Any]]) -> None:
        for t in trades:
            self.record_trade(t)

    def read_all(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)
