"""
sector_engine.py
================
Per-sector momentum from the NSE sectoral indices.

`compute_sector_momentum()` fetches each sectoral index (daily) once per scan and
maps its trailing return to a 0–100 momentum score (50 = neutral). The result is a
{sector_name: score} map keyed by the same sector names used in
nse_universe.SECTOR_MAP, so a scanned symbol's sector momentum is a dict lookup.

Sectors whose index can't be fetched fall back to SECTOR_NEUTRAL.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, Optional

import pandas as pd

from app.core import config

logger = logging.getLogger(__name__)

# NSE sector name (matches nse_universe.SECTOR_MAP values) → Yahoo index symbol
SECTOR_INDEX_SYMBOLS: Dict[str, str] = {
    "Banking":        "^NSEBANK",
    "IT":             "^CNXIT",
    "Pharma":         "^CNXPHARMA",
    "Auto":           "^CNXAUTO",
    "FMCG":           "^CNXFMCG",
    "Metal":          "^CNXMETAL",
    "Energy":         "^CNXENERGY",
    "Realty":         "^CNXREALTY",
    "Infrastructure": "^CNXINFRA",
}


def _momentum_from_return(ret: float) -> float:
    """±SECTOR_RETURN_SCALE return over the lookback maps to ~90 / ~10."""
    score = 50.0 + (ret / config.SECTOR_RETURN_SCALE) * 40.0
    return float(max(0.0, min(100.0, score)))


def _trailing_return(df: pd.DataFrame, lookback: int) -> Optional[float]:
    close = df["Close"].dropna()
    if len(close) <= lookback:
        return None
    start = float(close.iloc[-lookback - 1])
    end = float(close.iloc[-1])
    if start <= 0:
        return None
    return (end - start) / start


def compute_sector_momentum(
    fetch_fn: Optional[Callable[[str], pd.DataFrame]] = None,
) -> Dict[str, float]:
    """
    Build {sector_name: momentum_score 0–100}. `fetch_fn(symbol) -> daily df`
    defaults to data_fetcher.get_ohlcv(symbol, "1d"). Failures degrade to neutral.
    """
    if fetch_fn is None:
        from app.core.scanner import data_fetcher

        def fetch_fn(sym: str) -> pd.DataFrame:  # type: ignore[misc]
            return data_fetcher.get_ohlcv(sym, interval="1d")

    out: Dict[str, float] = {}
    for sector, index_sym in SECTOR_INDEX_SYMBOLS.items():
        try:
            df = fetch_fn(index_sym)
            ret = _trailing_return(df, config.SECTOR_MOMENTUM_LOOKBACK) if df is not None else None
            out[sector] = _momentum_from_return(ret) if ret is not None else config.SECTOR_NEUTRAL
        except Exception as e:
            logger.debug("sector momentum fetch failed for %s (%s): %s", sector, index_sym, e)
            out[sector] = config.SECTOR_NEUTRAL
    return out
