"""Headline-backed sentiment from merged news sources.

``get_recent_news`` uses :mod:`core.news_providers` (yfinance, Google RSS, and optional
Marketaux / NewsData when API keys are set; Finnhub excluded). ``analyze_news_sentiment`` scores
deduplicated headlines in the lookback window (lexicon or local Transformer).

Manual verification: ``tools/yfinance_news_smoke.py`` and ``tools/news_api_probe.py``.
"""

import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from config.settings import (
    NEWS_SENTIMENT_BACKEND,
    NEWS_SENTIMENT_CACHE_TTL_SEC,
    NEWS_SENTIMENT_ENABLED,
    NEWS_SENTIMENT_LOOKBACK_DAYS,
    NEWS_SENTIMENT_MIN_ARTICLES,
    NEWS_SENTIMENT_NEG_THRESHOLD,
    NEWS_SENTIMENT_POS_THRESHOLD,
    NEWS_SENTIMENT_TRANSFORMER_BATCH_SIZE,
    NEWS_SENTIMENT_TRANSFORMER_MAX_LENGTH,
    NEWS_SENTIMENT_TRANSFORMER_MODEL,
)
from utils.logger import logger

# Simple in-memory cache with TTL
_cache: Dict[Tuple[str, str], Tuple[float, dict]] = {}

# Minimal sentiment lexicon (titles only). You can extend/plug a provider later.
_POSITIVE_WORDS = {
    "beat",
    "beats",
    "surge",
    "surges",
    "jump",
    "jumps",
    "soar",
    "soars",
    "rally",
    "rallies",
    "strong",
    "bullish",
    "upgrade",
    "upgrades",
    "outperform",
    "record",
    "growth",
    "profit",
    "profits",
    "gain",
    "gains",
    "positive",
    "optimistic",
    "robust",
    "exceed",
    "exceeds",
    "tops",
}
_NEGATIVE_WORDS = {
    "miss",
    "misses",
    "fall",
    "falls",
    "drop",
    "drops",
    "slide",
    "slides",
    "plunge",
    "plunges",
    "weak",
    "bearish",
    "downgrade",
    "downgrades",
    "underperform",
    "loss",
    "losses",
    "decline",
    "declines",
    "negative",
    "pessimistic",
    "probe",
    "lawsuit",
    "scam",
    "fraud",
    "raid",
    "ban",
    "halt",
    "default",
    "cut",
    "cuts",
    "warning",
    "warns",
}


def _token_score(text: str) -> float:
    if not text:
        return 0.0
    text_l = text.lower()
    pos = sum(1 for w in _POSITIVE_WORDS if w in text_l)
    neg = sum(1 for w in _NEGATIVE_WORDS if w in text_l)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total


def _now_ts() -> float:
    return time.time()


def _cache_key(ticker: str, as_of_date: Optional[str]) -> Tuple[str, str, str]:
    from core.news_providers import resolve_news_profile

    profile = resolve_news_profile(as_of_date=as_of_date)
    return (ticker.upper(), as_of_date or "latest", profile)


def get_recent_news(ticker: str, profile: Optional[str] = None) -> List[dict]:
    """Return merged recent headlines for *ticker* (profile: cheap | full)."""
    from core.news_providers import enabled_sources, fetch_composite_news, fetch_yfinance_articles

    try:
        sources = enabled_sources(profile)
        if sources == ["yfinance"]:
            return fetch_yfinance_articles(ticker)
        return fetch_composite_news(ticker, profile=profile)
    except Exception as e:
        logger.warning("News fetch failed for %s: %s", ticker, e)
        return []


def news_item_timestamp_and_title(item: Dict[str, Any]) -> Tuple[Any, str]:
    """Return publish time and title for yfinance-shaped or normalized articles."""
    if item.get("source") in ("google_rss", "marketaux", "newsdata", "finnhub"):
        return item.get("providerPublishTime"), (item.get("title") or "").strip()
    return yfinance_news_raw_timestamp_and_title(item)


def parse_news_timestamp(ts_raw: Any) -> Optional[datetime]:
    """Parse article timestamps from any supported provider payload."""
    from core.news_providers import parse_published

    if ts_raw is None:
        return None
    dt = parse_published(ts_raw)
    if dt is not None:
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    return parse_yfinance_news_timestamp(ts_raw)


def yfinance_news_raw_timestamp_and_title(item: Dict[str, Any]) -> Tuple[Any, str]:
    """Return Yahoo ``.news`` item publish time payload and stripped title.

    Mirrors yfinance payloads where detail may live on ``content`` or the root dict.
    Used by :func:`analyze_news_sentiment` and ``tools/yfinance_news_smoke.py`` so CLI
    output matches sentiment filtering semantics for timestamp/title precedence.

    Args:
        item: One element from ``yf.Ticker(...).news``.

    Returns:
        ``(timestamp_field, title)`` — ``timestamp_field`` is whatever Yahoo provided
        (Unix seconds, ms, ISO string); parse with :func:`parse_yfinance_news_timestamp`.
    """
    content = item.get("content", item)
    ts_raw = (
        item.get("providerPublishTime")
        or item.get("time")
        or content.get("publishTime")
        or content.get("providerPublishTime")
        or content.get("pubDate")
        or content.get("displayTime")
    )
    title = (content.get("title") or item.get("title") or "").strip()
    return ts_raw, title


def parse_yfinance_news_timestamp(ts_raw: Any) -> Optional[datetime]:
    """Parse Yahoo news time fields into UTC-naive ``datetime`` for lookback filtering.

    Args:
        ts_raw: Seconds, milliseconds, or ISO-ish string from
            :func:`yfinance_news_raw_timestamp_and_title`.

    Returns:
        Parsed instant, or ``None`` if parsing fails.
    """
    try:
        if isinstance(ts_raw, str):
            if ts_raw.endswith("Z"):
                return datetime.strptime(ts_raw[:-1], "%Y-%m-%dT%H:%M:%S")
            return datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).replace(tzinfo=None)
        # bool is a subtype of int; Yahoo never sends booleans — reject if so.
        if isinstance(ts_raw, (int, float)) and not isinstance(ts_raw, bool) and ts_raw > 1e10:
            return datetime.utcfromtimestamp(ts_raw / 1000)
        if isinstance(ts_raw, (int, float)) and not isinstance(ts_raw, bool):
            return datetime.utcfromtimestamp(int(ts_raw))
    except Exception:
        return None
    return None


def analyze_news_sentiment(ticker: str, as_of_date: Optional[str] = None) -> dict:
    """
    Compute sentiment from recent news headlines.

    By default (``NEWS_SENTIMENT_BACKEND=auto``), uses a small Hugging Face Transformers
    model on **CPU** when ``torch``/``transformers`` are installed; otherwise falls back
    to a minimal word-list heuristic. See ``requirements-sentiment.txt`` for optional deps.

    Returns dict with keys: enabled, score (-1..1), articles, used, confidence (0..1),
    label ('positive'|'neutral'|'negative'), reason (optional string),
    scorer ('transformer'|'lexicon'), model (optional HF id when transformer used).
    """
    result_neutral = {
        "enabled": bool(NEWS_SENTIMENT_ENABLED),
        "score": 0.0,
        "articles": [],  # Should be list of articles, not int
        "used": 0,
        "confidence": 0.0,
        "label": "neutral",
        "total": 0,  # Add total count for backward compatibility
        "scorer": "none",
    }

    if not NEWS_SENTIMENT_ENABLED:
        return result_neutral

    key = _cache_key(ticker, as_of_date)
    now = _now_ts()
    cached = _cache.get(key)
    if cached and (now - cached[0]) < NEWS_SENTIMENT_CACHE_TTL_SEC:
        return cached[1]

    # Pull news and filter by lookback/as_of_date
    news = get_recent_news(ticker)
    if not news:
        res = result_neutral.copy()
        res.update({"reason": "no_news", "total": 0})
        _cache[key] = (now, res)
        return res

    # Determine time window (use UTC for consistency with news timestamps)
    if as_of_date:
        end_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
    else:
        end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=NEWS_SENTIMENT_LOOKBACK_DAYS)

    used_titles: List[str] = []
    used_articles: List[dict] = []
    source_counts: Dict[str, int] = {}
    for item in news:
        ts_raw, title = news_item_timestamp_and_title(item)
        if ts_raw is None:
            continue

        dt = parse_news_timestamp(ts_raw)
        if dt is None:
            continue

        if not (start_dt <= dt <= end_dt):
            continue

        if not title:
            continue

        used_titles.append(title)
        used_articles.append(item)  # Store the article
        src = str(item.get("source") or "yfinance")
        source_counts[src] = source_counts.get(src, 0) + 1

    total_articles = len(news)
    used_count = len(used_titles)
    if used_count == 0:
        res = result_neutral.copy()
        res.update({"articles": [], "total": total_articles, "reason": "no_recent_news"})
        _cache[key] = (now, res)
        return res

    want_transformer = NEWS_SENTIMENT_BACKEND in ("auto", "transformer")
    used_scores: List[float]
    scorer = "lexicon"
    model_name: Optional[str] = None

    if want_transformer:
        from core.news_sentiment_transformers import score_headlines_cpu

        tf_scores = score_headlines_cpu(
            used_titles,
            model_id=NEWS_SENTIMENT_TRANSFORMER_MODEL,
            batch_size=NEWS_SENTIMENT_TRANSFORMER_BATCH_SIZE,
            max_length=NEWS_SENTIMENT_TRANSFORMER_MAX_LENGTH,
        )
        if tf_scores is not None and len(tf_scores) == used_count:
            used_scores = tf_scores
            scorer = "transformer"
            model_name = NEWS_SENTIMENT_TRANSFORMER_MODEL
        else:
            used_scores = [_token_score(t) for t in used_titles]
            if NEWS_SENTIMENT_BACKEND == "transformer":
                logger.warning(
                    "NEWS_SENTIMENT_BACKEND=transformer but CPU pipeline unavailable; "
                    "using lexicon for %s",
                    ticker,
                )
    else:
        used_scores = [_token_score(t) for t in used_titles]

    avg_score = sum(used_scores) / len(used_scores)
    label = (
        "positive"
        if avg_score >= NEWS_SENTIMENT_POS_THRESHOLD
        else "negative" if avg_score <= NEWS_SENTIMENT_NEG_THRESHOLD else "neutral"
    )
    confidence = max(0.1, min(1.0, used_count / max(NEWS_SENTIMENT_MIN_ARTICLES, 5)))

    res = {
        "enabled": True,
        "score": round(avg_score, 3),
        "articles": used_articles,  # List of articles used
        "total": total_articles,  # Total count of articles
        "used": used_count,
        "confidence": round(confidence, 3),
        "label": label,
        "scorer": scorer,
        "sources": source_counts,
    }
    if model_name:
        res["model"] = model_name

    _cache[key] = (now, res)
    return res


def enrich_result_with_paid_news(result: dict) -> dict:
    """
    Re-score news for a filtered buy candidate using paid APIs (Marketaux / NewsData).

    Universe scans should use ``news_profile='cheap'``; call this only for shortlisted names.
    May downgrade ``buy`` / ``strong_buy`` to ``watch`` when composite sentiment is strongly negative.
    """
    from config.settings import (
        NEWS_SENTIMENT_DOWNGRADE_MIN_CONFIDENCE,
        NEWS_SENTIMENT_DOWNGRADE_SCORE_THRESHOLD,
        NEWS_SENTIMENT_MIN_ARTICLES,
    )
    from core.news_context import reset_news_profile, set_news_profile

    ticker = result.get("ticker")
    if not ticker:
        return result

    token = set_news_profile("full")
    try:
        keys_to_drop = [k for k in _cache if k[0] == str(ticker).upper()]
        for key in keys_to_drop:
            _cache.pop(key, None)
        sentiment = analyze_news_sentiment(ticker)
    finally:
        reset_news_profile(token)

    result["news_sentiment"] = sentiment

    verdict = result.get("verdict")
    if verdict not in ("buy", "strong_buy") or not sentiment.get("enabled"):
        return result

    used = int(sentiment.get("used", 0))
    conf = float(sentiment.get("confidence", 0.0))
    score = float(sentiment.get("score", 0.0))
    min_used = max(1, int(NEWS_SENTIMENT_MIN_ARTICLES))
    if (
        used >= min_used
        and conf >= NEWS_SENTIMENT_DOWNGRADE_MIN_CONFIDENCE
        and score <= NEWS_SENTIMENT_DOWNGRADE_SCORE_THRESHOLD
    ):
        result["verdict"] = "watch"
        justification = list(result.get("justification") or [])
        if "news_negative" not in justification:
            justification.append("news_negative")
        result["justification"] = justification

    return result


def enrich_filtered_candidates_with_paid_news(candidates: list[dict]) -> list[dict]:
    """Apply :func:`enrich_result_with_paid_news` to each filtered candidate."""
    import os

    flag = os.getenv("NEWS_ENRICH_FILTERED_NEWS", "true").lower()
    if flag not in ("1", "true", "yes", "on"):
        return candidates
    has_paid = bool(os.getenv("MARKETAUX_API_KEY", "").strip()) or bool(
        os.getenv("NEWSDATA_API_KEY", "").strip()
    )
    if not has_paid:
        return candidates

    enriched: list[dict] = []
    for row in candidates:
        try:
            enriched.append(enrich_result_with_paid_news(dict(row)))
        except Exception as exc:
            logger.warning("Paid news enrich failed for %s: %s", row.get("ticker"), exc)
            enriched.append(row)
    return enriched
