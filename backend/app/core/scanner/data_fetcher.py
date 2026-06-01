"""
data_fetcher.py
================
Pulls OHLCV bars for NSE symbols across multiple timeframes.
Primary source: yfinance (works for Indian stocks via the `.NS` suffix).
Falls back gracefully on errors. Caches to disk to avoid re-hitting the API.

NOTE: For production-grade intraday data, swap `_fetch_yf` with Upstox/NSE.
The Fetcher API stays the same — only `_fetch_yf` needs to change.

Timeframe notes:
  * "4h"  — synthesized by resampling 60m bars (BUG-3 fix)
  * "3m"  — yfinance provides up to 7 days of 3m data
  * "1m"  — yfinance provides up to 7 days of 1m data
"""

from __future__ import annotations

import os
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from app.core import config

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
except ImportError:
    yf = None
    logger.warning("yfinance not installed; data fetching will fail.")


CACHE_DIR = Path(os.environ.get("GATE_CACHE_DIR", "./.gate_cache"))
CACHE_DIR.mkdir(exist_ok=True)

# Tiered TTL: intraday data stales fast; EOD/weekly/monthly data can be cached longer.
_INTRADAY_TFS = {"1m", "3m", "5m", "15m", "30m", "60m", "4h"}
_CACHE_TTL_INTRADAY = 3_600       # 1 hour
_CACHE_TTL_DAILY    = 86_400      # 24 hours — daily, weekly, monthly bars change only EOD


def _cache_ttl(interval: str) -> int:
    return _CACHE_TTL_INTRADAY if interval in _INTRADAY_TFS else _CACHE_TTL_DAILY

# yfinance interval strings — maps our internal TF names to what yfinance accepts
_YF_INTERVAL_MAP = {
    "1m":  "1m",
    "3m":  "3m",
    "5m":  "5m",
    "15m": "15m",
    "30m": "30m",
    "60m": "60m",
    "4h":  None,   # synthesized from 60m; no direct yfinance equivalent
    "1d":  "1d",
    "1wk": "1wk",
    "1mo": "1mo",
}


def _cache_path(symbol: str, interval: str) -> Path:
    safe = symbol.replace("/", "_").replace("&", "and")
    return CACHE_DIR / f"{safe}__{interval}.parquet"


def _read_cache(symbol: str, interval: str) -> Optional[pd.DataFrame]:
    path = _cache_path(symbol, interval)
    if not path.exists():
        return None
    if (time.time() - path.stat().st_mtime) > _cache_ttl(interval):
        return None
    try:
        return pd.read_parquet(path)
    except Exception as e:
        logger.debug("Cache read failed for %s %s: %s", symbol, interval, e)
        return None


def _write_cache(df: pd.DataFrame, symbol: str, interval: str) -> None:
    try:
        df.to_parquet(_cache_path(symbol, interval))
    except Exception as e:
        logger.debug("Cache write failed for %s %s: %s", symbol, interval, e)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure columns are Open/High/Low/Close/Volume, index is DatetimeIndex."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    rename = {c: c.title() for c in df.columns}
    df = df.rename(columns=rename)
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required - set(df.columns)
    if missing:
        return pd.DataFrame()
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    df.index = pd.to_datetime(df.index)
    return df


def _fetch_yf(symbol: str, interval: str, period: str) -> pd.DataFrame:
    if yf is None:
        return pd.DataFrame()
    yf_interval = _YF_INTERVAL_MAP.get(interval, interval)
    if yf_interval is None:
        return pd.DataFrame()
    yf_sym = config.yf_symbol(symbol)
    try:
        df = yf.download(
            yf_sym,
            interval=yf_interval,
            period=period,
            progress=False,
            auto_adjust=True,
            threads=False,
        )
        return _normalize(df)
    except Exception as e:
        logger.warning("yfinance fetch failed for %s @ %s: %s", symbol, interval, e)
        return pd.DataFrame()


def synthesize_4h_from_1h(df_1h: pd.DataFrame) -> pd.DataFrame:
    """yfinance doesn't expose 4h directly — resample from 60m (BUG-3 fix)."""
    if df_1h.empty:
        return df_1h
    agg = {
        "Open":   "first",
        "High":   "max",
        "Low":    "min",
        "Close":  "last",
        "Volume": "sum",
    }
    return df_1h.resample("4h").agg(agg).dropna()


def get_ohlcv(
    symbol: str,
    interval: str = "1d",
    period: Optional[str] = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Fetch OHLCV for a single symbol/interval.
    `period` defaults to config.TIMEFRAME_HISTORY[interval].

    For interval="4h", the data is synthesized from 60m bars automatically.
    """
    # 4h is synthesized — delegate to the 60m fetch + resample
    if interval == "4h":
        df_1h = get_ohlcv(symbol, interval="60m", period=period, use_cache=use_cache)
        df_4h = synthesize_4h_from_1h(df_1h)
        if use_cache and not df_4h.empty:
            _write_cache(df_4h, symbol, "4h")
        return df_4h

    period = period or config.TIMEFRAME_HISTORY.get(interval, "1y")
    if use_cache:
        cached = _read_cache(symbol, interval)
        if cached is not None and not cached.empty:
            return cached
    df = _fetch_yf(symbol, interval, period)
    if not df.empty and use_cache:
        _write_cache(df, symbol, interval)
    return df


def get_multi_timeframe(
    symbol: str,
    intervals: Optional[List[str]] = None,
    use_cache: bool = True,
) -> Dict[str, pd.DataFrame]:
    """
    Fetch a symbol across multiple timeframes.
    Returns dict { interval: DataFrame }.  Empty frames are kept so caller can
    detect missing data.

    BUG-3 fix: "4h" is now handled automatically via synthesize_4h_from_1h.
    MISS-4 fix: "1m" and "3m" are now included in TIMEFRAME_ORDER and supported.
    """
    intervals = intervals or config.TIMEFRAME_ORDER
    out: Dict[str, pd.DataFrame] = {}
    for tf in intervals:
        out[tf] = get_ohlcv(symbol, interval=tf, use_cache=use_cache)
    return out


def get_bulk_history(
    symbols: List[str],
    interval: str = "1d",
    start: str = "2020-01-01",
    end: Optional[str] = None,
    workers: int = 4,
) -> Dict[str, pd.DataFrame]:
    """
    Fetch long history for a list of symbols — optimised for backtesting.

    Uses yfinance bulk download (single HTTP request for all symbols) then
    splits the result per symbol. Falls back to per-symbol fetches on error.

    Parameters
    ----------
    symbols  : list of NSE tickers (without .NS suffix)
    interval : yfinance interval string, e.g. "1d"
    start    : ISO date string "YYYY-MM-DD"
    end      : ISO date string (None = today)
    workers  : thread workers for the per-symbol fallback path

    Returns
    -------
    Dict[str, pd.DataFrame]  symbol -> OHLCV DataFrame
    """
    import concurrent.futures as cf

    if yf is None:
        return {}

    yf_syms = [config.yf_symbol(s) for s in symbols]
    yf_interval = _YF_INTERVAL_MAP.get(interval, interval)
    if yf_interval is None:
        logger.warning("get_bulk_history: interval %s has no yfinance equivalent", interval)
        return {}

    result: Dict[str, pd.DataFrame] = {}

    try:
        raw = yf.download(
            yf_syms,
            interval=yf_interval,
            start=start,
            end=end,
            progress=False,
            auto_adjust=True,
            threads=True,
            group_by="ticker",
        )
        if raw.empty:
            raise ValueError("empty bulk download")

        for sym, yf_sym in zip(symbols, yf_syms):
            try:
                if len(yf_syms) == 1:
                    df = _normalize(raw)
                else:
                    df = _normalize(raw[yf_sym])
                if not df.empty:
                    result[sym] = df
            except Exception:
                pass

        if len(result) >= len(symbols) * 0.8:
            return result
    except Exception as e:
        logger.warning("Bulk download failed (%s) — falling back to per-symbol fetch", e)

    # Per-symbol fallback
    def _fetch_one(sym):
        yf_sym = config.yf_symbol(sym)
        try:
            df = yf.download(
                yf_sym,
                interval=yf_interval,
                start=start,
                end=end,
                progress=False,
                auto_adjust=True,
                threads=False,
            )
            return sym, _normalize(df)
        except Exception as exc:
            logger.debug("Fallback fetch failed for %s: %s", sym, exc)
            return sym, pd.DataFrame()

    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        for sym, df in pool.map(_fetch_one, symbols):
            if not df.empty:
                result[sym] = df

    return result
