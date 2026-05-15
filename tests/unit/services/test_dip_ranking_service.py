from __future__ import annotations

import pandas as pd

from services.dip_ranking_service import rank_dip_candidates


class _FakeModel:
    def __init__(self, mapping: dict[str, float | None]) -> None:
        self._mapping = mapping

    def score_current_setup(self, df: pd.DataFrame):  # noqa: ANN001
        return self._mapping.get(df.attrs["ticker"])


def test_rank_dip_candidates_orders_desc() -> None:
    df_a = pd.DataFrame({"close": [1.0], "rsi_10": [25.0], "ema9": [2.0]})
    df_a.attrs["ticker"] = "A"
    df_b = pd.DataFrame({"close": [1.0], "rsi_10": [25.0], "ema9": [2.0]})
    df_b.attrs["ticker"] = "B"
    df_c = pd.DataFrame({"close": [1.0], "rsi_10": [35.0], "ema9": [2.0]})
    df_c.attrs["ticker"] = "C"

    model = _FakeModel({"A": 0.2, "B": 0.9, "C": None})
    ranked = rank_dip_candidates([("A", df_a), ("B", df_b), ("C", df_c)], model=model)

    assert [r.ticker for r in ranked] == ["B", "A"]
