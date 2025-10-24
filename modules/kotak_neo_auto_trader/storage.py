#!/usr/bin/env python3
"""
Storage utilities for trades history JSON
"""

import json
import os
from datetime import datetime
from typing import Dict, Any

from utils.logger import logger

DEFAULT_HISTORY_TEMPLATE = {
    "trades": [],  # list of trade entries
    "last_run": None,
}


def ensure_dir(path: str):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def load_history(path: str) -> Dict[str, Any]:
    try:
        if not os.path.exists(path):
            ensure_dir(path)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_HISTORY_TEMPLATE, f, indent=2)
            return DEFAULT_HISTORY_TEMPLATE.copy()
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load trades history at {path}: {e}")
        return DEFAULT_HISTORY_TEMPLATE.copy()


essential_trade_fields = [
    "symbol", "entry_price", "entry_time", "rsi10", "ema9", "ema200",
    "capital", "qty", "rsi_entry_level", "order_response", "status"
]


def append_trade(path: str, trade: Dict[str, Any]) -> None:
    try:
        data = load_history(path)
        data.setdefault("trades", [])
        data["trades"].append(trade)
        data["last_run"] = datetime.now().isoformat()
        ensure_dir(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to append trade to history: {e}")


def save_history(path: str, data: Dict[str, Any]) -> None:
    try:
        ensure_dir(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save trades history: {e}")
