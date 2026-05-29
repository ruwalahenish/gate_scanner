"""
Wraps the existing gate_scanner Python engines in async thread-pool calls.
All CPU-bound engine work runs in a ThreadPoolExecutor to avoid blocking
the FastAPI event loop.
"""
import asyncio
import sys
import os
from concurrent.futures import ThreadPoolExecutor
from app.config import get_settings

# Add gate_scanner parent to path so imports resolve
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_settings = get_settings()
_executor = ThreadPoolExecutor(max_workers=_settings.scan_executor_workers)


def _run_scan_sync(universe: list[str], mode: str) -> list[dict]:
    """Run the 5-stage GATE pipeline synchronously (called in thread pool)."""
    # Import here so the module path is set before import
    from gate_scanner.main import run_scan
    return run_scan(universe=universe if universe else None, mode=mode)


async def run_scan_async(universe: list[str], mode: str = "daily") -> list[dict]:
    """Async wrapper: runs GATE scan in thread pool, returns list of result dicts."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _run_scan_sync, universe, mode)


def _analyze_symbol_sync(symbol: str, timeframes: list[str]) -> dict:
    from gate_scanner.data_fetcher import get_multi_timeframe
    from gate_scanner.multi_timeframe import analyze_timeframe, mtf_summary
    from gate_scanner.signal_engine import generate_signal

    data = get_multi_timeframe(symbol, timeframes)
    per_tf = {
        tf: analyze_timeframe(data[tf], tf, symbol)
        for tf in timeframes
        if tf in data and not data[tf].empty
    }
    summary = mtf_summary(per_tf)
    signal = generate_signal(symbol, data, per_tf, summary)
    return {
        "symbol": symbol,
        "per_tf": per_tf,
        "summary": summary,
        "signal": signal,
    }


async def analyze_symbol_async(symbol: str, timeframes: list[str] | None = None) -> dict:
    """Async wrapper: runs MTF analysis for a single symbol."""
    from gate_scanner.config import TIMEFRAMES
    tfs = timeframes or ["60m", "4h", "1d", "1wk", "1mo"]
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _analyze_symbol_sync, symbol, tfs)


def _fetch_ohlcv_sync(symbol: str, timeframe: str) -> list[dict]:
    from gate_scanner.data_fetcher import get_multi_timeframe
    from gate_scanner.indicators import add_emas
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


def _isnan(v) -> bool:
    import math
    try:
        return math.isnan(float(v))
    except Exception:
        return True


async def fetch_ohlcv_async(symbol: str, timeframe: str = "1d") -> list[dict]:
    """Fetch OHLCV + EMA data for charting."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _fetch_ohlcv_sync, symbol, timeframe)
