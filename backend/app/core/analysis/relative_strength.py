"""
relative_strength.py
====================
Relative strength of a stock versus the market index (Nifty 50, ^NSEI).

`rs_score` returns 0–100 where 50 is neutral (tracking the index), > 50 means the
stock is OUTPERFORMING the index over the lookback windows. Multiple windows
(~1m / 3m / 6m) are averaged so the score reflects sustained leadership rather
than a single recent pop.
"""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

from app.core import config


def _window_return(close: pd.Series, window: int) -> Optional[float]:
    s = close.dropna()
    if len(s) <= window:
        return None
    start = float(s.iloc[-window - 1])
    end = float(s.iloc[-1])
    if start <= 0:
        return None
    return (end - start) / start


def rs_score(
    stock_df: pd.DataFrame,
    index_df: Optional[pd.DataFrame],
    windows: Optional[List[int]] = None,
) -> float:
    """
    Average outperformance of the stock vs the index across `windows`,
    mapped to a 0–100 score. Returns RS_NEUTRAL when the index is unavailable.
    """
    if index_df is None or index_df.empty or stock_df is None or stock_df.empty:
        return config.RS_NEUTRAL

    windows = windows or config.RS_LOOKBACK_WINDOWS
    stock_close = stock_df["Close"]
    index_close = index_df["Close"]

    diffs: List[float] = []
    for w in windows:
        sr = _window_return(stock_close, w)
        ir = _window_return(index_close, w)
        if sr is None or ir is None:
            continue
        diffs.append(sr - ir)

    if not diffs:
        return config.RS_NEUTRAL

    avg_outperf = sum(diffs) / len(diffs)
    # ±RS_RETURN_SCALE outperformance over a window maps to ~90 / ~10
    score = 50.0 + (avg_outperf / config.RS_RETURN_SCALE) * 40.0
    return float(max(0.0, min(100.0, score)))
