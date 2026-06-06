#!/usr/bin/env python3
"""
Developer smoke tool: Kotak Neo REST ``check_margin`` and optional live order placement.

Credentials are read only from ``--config`` (default:
``modules/kotak_neo_auto_trader/kotak_neo.env``). Do not hardcode secrets here.

Live ``place-amo`` is gated by **both**:

1. Environment variable ``KOTAK_ALLOW_LIVE_PLACE_ORDER=1``
2. CLI flag ``--confirm-live-order``

Examples (from repository root, root ``.venv`` active)::

    python modules/kotak_neo_auto_trader/dev_tests/kotak_broker_smoke.py \\
        check-margin --symbol RELIANCE-EQ --qty 1 --price 0 --order-type MKT

    export KOTAK_ALLOW_LIVE_PLACE_ORDER=1
    python modules/kotak_neo_auto_trader/dev_tests/kotak_broker_smoke.py \\
        place-amo --symbol RELIANCE-EQ --qty 1 --confirm-live-order

PowerShell::

    $env:KOTAK_ALLOW_LIVE_PLACE_ORDER = '1'
    python modules/kotak_neo_auto_trader/dev_tests/kotak_broker_smoke.py \\
        place-amo --symbol RELIANCE-EQ --qty 1 --confirm-live-order
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_MAX_DEV_PLACE_QTY = 10
_REQ_KEYS = ("reqdMrgn", "requiredMargin", "reqMargin", "ordMrgn")
_CASH_KEYS = ("avlCash", "availableCash", "cash", "netCash")


def _repo_root() -> Path:
    """Walk upward from this file until a directory contains ``src`` and ``modules``."""
    p = Path(__file__).resolve().parent
    for _ in range(12):
        if (p / "src").is_dir() and (p / "modules").is_dir():
            return p
        if p == p.parent:
            break
        p = p.parent
    raise RuntimeError(
        "Could not resolve repository root (expected a parent dir with src/ and modules/)."
    )


def _to_float(raw: object, default: float = 0.0) -> float:
    """Parse a numeric margin field from Kotak JSON (commas, strings)."""
    try:
        if raw is None:
            return default
        return float(str(raw).replace(",", "").strip())
    except Exception:
        return default


def _margin_body(resp: dict[str, Any]) -> dict[str, Any]:
    """Unwrap Kotak check-margin payload when nested under ``data``."""
    data_node = resp.get("data")
    if isinstance(data_node, dict):
        return data_node
    if isinstance(data_node, list) and data_node and isinstance(data_node[0], dict):
        return data_node[0]
    return resp


def _first(*keys: str, source: dict[str, Any]) -> Any:
    for key in keys:
        if key in source and source.get(key) is not None:
            return source.get(key)
    return None


def _run_check_margin(args: argparse.Namespace) -> int:
    """Login, resolve token, call ``check_margin``, print JSON and a short summary."""
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth  # noqa: PLC0415
    from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster  # noqa: PLC0415

    auth = KotakNeoAuth(config_file=args.config)
    if not auth.login():
        print("ERROR: login failed", file=sys.stderr)
        return 1

    rest = auth.get_rest_client()
    scrip_master = KotakNeoScripMaster(auth_client=rest, exchanges=[args.exchange.upper()])
    if not scrip_master.load_scrip_master(force_download=False):
        print("ERROR: failed to load scrip master", file=sys.stderr)
        return 1

    token = scrip_master.get_token(args.symbol, exchange=args.exchange.upper())
    if not token and "-" in args.symbol:
        token = scrip_master.get_token(args.symbol.split("-")[0], exchange=args.exchange.upper())
    if not token:
        print(f"ERROR: token not found for symbol={args.symbol}", file=sys.stderr)
        return 1

    ex_seg = "nse_cm" if args.exchange.upper() == "NSE" else "bse_cm"
    prc_tp = args.order_type
    price = 0.0 if prc_tp == "MKT" else float(args.price)

    jdata = {
        "brkName": "KOTAK",
        "brnchId": "ONLINE",
        "exSeg": ex_seg,
        "prc": str(price),
        "prcTp": prc_tp,
        "prod": args.product.upper(),
        "qty": str(int(args.qty)),
        "tok": str(token),
        "trnsTp": args.transaction_type,
    }

    print("=== check-margin request ===")
    print(json.dumps(jdata, indent=2))

    resp = rest.check_margin(jdata)
    if not isinstance(resp, dict):
        print("\n=== check-margin response (non-dict) ===", file=sys.stderr)
        print(repr(resp), file=sys.stderr)
        return 1

    print("\n=== check-margin response ===")
    print(json.dumps(resp, indent=2))

    body = _margin_body(resp)
    avl_cash = _to_float(_first(*_CASH_KEYS, source=body))
    if avl_cash == 0.0:
        avl_cash = _to_float(_first(*_CASH_KEYS, source=resp))
    reqd_mrgn = _to_float(_first(*_REQ_KEYS, source=body))
    if reqd_mrgn == 0.0:
        reqd_mrgn = _to_float(_first(*_REQ_KEYS, source=resp))
    insuf_fund = _to_float(_first("insufFund", "insufficientFund", "shortfall", source=body))
    rms = str(_first("rmsVldtd", "rmsValidated", source=body) or "").upper()
    stat = str(_first("stat", "status", source=resp) or "").lower()
    st_code = str(_first("stCode", "statusCode", "code", source=resp) or "")

    ok = (
        stat in {"ok", "success", "true"}
        and st_code in {"200", "0", ""}
        and (rms == "OK" or insuf_fund <= 0.0 or avl_cash >= reqd_mrgn)
    )

    print("\n=== summary ===")
    print(f"symbol={args.symbol} token={token}")
    print(f"available_cash={avl_cash:.2f}")
    print(f"required_margin={reqd_mrgn:.2f}")
    print(f"insufficient_fund={insuf_fund:.2f}")
    print(f"rmsVldtd={rms or 'n/a'} stat={stat} stCode={st_code or 'n/a'}")
    print(f"sufficient={'YES' if ok else 'NO'}")
    return 0


def _place_amo_preflight_error(args: argparse.Namespace) -> str | None:
    """Return an error message if live place is not allowed, else None."""
    if os.environ.get("KOTAK_ALLOW_LIVE_PLACE_ORDER", "").strip() != "1":
        return "ERROR: place-amo refused: set environment variable KOTAK_ALLOW_LIVE_PLACE_ORDER=1"
    if not args.confirm_live_order:
        return (
            "ERROR: place-amo refused: pass --confirm-live-order (this places a real broker order)"
        )
    qty = int(args.qty)
    if qty < 1:
        return "ERROR: qty must be >= 1"
    if qty > _MAX_DEV_PLACE_QTY:
        return f"ERROR: qty capped at {_MAX_DEV_PLACE_QTY} for this dev script; reduce --qty"
    return None


def _run_place_amo(args: argparse.Namespace) -> int:
    """
    Gated live AMO market buy via ``KotakNeoOrders`` (same REST path as ``auto_trade_engine``).

    Requires ``KOTAK_ALLOW_LIVE_PLACE_ORDER=1`` and ``--confirm-live-order``.
    """
    err = _place_amo_preflight_error(args)
    if err:
        print(err, file=sys.stderr)
        return 1

    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth  # noqa: PLC0415
    from modules.kotak_neo_auto_trader.orders import KotakNeoOrders  # noqa: PLC0415

    auth = KotakNeoAuth(config_file=args.config)
    if not auth.login():
        print("ERROR: login failed", file=sys.stderr)
        return 1

    orders = KotakNeoOrders(auth)
    variety = str(args.variety).upper()
    print(f"=== place market buy variety={variety} symbol={args.symbol} qty={args.qty} ===")

    resp = orders.place_market_buy(
        symbol=args.symbol,
        quantity=int(args.qty),
        variety=variety,
        exchange=args.exchange.upper(),
        product=args.product.upper(),
    )
    print("=== response ===")
    print(json.dumps(resp, indent=2) if isinstance(resp, dict) else repr(resp))
    bad = (
        resp is None or not isinstance(resp, dict) or str(resp.get("stat", "")).strip() == "Not_Ok"
    )
    return 1 if bad else 0


def main() -> int:
    """Parse CLI and dispatch to check-margin or gated place-amo."""
    sys.path.insert(0, str(_repo_root()))

    default_config = "modules/kotak_neo_auto_trader/kotak_neo.env"

    desc = (
        "Kotak Neo dev smoke: check-margin or gated live AMO market buy "
        "(env file credentials only)."
    )
    parser = argparse.ArgumentParser(description=desc)
    sub = parser.add_subparsers(dest="command", required=True)

    cm_help = "Call REST check-margin for one symbol/qty (no order placed)."
    p_cm = sub.add_parser("check-margin", help=cm_help)
    p_cm.add_argument("--config", default=default_config, help="Path to kotak-style .env file")
    p_cm.add_argument("--symbol", required=True, help="Trading symbol, e.g. RELIANCE-EQ")
    p_cm.add_argument("--qty", type=int, required=True, help="Order quantity")
    p_cm.add_argument(
        "--price",
        type=float,
        default=0.0,
        help="Limit price (ignored when --order-type MKT)",
    )
    p_cm.add_argument(
        "--order-type",
        choices=["L", "MKT"],
        default="L",
        help="Order type for margin check",
    )
    p_cm.add_argument("--transaction-type", choices=["B", "S"], default="B", help="B=Buy, S=Sell")
    p_cm.add_argument("--product", default="CNC", help="Product code (CNC, ...)")
    p_cm.add_argument("--exchange", default="NSE", help="Exchange for scrip token lookup")
    p_cm.set_defaults(func=_run_check_margin)

    po_help = (
        "Place a live AMO (or REGULAR) market BUY; requires env gate and --confirm-live-order."
    )
    p_po = sub.add_parser("place-amo", help=po_help)
    p_po.add_argument("--config", default=default_config, help="Path to kotak-style .env file")
    sym_help = "Trading symbol (use -EQ suffix when required), e.g. RELIANCE-EQ"
    p_po.add_argument("--symbol", required=True, help=sym_help)
    p_po.add_argument("--qty", type=int, default=1, help="Quantity (max 10 for this script)")
    p_po.add_argument("--product", default="CNC", help="Product code")
    p_po.add_argument("--exchange", default="NSE", help="Exchange")
    p_po.add_argument(
        "--variety",
        default="AMO",
        choices=["AMO", "REGULAR"],
        help="Order variety passed to broker (default AMO)",
    )
    p_po.add_argument(
        "--confirm-live-order",
        action="store_true",
        help="Required acknowledgement: this submits a real order to Kotak.",
    )
    p_po.set_defaults(func=_run_place_amo)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
