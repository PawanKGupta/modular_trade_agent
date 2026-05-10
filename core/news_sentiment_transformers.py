"""
CPU-friendly headline sentiment using Hugging Face Transformers (optional dependency).

Falls back to lexicon scoring in :mod:`core.news_sentiment` when this module cannot load
a model (missing ``torch``/``transformers``, download failure, etc.).
"""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

_FAILED = object()
_pipeline: Any | None = None
_pipeline_lock = threading.Lock()


def map_label_scores_to_float(label_scores: list[dict[str, Any]]) -> float:
    """
    Map pipeline ``return_all_scores`` output to approximately [-1, 1].

    Works for binary (POSITIVE/NEGATIVE, LABEL_0/LABEL_1) and common 3-way
    (POSITIVE / NEGATIVE / NEUTRAL) heads.

    Args:
        label_scores: Dicts with ``label`` and ``score`` (class probability).

    Returns:
        ``P(positive) - P(negative)``, clamped to [-1, 1]. Neutral mass is implicit
        in the softmax and reduces the magnitude of pos/neg when present.
    """
    pos = 0.0
    neg = 0.0
    for d in label_scores:
        lab = str(d.get("label", "")).strip().upper()
        prob = float(d.get("score", 0.0))
        if "NEU" in lab or "NEUTRAL" in lab:
            continue
        if "POS" in lab or lab == "LABEL_1":
            pos += prob
        elif "NEG" in lab or lab == "LABEL_0":
            neg += prob
        elif lab.startswith("LABEL_") and lab not in ("LABEL_0", "LABEL_1"):
            continue

    if pos == 0.0 and neg == 0.0:
        return 0.0

    raw = pos - neg
    return max(-1.0, min(1.0, raw))


def _get_pipeline(model_id: str, max_length: int) -> Any | None:
    """
    Lazy-load a single shared sentiment-analysis pipeline on CPU.

    Args:
        model_id: Hugging Face model identifier.
        max_length: Tokenizer truncation length.

    Returns:
        Pipeline callable, or None if loading failed.
    """
    global _pipeline

    with _pipeline_lock:
        if _pipeline is _FAILED:
            return None
        if _pipeline is not None:
            return _pipeline

        try:
            import torch  # noqa: F401 — ensure dependency present before transformers
            from transformers import pipeline
        except ImportError as e:
            logger.warning(
                "News sentiment transformer unavailable (missing dependency): %s. "
                "Install optional deps: pip install -r requirements-sentiment.txt",
                e,
            )
            _pipeline = _FAILED
            return None

        try:
            pl = pipeline(
                "sentiment-analysis",
                model=model_id,
                tokenizer=model_id,
                device=-1,
                truncation=True,
                max_length=max_length,
                framework="pt",
                return_all_scores=True,
            )
        except Exception as e:
            logger.warning("Failed to create sentiment pipeline for %s: %s", model_id, e)
            _pipeline = _FAILED
            return None

        _pipeline = pl
        logger.info(
            "Loaded CPU sentiment-analysis pipeline: %s (max_length=%s)",
            model_id,
            max_length,
        )
        return _pipeline


def score_headlines_cpu(
    titles: list[str],
    *,
    model_id: str,
    batch_size: int,
    max_length: int,
) -> list[float] | None:
    """
    Score headline strings in batches on CPU.

    Args:
        titles: Headline texts (empty strings are scored as 0.0 without calling the model).
        model_id: Hugging Face hub model id.
        batch_size: Number of headlines per pipeline call.
        max_length: Max tokenizer sequence length.

    Returns:
        One float per title in [-1, 1], or None if the pipeline could not run.
    """
    if not titles:
        return []

    clf = _get_pipeline(model_id, max_length)
    if clf is None:
        return None

    results = [0.0] * len(titles)
    to_score: list[tuple[int, str]] = []
    char_cap = max_length * 4
    for i, raw in enumerate(titles):
        t = (raw or "").strip()
        if t:
            to_score.append((i, t if len(t) <= char_cap else t[:char_cap]))

    chunk_size = max(1, batch_size)

    try:
        for start in range(0, len(to_score), chunk_size):
            batch = to_score[start : start + chunk_size]
            texts = [pair[1] for pair in batch]
            raw_batch = clf(texts, truncation=True, max_length=max_length)

            per_item_lists: list[list[dict[str, Any]]]
            if isinstance(raw_batch, list) and raw_batch and isinstance(raw_batch[0], dict):
                per_item_lists = [raw_batch]
            elif isinstance(raw_batch, list):
                per_item_lists = raw_batch
            else:
                logger.warning("Unexpected sentiment pipeline return type")
                return None

            if len(per_item_lists) != len(texts):
                logger.warning(
                    "Sentiment pipeline length mismatch (%s vs %s)",
                    len(per_item_lists),
                    len(texts),
                )
                return None

            for pair_idx, row_scores in enumerate(per_item_lists):
                if not isinstance(row_scores, list) or not row_scores:
                    return None
                orig_idx, _text = batch[pair_idx]
                results[orig_idx] = map_label_scores_to_float(row_scores)

    except Exception as e:
        logger.warning("Sentiment inference failed: %s", e)
        return None

    return results
