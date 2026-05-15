import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import yfinance as yf

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


def _cache_key(ticker: str, as_of_date: Optional[str]) -> Tuple[str, str]:
    return (ticker.upper(), as_of_date or "latest")


def get_recent_news(ticker: str) -> List[dict]:
    try:
        return yf.Ticker(ticker).news or []
    except Exception as e:
        logger.warning(f"News fetch failed for {ticker}: {e}")
        return []


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
    for item in news:
        # Handle both old and new yfinance API structure
        content = item.get("content", item)  # New API has nested content

        # Try different timestamp fields (both old numeric and new string formats)
        ts = (
            item.get("providerPublishTime")
            or item.get("time")
            or content.get("publishTime")
            or content.get("providerPublishTime")
            or content.get("pubDate")
            or content.get("displayTime")
        )

        if ts is None:
            continue

        try:
            # Handle both numeric timestamps and ISO string timestamps
            if isinstance(ts, str):
                # Parse ISO 8601 string format: "2025-09-24T10:58:31Z"
                if ts.endswith("Z"):
                    dt = datetime.strptime(ts[:-1], "%Y-%m-%dT%H:%M:%S")
                else:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
            elif ts > 1e10:  # Milliseconds timestamp
                dt = datetime.utcfromtimestamp(ts / 1000)
            else:  # Seconds timestamp
                dt = datetime.utcfromtimestamp(int(ts))
        except Exception:
            continue

        if not (start_dt <= dt <= end_dt):
            continue

        # Get title from content or root level
        title = content.get("title") or item.get("title", "")
        if not title:
            continue

        used_titles.append(title)
        used_articles.append(item)  # Store the article

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
    }
    if model_name:
        res["model"] = model_name

    _cache[key] = (now, res)
    return res
