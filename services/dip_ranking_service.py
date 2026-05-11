"""
Rank current dip candidates using the dip-success model.

This is a thin convenience wrapper around
:class:`services.ml_dip_success_service.MLDipSuccessService`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import pandas as pd

from services.ml_dip_success_service import MLDipSuccessService


@dataclass(frozen=True)
class DipScore:
    ticker: str
    p_net_win: float


def rank_dip_candidates(
    candidates: Iterable[tuple[str, pd.DataFrame]],
    *,
    model: MLDipSuccessService,
    limit: int | None = None,
) -> list[DipScore]:
    """
    Score and rank candidates by calibrated P(net_win).

    Args:
        candidates: Iterable of (ticker, daily_df) up to today for that ticker.
        model: Loaded dip success model.
        limit: Optional cap on returned results.

    Returns:
        Sorted list descending by p_net_win.
    """
    out: list[DipScore] = []
    for ticker, df in candidates:
        p = model.score_current_setup(df)
        if p is None:
            continue
        out.append(DipScore(ticker=ticker, p_net_win=float(p)))

    out.sort(key=lambda x: x.p_net_win, reverse=True)
    return out[:limit] if limit is not None else out
