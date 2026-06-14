#!/usr/bin/env python3
"""
Probe Kotak Neo REST quotes for market depth / bid-ask fields.

Credentials (first match wins):
  --config PATH   kotak_neo.env file
  --user-id ID    decrypt broker creds from DB (requires DB_URL + encryption keys in .env)

Example (repo root, root .venv):
  python modules/kotak_neo_auto_trader/dev_tests/probe_market_depth.py --symbol RELIANCE --user-id 2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

load_dotenv(_REPO_ROOT / ".env")

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth  # noqa: E402
from modules.kotak_neo_auto_trader.market_data import KotakNeoMarketData  # noqa: E402
from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster  # noqa: E402
from src.application.services.broker_credentials import (  # noqa: E402
    create_temp_env_file,
    load_broker_credentials,
)
from src.infrastructure.db.session import SessionLocal  # noqa: E402

_FILTERS = ("ltp", "ohlc", "circuit_limits", "market_depth", "all")
_DEPTH_KEYS = (
    "bp",
    "sp",
    "bq",
    "sq",
    "bid",
    "ask",
    "bidPrice",
    "askPrice",
    "bidQty",
    "askQty",
    "depth",
    "market_depth",
    "buy",
    "sell",
    "iep",
    "IEP",
    "preOpen",
    "preopen",
)


def _repo_root() -> Path:
    return _REPO_ROOT


def _resolve_config(args: argparse.Namespace) -> tuple[str, Path | None]:
    """Return (config_path, temp_file_to_cleanup)."""
    if args.config:
        return args.config, None
    if args.user_id is not None:
        db = SessionLocal()
        try:
            creds = load_broker_credentials(args.user_id, db)
        finally:
            db.close()
        if not creds:
            raise SystemExit(f"No broker credentials for user_id={args.user_id}")
        temp = create_temp_env_file(creds)
        return temp, Path(temp)
    default = _repo_root() / "modules/kotak_neo_auto_trader/kotak_neo.env"
    if default.is_file():
        return str(default), None
    raise SystemExit("Provide --config PATH or --user-id ID (no kotak_neo.env on disk)")


def _summarize(obj: Any, depth: int = 0, max_depth: int = 4) -> Any:
    """Shrink large quote payloads for terminal output."""
    if depth >= max_depth:
        if isinstance(obj, (dict, list)):
            return f"<{type(obj).__name__} len={len(obj)}>"
        return obj
    if isinstance(obj, dict):
        return {k: _summarize(v, depth + 1, max_depth) for k, v in obj.items()}
    if isinstance(obj, list):
        if len(obj) > 6:
            head = [_summarize(x, depth + 1, max_depth) for x in obj[:3]]
            return head + [f"... +{len(obj) - 3} more"]
        return [_summarize(x, depth + 1, max_depth) for x in obj]
    return obj


def _find_depth_keys(obj: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            kl = str(k).lower()
            if any(d.lower() in kl for d in _DEPTH_KEYS):
                found.append(path)
            found.extend(_find_depth_keys(v, path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj[:5]):
            found.extend(_find_depth_keys(item, f"{prefix}[{i}]"))
    return found


def _extract_quote_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("data", "quotes", "result"):
            node = data.get(key)
            if isinstance(node, list):
                return [x for x in node if isinstance(x, dict)]
        return [data]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Kotak Neo quote filters for market depth")
    parser.add_argument("--symbol", default="RELIANCE", help="Base symbol (default: RELIANCE)")
    parser.add_argument("--config", help="Path to kotak_neo.env")
    parser.add_argument("--user-id", type=int, help="Load creds from DB for this user")
    parser.add_argument("--filters", nargs="*", default=list(_FILTERS), help="Quote filters to try")
    args = parser.parse_args()

    temp_cleanup: Path | None = None
    try:
        config_path, temp_cleanup = _resolve_config(args)
        auth = KotakNeoAuth(config_path)
        if not auth.login():
            print("Login failed", file=sys.stderr)
            return 1
        print("Login OK\n")

        scrip = KotakNeoScripMaster(auth_client=auth.get_rest_client(), exchanges=["NSE"])
        scrip.load_scrip_master(force_download=False)
        inst = scrip.get_instrument(f"{args.symbol.upper()}-EQ", exchange="NSE")
        if not inst:
            inst = scrip.get_instrument(args.symbol.upper(), exchange="NSE")
        token = (inst or {}).get("token")
        trading_symbol = (inst or {}).get("symbol") or f"{args.symbol.upper()}-EQ"
        print(f"Symbol: {args.symbol} -> {trading_symbol} token={token}\n")

        md = KotakNeoMarketData(auth)
        queries: list[tuple[str, str]] = []
        if token:
            queries.append(("token", f"nse_cm|{token}"))
        queries.append(("name", f"nse_cm|{trading_symbol}"))

        for q_label, query in queries:
            print("=" * 72)
            print(f"Query ({q_label}): {query}")
            for filt in args.filters:
                print("-" * 72)
                print(f"filter: {filt}")
                raw = md.get_quote(query, filter_name=filt)
                if raw is None:
                    print("  -> None / error")
                    continue
                rows = _extract_quote_rows(raw)
                depth_paths = _find_depth_keys(raw)
                print(f"  top-level type: {type(raw).__name__}")
                if rows:
                    print(f"  row keys: {sorted(rows[0].keys())}")
                if depth_paths:
                    print(f"  depth-related paths: {depth_paths}")
                else:
                    print("  depth-related paths: (none)")
                print("  payload:")
                print(json.dumps(_summarize(raw), indent=2, default=str))
            print()

        return 0
    finally:
        if temp_cleanup and temp_cleanup.is_file():
            try:
                temp_cleanup.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
