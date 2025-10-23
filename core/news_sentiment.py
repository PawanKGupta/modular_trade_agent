import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import yfinance as yf

from utils.logger import logger
from config.settings import (
    NEWS_SENTIMENT_ENABLED,
    NEWS_SENTIMENT_LOOKBACK_DAYS,
    NEWS_SENTIMENT_MIN_ARTICLES,
    NEWS_SENTIMENT_POS_THRESHOLD,
    NEWS_SENTIMENT_NEG_THRESHOLD,
    NEWS_SENTIMENT_CACHE_TTL_SEC,
)

# Simple in-memory cache with TTL
_cache: Dict[Tuple[str, str], Tuple[float, dict]] = {}

# Minimal sentiment lexicon (titles only). You can extend/plug a provider later.
_POSITIVE_WORDS = {
    'beat', 'beats', 'surge', 'surges', 'jump', 'jumps', 'soar', 'soars', 'rally', 'rallies',
    'strong', 'bullish', 'upgrade', 'upgrades', 'outperform', 'record', 'growth', 'profit',
    'profits', 'gain', 'gains', 'positive', 'optimistic', 'robust', 'exceed', 'exceeds', 'tops'
}
_NEGATIVE_WORDS = {
    'miss', 'misses', 'fall', 'falls', 'drop', 'drops', 'slide', 'slides', 'plunge', 'plunges',
    'weak', 'bearish', 'downgrade', 'downgrades', 'underperform', 'loss', 'losses', 'decline',
    'declines', 'negative', 'pessimistic', 'probe', 'lawsuit', 'scam', 'fraud', 'raid', 'ban',
    'halt', 'default', 'cut', 'cuts', 'warning', 'warns'
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
    return (ticker.upper(), as_of_date or 'latest')


def get_recent_news(ticker: str) -> List[dict]:
    try:
        return yf.Ticker(ticker).news or []
    except Exception as e:
        logger.warning(f"News fetch failed for {ticker}: {e}")
        return []


def analyze_news_sentiment(ticker: str, as_of_date: Optional[str] = None) -> dict:
    """
    Compute naive sentiment from recent news headlines using a lexicon.

    Returns dict with keys: enabled, score (-1..1), articles, used, confidence (0..1),
    label ('positive'|'neutral'|'negative'), reason (optional string).
    """
    result_neutral = {
        'enabled': bool(NEWS_SENTIMENT_ENABLED),
        'score': 0.0,
        'articles': 0,
        'used': 0,
        'confidence': 0.0,
        'label': 'neutral',
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
        res['reason'] = 'no_news'
        _cache[key] = (now, res)
        return res

    # Determine time window
    if as_of_date:
        end_dt = datetime.strptime(as_of_date, '%Y-%m-%d')
    else:
        end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=NEWS_SENTIMENT_LOOKBACK_DAYS)

    used_scores: List[float] = []
    used_count = 0
    for item in news:
        # yfinance provides providerPublishTime (epoch seconds)
        ts = item.get('providerPublishTime') or item.get('time')
        if ts is None:
            continue
        try:
            dt = datetime.utcfromtimestamp(int(ts))
        except Exception:
            continue
        if not (start_dt <= dt <= end_dt):
            continue
        title = item.get('title', '')
        score = _token_score(title)
        used_scores.append(score)
        used_count += 1

    total_articles = len(news)
    if used_count == 0:
        res = result_neutral.copy()
        res.update({'articles': total_articles, 'reason': 'no_recent_news'})
        _cache[key] = (now, res)
        return res

    avg_score = sum(used_scores) / len(used_scores)
    label = 'positive' if avg_score >= NEWS_SENTIMENT_POS_THRESHOLD else 'negative' if avg_score <= NEWS_SENTIMENT_NEG_THRESHOLD else 'neutral'
    confidence = max(0.1, min(1.0, used_count / max(NEWS_SENTIMENT_MIN_ARTICLES, 5)))

    res = {
        'enabled': True,
        'score': round(avg_score, 3),
        'articles': total_articles,
        'used': used_count,
        'confidence': round(confidence, 3),
        'label': label,
    }

    _cache[key] = (now, res)
    return res