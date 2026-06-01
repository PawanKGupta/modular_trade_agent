#!/usr/bin/env python3
"""Probe free/low-cost news sources for NSE tickers (no secrets in output).

Usage:
  .venv/bin/python tools/news_api_probe.py
  .venv/bin/python tools/news_api_probe.py --symbol AXISCADES.NS

Reads optional API keys from environment:
  FINNHUB_API_KEY, MARKETAUX_API_KEY, NEWS_API_KEY, ALPHAVANTAGE_API_KEY,
  NEWSDATA_API_KEY, FMP_API_KEY
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

import yfinance as yf

USER_AGENT = "ReboundTradeAgent/1.0 (news-probe; +https://github.com/local)"


def _http_get(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> tuple[int, str]:
    hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    req = Request(url, headers=hdrs)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return -1, str(e)


def symbol_parts(symbol: str) -> tuple[str, str, str]:
    s = symbol.upper().strip()
    base = s.replace(".NS", "").replace(".BO", "")
    company_q = base.replace("_", " ")
    return s, base, company_q


def _parse_iso_or_rss_date(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        ts = float(raw)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    text = str(raw).strip()
    if not text:
        return None
    try:
        if text.isdigit():
            ts = int(text)
            if ts > 1e12:
                ts //= 1000
            return datetime.fromtimestamp(ts, tz=timezone.utc)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None


def _recent_count(items: list[dict], lookback_days: int = 30) -> int:
    cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(days=lookback_days)
    n = 0
    for it in items:
        dt = _parse_iso_or_rss_date(it.get("published"))
        if dt is None:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt >= cutoff:
            n += 1
    return n


def probe_yfinance(symbol: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        raw = yf.Ticker(symbol).news or []
    except Exception as e:
        return {"provider": "yfinance", "ok": False, "error": str(e), "latency_ms": int((time.perf_counter() - t0) * 1000)}
    items = []
    for row in raw[:10]:
        content = row.get("content") if isinstance(row.get("content"), dict) else row
        title = (content or {}).get("title") or row.get("title") or ""
        pub = (content or {}).get("pubDate") or row.get("providerPublishTime")
        items.append({"title": title[:120], "published": pub})
    return {
        "provider": "yfinance",
        "ok": True,
        "total": len(raw),
        "recent_30d": _recent_count(items),
        "sample_titles": [i["title"] for i in items[:3]],
        "latency_ms": int((time.perf_counter() - t0) * 1000),
        "needs_key": False,
    }


def probe_google_news_rss(symbol: str) -> dict[str, Any]:
    _, base, company_q = symbol_parts(symbol)
    query = quote_plus(f"{company_q} stock India NSE")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    t0 = time.perf_counter()
    status, body = _http_get(url)
    latency = int((time.perf_counter() - t0) * 1000)
    if status != 200:
        return {"provider": "google_news_rss", "ok": False, "status": status, "error": body[:200], "latency_ms": latency, "needs_key": False}
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        return {"provider": "google_news_rss", "ok": False, "error": str(e), "latency_ms": latency, "needs_key": False}
    items = []
    for item in root.findall(".//item")[:15]:
        title = (item.findtext("title") or "").strip()
        pub = item.findtext("pubDate")
        items.append({"title": title[:120], "published": pub})
    return {
        "provider": "google_news_rss",
        "ok": True,
        "total": len(items),
        "recent_30d": _recent_count(items),
        "sample_titles": [i["title"] for i in items[:3]],
        "latency_ms": latency,
        "needs_key": False,
    }


def probe_finnhub(symbol: str, api_key: str) -> dict[str, Any]:
    _, base, _ = symbol_parts(symbol)
    # Finnhub uses exchange suffix for some markets; NSE often as SYMBOL.NS or just symbol
    from_date = (datetime.now(timezone.utc) - __import__("datetime").timedelta(days=30)).strftime("%Y-%m-%d")
    to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    url = (
        f"https://finnhub.io/api/v1/company-news?symbol={quote_plus(base)}"
        f"&from={from_date}&to={to_date}&token={api_key}"
    )
    t0 = time.perf_counter()
    status, body = _http_get(url)
    latency = int((time.perf_counter() - t0) * 1000)
    if status != 200:
        return {"provider": "finnhub", "ok": False, "status": status, "error": body[:300], "latency_ms": latency, "needs_key": True}
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"provider": "finnhub", "ok": False, "error": body[:300], "latency_ms": latency, "needs_key": True}
    if isinstance(data, dict) and data.get("error"):
        return {"provider": "finnhub", "ok": False, "error": data.get("error"), "latency_ms": latency, "needs_key": True}
    items = []
    for row in (data or [])[:15]:
        items.append({"title": (row.get("headline") or "")[:120], "published": row.get("datetime")})
    return {
        "provider": "finnhub",
        "ok": True,
        "total": len(data) if isinstance(data, list) else 0,
        "recent_30d": _recent_count(items),
        "sample_titles": [i["title"] for i in items[:3]],
        "latency_ms": latency,
        "needs_key": True,
    }


def probe_marketaux(symbol: str, api_key: str) -> dict[str, Any]:
    _, base, _ = symbol_parts(symbol)
    url = (
        "https://api.marketaux.com/v1/news/all?"
        f"symbols={quote_plus(base)}&filter_entities=true&language=en&limit=10&api_token={api_key}"
    )
    t0 = time.perf_counter()
    status, body = _http_get(url)
    latency = int((time.perf_counter() - t0) * 1000)
    if status != 200:
        return {"provider": "marketaux", "ok": False, "status": status, "error": body[:300], "latency_ms": latency, "needs_key": True}
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"provider": "marketaux", "ok": False, "error": body[:300], "latency_ms": latency, "needs_key": True}
    if data.get("error"):
        return {"provider": "marketaux", "ok": False, "error": data, "latency_ms": latency, "needs_key": True}
    rows = data.get("data") or []
    items = [{"title": (r.get("title") or "")[:120], "published": r.get("published_at")} for r in rows]
    return {
        "provider": "marketaux",
        "ok": True,
        "total": data.get("meta", {}).get("found", len(rows)),
        "recent_30d": _recent_count(items),
        "sample_titles": [i["title"] for i in items[:3]],
        "has_sentiment": any(r.get("entities") for r in rows),
        "latency_ms": latency,
        "needs_key": True,
    }


def probe_alphavantage(symbol: str, api_key: str) -> dict[str, Any]:
    _, base, _ = symbol_parts(symbol)
    url = (
        "https://www.alphavantage.co/query?function=NEWS_SENTIMENT"
        f"&tickers={quote_plus(base)}&limit=10&apikey={api_key}"
    )
    t0 = time.perf_counter()
    status, body = _http_get(url)
    latency = int((time.perf_counter() - t0) * 1000)
    if status != 200:
        return {"provider": "alphavantage", "ok": False, "status": status, "error": body[:300], "latency_ms": latency, "needs_key": True}
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"provider": "alphavantage", "ok": False, "error": body[:300], "latency_ms": latency, "needs_key": True}
    if "Note" in data or "Information" in data:
        return {"provider": "alphavantage", "ok": False, "error": data.get("Note") or data.get("Information"), "latency_ms": latency, "needs_key": True}
    feed = data.get("feed") or []
    items = [{"title": (r.get("title") or "")[:120], "published": r.get("time_published")} for r in feed]
    return {
        "provider": "alphavantage",
        "ok": True,
        "total": len(feed),
        "recent_30d": _recent_count(items),
        "sample_titles": [i["title"] for i in items[:3]],
        "has_sentiment": True,
        "latency_ms": latency,
        "needs_key": True,
    }


def probe_newsdata(symbol: str, api_key: str) -> dict[str, Any]:
    _, base, company_q = symbol_parts(symbol)
    q = quote_plus(f"{company_q} NSE")
    url = f"https://newsdata.io/api/1/news?apikey={api_key}&q={q}&country=in&language=en"
    t0 = time.perf_counter()
    status, body = _http_get(url)
    latency = int((time.perf_counter() - t0) * 1000)
    if status != 200:
        return {"provider": "newsdata.io", "ok": False, "status": status, "error": body[:300], "latency_ms": latency, "needs_key": True}
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"provider": "newsdata.io", "ok": False, "error": body[:300], "latency_ms": latency, "needs_key": True}
    if data.get("status") != "success":
        return {"provider": "newsdata.io", "ok": False, "error": data.get("results", data), "latency_ms": latency, "needs_key": True}
    rows = data.get("results") or []
    items = [{"title": (r.get("title") or "")[:120], "published": r.get("pubDate")} for r in rows]
    return {
        "provider": "newsdata.io",
        "ok": True,
        "total": data.get("totalResults", len(rows)),
        "recent_30d": _recent_count(items),
        "sample_titles": [i["title"] for i in items[:3]],
        "latency_ms": latency,
        "needs_key": True,
    }


def probe_fmp(symbol: str, api_key: str) -> dict[str, Any]:
    _, base, _ = symbol_parts(symbol)
    url = f"https://financialmodelingprep.com/api/v3/stock_news?tickers={quote_plus(base)}&limit=10&apikey={api_key}"
    t0 = time.perf_counter()
    status, body = _http_get(url)
    latency = int((time.perf_counter() - t0) * 1000)
    if status != 200:
        return {"provider": "fmp", "ok": False, "status": status, "error": body[:300], "latency_ms": latency, "needs_key": True}
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"provider": "fmp", "ok": False, "error": body[:300], "latency_ms": latency, "needs_key": True}
    if isinstance(data, dict) and "Error Message" in data:
        return {"provider": "fmp", "ok": False, "error": data["Error Message"], "latency_ms": latency, "needs_key": True}
    rows = data if isinstance(data, list) else []
    items = [{"title": (r.get("title") or "")[:120], "published": r.get("publishedDate")} for r in rows]
    return {
        "provider": "fmp",
        "ok": True,
        "total": len(rows),
        "recent_30d": _recent_count(items),
        "sample_titles": [i["title"] for i in items[:3]],
        "latency_ms": latency,
        "needs_key": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="AXISCADES.NS")
    parser.add_argument("--also", default="RELIANCE.NS", help="Second symbol for coverage check")
    args = parser.parse_args()

    symbols = [args.symbol]
    if args.also and args.also not in symbols:
        symbols.append(args.also)

    keys = {
        "finnhub": os.getenv("FINNHUB_API_KEY", "").strip(),
        "marketaux": os.getenv("MARKETAUX_API_KEY", "").strip(),
        "alphavantage": os.getenv("ALPHAVANTAGE_API_KEY", "").strip(),
        "newsdata": os.getenv("NEWSDATA_API_KEY", "").strip(),
        "fmp": os.getenv("FMP_API_KEY", "").strip(),
    }

    print("News API probe — symbols:", ", ".join(symbols))
    print("Keys present:", {k: bool(v) for k, v in keys.items()})
    print()

    for symbol in symbols:
        print("=" * 72)
        print(f"SYMBOL: {symbol}")
        print("=" * 72)
        results: list[dict[str, Any]] = []

        results.append(probe_yfinance(symbol))
        results.append(probe_google_news_rss(symbol))

        if keys["finnhub"]:
            results.append(probe_finnhub(symbol, keys["finnhub"]))
        else:
            # Finnhub public demo works only for US tickers; still document
            demo = probe_finnhub("AAPL", "demo")
            results.append(
                {
                    "provider": "finnhub",
                    "ok": False,
                    "skipped": True,
                    "reason": "FINNHUB_API_KEY not set",
                    "demo_aapl_ok": demo.get("ok"),
                    "demo_aapl_recent_30d": demo.get("recent_30d"),
                    "needs_key": True,
                }
            )

        for name, key, fn in [
            ("marketaux", keys["marketaux"], probe_marketaux),
            ("alphavantage", keys["alphavantage"], probe_alphavantage),
            ("newsdata", keys["newsdata"], probe_newsdata),
            ("fmp", keys["fmp"], probe_fmp),
        ]:
            if key:
                results.append(fn(symbol, key))
            else:
                results.append(
                    {
                        "provider": name,
                        "ok": False,
                        "skipped": True,
                        "reason": f"{name.upper()}_API_KEY not set",
                        "needs_key": True,
                    }
                )

        for r in results:
            print(json.dumps(r, indent=2, default=str))
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
