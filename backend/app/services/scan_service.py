"""
services/scan_service.py
=========================
Async service layer for the GATE scan pipeline.

Wraps CPU-bound (pandas/yfinance) engine work in a ThreadPoolExecutor to avoid
blocking the FastAPI event loop.

Progressive streaming
---------------------
`run_scan_async` accepts an `on_batch` async coroutine that is awaited after
each batch of symbols is ranked.  The pipeline thread calls back into the event
loop via `asyncio.run_coroutine_threadsafe`, allowing incremental DB writes and
Redis/WebSocket publishes without blocking the worker thread.
"""

import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor

from app.config import get_settings

_settings = get_settings()
_executor = ThreadPoolExecutor(max_workers=_settings.scan_executor_workers)


def _run_scan_sync(universe: list[str], mode: str, on_batch_sync=None) -> list[dict]:
    """Run the 5-stage GATE pipeline synchronously (called in thread pool)."""
    from app.core.scanner.pipeline import run_scan
    return run_scan(universe=universe if universe else None, on_batch=on_batch_sync)


async def _resolve_universe_from_db(mode: str) -> list[str]:
    """
    Query stock_master for the universe corresponding to a scan mode.
    Returns an empty list if stock_master is unpopulated or unavailable.
    """
    try:
        from app.db import get_pool
        from app.queries.stock_master import get_symbols_for_mode
        pool = get_pool()
        if pool is None:
            return []
        async with pool.acquire() as conn:
            symbols = await get_symbols_for_mode(conn, mode)
        if len(symbols) >= 10:
            return symbols
    except Exception:
        pass
    return []


async def run_scan_async(
    universe: list[str],
    mode: str = "daily",
    on_batch=None,
) -> list[dict]:
    """
    Async wrapper: runs GATE scan in thread pool, returns list of result dicts.

    Parameters
    ----------
    on_batch : async coroutine callable(batch: list, done: int, total: int)
               Awaited after each batch is ranked. May perform DB writes and
               Redis publishes.  Must not raise — wrap in try/except internally.
    """
    # If no explicit universe, resolve from stock_master first.
    # Falls back to get_full_universe() inside the pipeline if DB returns empty.
    if not universe:
        universe = await _resolve_universe_from_db(mode)

    loop = asyncio.get_event_loop()

    # Build a sync callback that bridges the thread-pool back to the event loop
    sync_cb = None
    if on_batch is not None:
        def sync_cb(batch: list, done: int, total: int):
            future = asyncio.run_coroutine_threadsafe(on_batch(batch, done, total), loop)
            try:
                future.result(timeout=30)  # wait for the async persist+publish to finish
            except Exception:
                pass  # never let a callback error abort the pipeline

    fn = functools.partial(_run_scan_sync, universe, mode, on_batch_sync=sync_cb)
    return await loop.run_in_executor(_executor, fn)


def _analyze_symbol_sync(symbol: str, timeframes: list[str]) -> dict:
    from app.core.scanner.data_fetcher import get_multi_timeframe
    from app.core.analysis.multi_timeframe import analyze_timeframe, mtf_summary
    from app.agents.risk_agent import RiskManagementAgent

    data = get_multi_timeframe(symbol, timeframes)
    per_tf = {
        tf: analyze_timeframe(data[tf], tf, symbol)
        for tf in timeframes
        if tf in data and not data[tf].empty
    }
    summary = mtf_summary(per_tf)
    signal = RiskManagementAgent().build_signal(symbol, data, per_tf, summary)
    return {
        "symbol": symbol,
        "per_tf": per_tf,
        "summary": summary,
        "signal": signal,
    }


async def analyze_symbol_async(symbol: str, timeframes: list[str] | None = None) -> dict:
    """Async wrapper: runs MTF analysis for a single symbol.
    Defaults to SCAN_TIMEFRAMES (daily strategy: 4h SL, 1d entry, 1wk confirm).
    """
    from app.core.config import SCAN_TIMEFRAMES
    tfs = timeframes or SCAN_TIMEFRAMES
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _analyze_symbol_sync, symbol, tfs)


def _isnan(v) -> bool:
    import math
    try:
        return math.isnan(float(v))
    except Exception:
        return True


def _fetch_ohlcv_sync(symbol: str, timeframe: str) -> list[dict]:
    from app.core.scanner.data_fetcher import get_multi_timeframe
    from app.core.analysis.indicators import add_emas
    data = get_multi_timeframe(symbol, [timeframe])
    df = data.get(timeframe)
    if df is None or df.empty:
        return []
    df = add_emas(df)
    df = df.dropna(subset=["Close"])
    records = []
    for ts, row in df.iterrows():
        t = int(ts.timestamp())
        records.append({
            "time": t,
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row.get("Volume", 0)),
            "ema20": round(float(row["EMA20"]), 2) if "EMA20" in row and not _isnan(row["EMA20"]) else None,
            "ema50": round(float(row["EMA50"]), 2) if "EMA50" in row and not _isnan(row["EMA50"]) else None,
            "ema100": round(float(row["EMA100"]), 2) if "EMA100" in row and not _isnan(row["EMA100"]) else None,
            "ema200": round(float(row["EMA200"]), 2) if "EMA200" in row and not _isnan(row["EMA200"]) else None,
        })
    return records


async def fetch_ohlcv_async(symbol: str, timeframe: str = "1d") -> list[dict]:
    """Fetch OHLCV + EMA data for charting."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _fetch_ohlcv_sync, symbol, timeframe)
