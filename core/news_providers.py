"""Multi-source news fetchers merged into a yfinance-compatible article list.

Providers normalize to dicts consumed by :mod:`core.news_sentiment` (``title``,
``providerPublishTime``, optional ``source`` / ``url``).

Enable via ``NEWS_SOURCES=composite`` (default) or an explicit comma list, e.g.
``yfinance,google_rss,marketaux,newsdata``. Finnhub is excluded (poor NSE coverage).
API keys are read from environment (never commit real keys).
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

import yfinance as yf

from utils.logger import logger

_USER_AGENT = "ReboundTradeAgent/1.0"
_COMPANY_QUERY_ALIASES: dict[str, str] = {
    "DMART": "Avenue Supermarts DMart",
    "LINDEINDIA": "Linde India",
}


def _env_flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _http_get(url: str, timeout: int = 20) -> str:
    req = Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "*/*"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def base_symbol(ticker: str) -> str:
    return ticker.upper().strip().replace(".NS", "").replace(".BO", "")


def nse_symbol(ticker: str) -> str:
    t = ticker.upper().strip()
    if t.endswith(".NS") or t.endswith(".BO"):
        return t
    return f"{t}.NS"


def company_search_query(ticker: str) -> str:
    base = base_symbol(ticker)
    return _COMPANY_QUERY_ALIASES.get(base, base.replace("_", " "))


def normalize_article(
    title: str,
    published: datetime | None,
    source: str,
    url: str | None = None,
) -> dict[str, Any]:
    """Build an article dict compatible with :func:`core.news_sentiment.news_item_timestamp_and_title`."""
    ts: int | str | None = None
    if published is not None:
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        ts = int(published.timestamp())
    return {
        "title": title.strip(),
        "providerPublishTime": ts,
        "source": source,
        "url": url,
    }


def parse_published(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
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
        if text.endswith("Z"):
            return datetime.strptime(text[:-1], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, IndexError):
        return None


def dedupe_key(title: str) -> str:
    t = title.lower().strip()
    if " - " in t:
        t = t.rsplit(" - ", 1)[0].strip()
    return re.sub(r"\s+", " ", t)


def _article_title(item: dict[str, Any]) -> str:
    content = item.get("content", item)
    if isinstance(content, dict):
        return (content.get("title") or item.get("title") or "").strip()
    return (item.get("title") or "").strip()


def _article_timestamp_raw(item: dict[str, Any]) -> Any:
    content = item.get("content", item)
    if not isinstance(content, dict):
        content = item
    return (
        item.get("providerPublishTime")
        or item.get("time")
        or content.get("publishTime")
        or content.get("providerPublishTime")
        or content.get("pubDate")
        or content.get("displayTime")
    )


def merge_articles(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge provider lists, dedupe by normalized title, newest first."""
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for group in groups:
        candidates.extend(group)

    def sort_key(item: dict[str, Any]) -> float:
        dt = parse_published(_article_timestamp_raw(item))
        return dt.timestamp() if dt else 0.0

    candidates.sort(key=sort_key, reverse=True)
    for item in candidates:
        title = _article_title(item)
        if not title:
            continue
        key = dedupe_key(title)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def fetch_yfinance_articles(ticker: str) -> list[dict[str, Any]]:
    try:
        raw = yf.Ticker(ticker).news or []
        out: list[dict[str, Any]] = []
        for item in raw:
            if not _article_title(item):
                continue
            normalized = dict(item)
            if "source" not in normalized:
                normalized["source"] = "yfinance"
            out.append(normalized)
        return out
    except Exception as e:
        logger.warning("yfinance news fetch failed for %s: %s", ticker, e)
        return []


def fetch_google_rss_articles(ticker: str, limit: int = 20) -> list[dict[str, Any]]:
    cq = company_search_query(ticker)
    query = quote(f"{cq} stock India NSE earnings")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        root = ET.fromstring(_http_get(url))
    except Exception as e:
        logger.warning("Google RSS news fetch failed for %s: %s", ticker, e)
        return []
    articles: list[dict[str, Any]] = []
    for item in root.findall(".//item")[:limit]:
        title = (item.findtext("title") or "").strip()
        pub = item.findtext("pubDate")
        link = item.findtext("link")
        if not title:
            continue
        articles.append(
            normalize_article(
                title=title,
                published=parse_published(pub),
                source="google_rss",
                url=link,
            )
        )
    return articles


def _marketaux_limit() -> int:
    try:
        return max(1, min(3, int(os.getenv("MARKETAUX_NEWS_LIMIT", "3"))))
    except ValueError:
        return 3


def fetch_marketaux_articles(
    ticker: str, api_key: str, limit: int | None = None
) -> list[dict[str, Any]]:
    sym = nse_symbol(ticker)
    page_limit = limit if limit is not None else _marketaux_limit()
    pub_after = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M")
    url = (
        "https://api.marketaux.com/v1/news/all?"
        f"symbols={quote(sym)}&countries=in&filter_entities=true&limit={page_limit}"
        f"&published_after={quote(pub_after)}&api_token={api_key}"
    )
    try:
        import json

        data = json.loads(_http_get(url))
        if data.get("error"):
            url2 = (
                "https://api.marketaux.com/v1/news/all?"
                f"search={quote(company_search_query(ticker))}&countries=in&limit={page_limit}"
                f"&published_after={quote(pub_after)}&api_token={api_key}"
            )
            data = json.loads(_http_get(url2))
        rows = data.get("data") or []
    except Exception as e:
        err = str(e)
        if "402" in err or "429" in err or "Payment" in err or "TOO MANY" in err.upper():
            logger.warning(
                "Marketaux quota/limit reached for %s (free tier: 100 req/day, 3 articles/req): %s",
                ticker,
                err[:120],
            )
        else:
            logger.warning("Marketaux news fetch failed for %s: %s", ticker, err[:120])
        return []

    articles: list[dict[str, Any]] = []
    for row in rows:
        title = (row.get("title") or "").strip()
        if not title:
            continue
        articles.append(
            normalize_article(
                title=title,
                published=parse_published(row.get("published_at")),
                source="marketaux",
                url=row.get("url"),
            )
        )
    return articles


def fetch_newsdata_articles(ticker: str, api_key: str, limit: int = 10) -> list[dict[str, Any]]:
    q = quote(company_search_query(ticker))
    url = f"https://newsdata.io/api/1/latest?apikey={api_key}&country=in&language=en&q={q}"
    try:
        import json

        data = json.loads(_http_get(url))
        if data.get("status") != "success":
            return []
        rows = (data.get("results") or [])[:limit]
    except Exception as e:
        err = str(e)
        if "429" in err or "TOO MANY" in err.upper():
            logger.warning(
                "NewsData.io daily credit/rate limit reached for %s (free tier: 200 credits/day): %s",
                ticker,
                err[:120],
            )
        else:
            logger.warning("NewsData.io fetch failed for %s: %s", ticker, err[:120])
        return []

    articles: list[dict[str, Any]] = []
    for row in rows:
        title = (row.get("title") or "").strip()
        if not title:
            continue
        articles.append(
            normalize_article(
                title=title,
                published=parse_published(row.get("pubDate")),
                source="newsdata",
                url=row.get("link"),
            )
        )
    return articles


def fetch_finnhub_articles(ticker: str, api_key: str) -> list[dict[str, Any]]:
    base = base_symbol(ticker)
    from_d = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    to_d = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    url = (
        f"https://finnhub.io/api/v1/company-news?symbol={quote(base)}"
        f"&from={from_d}&to={to_d}&token={api_key}"
    )
    try:
        import json

        data = json.loads(_http_get(url))
        if not isinstance(data, list):
            return []
    except Exception as e:
        logger.warning("Finnhub news fetch failed for %s: %s", ticker, e)
        return []

    articles: list[dict[str, Any]] = []
    for row in data:
        title = (row.get("headline") or "").strip()
        if not title:
            continue
        articles.append(
            normalize_article(
                title=title,
                published=parse_published(row.get("datetime")),
                source="finnhub",
                url=row.get("url"),
            )
        )
    return articles


_EXCLUDED_NEWS_SOURCES = frozenset({"finnhub"})
_CHEAP_SOURCES = ("yfinance", "google_rss")
_PAID_SOURCES = ("marketaux", "newsdata")


def resolve_news_profile(
    *,
    news_profile: str | None = None,
    as_of_date: str | None = None,
) -> str:
    """Resolve cheap (free) vs full (incl. paid APIs) news profile."""
    if news_profile in ("cheap", "full"):
        return news_profile
    # auto
    if as_of_date:
        return os.getenv("NEWS_BACKTEST_PROFILE", "cheap").strip().lower() or "cheap"
    ctx = None
    try:
        from core.news_context import current_news_profile

        ctx = current_news_profile()
    except ImportError:
        pass
    if ctx in ("cheap", "full"):
        return ctx
    return os.getenv("NEWS_LIVE_PROFILE", "full").strip().lower() or "full"


def enabled_sources(profile: str | None = None) -> list[str]:
    """Sources for *profile*: ``cheap`` = yfinance + Google RSS; ``full`` adds paid APIs."""
    if profile is None:
        try:
            from core.news_context import current_news_profile

            profile = current_news_profile()
        except ImportError:
            profile = None
    if profile is None:
        profile = resolve_news_profile()

    if profile == "cheap":
        return list(_CHEAP_SOURCES)

    raw = os.getenv("NEWS_SOURCES", "composite").strip().lower()
    if raw in ("", "composite"):
        sources = list(_CHEAP_SOURCES)
        if os.getenv("MARKETAUX_API_KEY", "").strip():
            sources.append("marketaux")
        if os.getenv("NEWSDATA_API_KEY", "").strip():
            sources.append("newsdata")
        return sources
    if raw == "yfinance":
        return ["yfinance"]
    sources = [s.strip() for s in raw.split(",") if s.strip()]
    filtered = [s for s in sources if s not in _EXCLUDED_NEWS_SOURCES]
    if len(filtered) < len(sources):
        logger.debug("Excluded news sources: %s", sorted(_EXCLUDED_NEWS_SOURCES))
    return filtered


def fetch_composite_news(ticker: str, profile: str | None = None) -> list[dict[str, Any]]:
    """Fetch and merge articles from all enabled news sources."""
    if profile is None:
        try:
            from core.news_context import current_news_profile

            profile = current_news_profile()
        except ImportError:
            profile = None
    sources = enabled_sources(profile)
    groups: list[list[dict[str, Any]]] = []
    marketaux_key = os.getenv("MARKETAUX_API_KEY", "").strip()
    newsdata_key = os.getenv("NEWSDATA_API_KEY", "").strip()

    for name in sources:
        if name == "yfinance":
            groups.append(fetch_yfinance_articles(ticker))
        elif name == "google_rss" and _env_flag("NEWS_GOOGLE_RSS_ENABLED", "true"):
            groups.append(fetch_google_rss_articles(ticker))
        elif name == "marketaux" and marketaux_key:
            groups.append(fetch_marketaux_articles(ticker, marketaux_key))
        elif name == "newsdata" and newsdata_key:
            groups.append(fetch_newsdata_articles(ticker, newsdata_key))
        elif name not in (*_CHEAP_SOURCES, *_PAID_SOURCES, "finnhub"):
            logger.warning("Unknown NEWS_SOURCES entry ignored: %s", name)

    merged = merge_articles(*groups)
    logger.debug(
        "%s news profile=%s sources=%s counts=%s merged=%d",
        ticker,
        profile or resolve_news_profile(),
        sources,
        [len(g) for g in groups],
        len(merged),
    )
    return merged
