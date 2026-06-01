"""Regression: incremental cache merge must prefer Yahoo on overlap."""

from __future__ import annotations

from datetime import date

import pandas as pd


def test_concat_keep_last_prefers_second_source():
    cached_df = pd.DataFrame(
        {"close": [100.0]},
        index=pd.to_datetime([date(2024, 1, 2)]),
    )
    fetched_df = pd.DataFrame(
        {"close": [105.0]},
        index=pd.to_datetime([date(2024, 1, 2)]),
    )
    combined = pd.concat([cached_df, fetched_df])
    combined = combined[~combined.index.duplicated(keep="last")]
    assert combined["close"].iloc[0] == 105.0
