#!/usr/bin/env python3
"""Live-only analysis to verify full news profile (paid APIs when quota allows).

Usage (from repo root, after Marketaux daily quota resets):
  .venv/bin/python tools/live_news_batch_verify.py
  .venv/bin/python tools/live_news_batch_verify.py --symbols AXISCADES.NS,RELIANCE.NS

Loads keys from .env. Does not run backtests (no as_of_date → cheap profile not forced).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_SYMBOLS = [
    "AXISCADES.NS",
    "LINDEINDIA.NS",
    "DMART.NS",
    "RELIANCE.NS",
    "HDFCBANK.NS",
]


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().split("#")[0].strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--symbols",
        default=",".join(DEFAULT_SYMBOLS),
        help="Comma-separated NSE tickers",
    )
    args = parser.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    _load_dotenv()
    os.environ.setdefault("NEWS_SOURCES", "composite")

    from config.strategy_config import StrategyConfig
    from core.news_providers import fetch_composite_news, resolve_news_profile
    from services.analysis_service import AnalysisService

    profile = resolve_news_profile()
    print(f"News profile (live): {profile}")
    print(f"Keys: marketaux={bool(os.getenv('MARKETAUX_API_KEY'))} newsdata={bool(os.getenv('NEWSDATA_API_KEY'))}")
    print()

    svc = AnalysisService(config=StrategyConfig.default())
    any_marketaux = False
    rows: list[dict] = []

    for sym in symbols:
        raw = fetch_composite_news(sym, profile="full")
        by_src: dict[str, int] = {}
        for art in raw:
            src = str(art.get("source") or "unknown")
            by_src[src] = by_src.get(src, 0) + 1
        ma = by_src.get("marketaux", 0)
        nd = by_src.get("newsdata", 0)
        if ma > 0:
            any_marketaux = True

        r = svc.analyze_ticker(sym, enable_multi_timeframe=True, export_to_csv=False)
        ns = r.get("news_sentiment") or {}
        row = {
            "symbol": sym,
            "verdict": r.get("verdict"),
            "fetched_merged": len(raw),
            "fetch_by_source": by_src,
            "sentiment_used": ns.get("used"),
            "sentiment_sources": ns.get("sources"),
            "label": ns.get("label"),
            "score": ns.get("score"),
        }
        rows.append(row)
        print(
            f"{sym}: fetch marketaux={ma} newsdata={nd} merged={len(raw)} | "
            f"sentiment used={ns.get('used')} sources={ns.get('sources')} verdict={r.get('verdict')}"
        )

    print()
    if any_marketaux:
        print("OK: Marketaux returned at least one article in this batch.")
    else:
        print(
            "WARN: No Marketaux articles (likely 402 quota or no coverage). "
            "Check logs for 'Marketaux quota' or re-run after daily reset."
        )

    print(json.dumps(rows, indent=2))
    return 0 if any_marketaux else 1


if __name__ == "__main__":
    sys.exit(main())
