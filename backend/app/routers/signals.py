import json
from fastapi import APIRouter, Depends, Query, HTTPException
import asyncpg

from app.dependencies import db_conn
from app.queries.signals import get_latest_signals, get_signal_history
from app.services.scan_service import analyze_symbol_async, fetch_ohlcv_async

router = APIRouter(tags=["signals"])


@router.get("")
async def list_signals(
    category: str | None = None,
    min_rank: float = Query(0, ge=0, le=100),
    min_gate: float = Query(0, ge=0, le=100),
    side: str | None = None,
    timeframe: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn: asyncpg.Connection = Depends(db_conn),
):
    rows, total = await get_latest_signals(
        conn,
        category=category,
        min_rank=min_rank,
        min_gate=min_gate,
        side=side,
        timeframe=timeframe,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "items": [_serialize(r) for r in rows],
    }


@router.get("/{symbol}/history")
async def signal_history(
    symbol: str,
    limit: int = Query(30, ge=1, le=100),
    conn: asyncpg.Connection = Depends(db_conn),
):
    rows = await get_signal_history(conn, symbol.upper(), limit)
    return [_serialize(r) for r in rows]


@router.get("/{symbol}/analysis")
async def symbol_analysis(symbol: str):
    """
    Run live MTF analysis for a symbol using the GATE engine.
    Expensive — ~5s. Cached by RTK Query for 5 minutes on the frontend.
    """
    try:
        result = await analyze_symbol_async(symbol.upper())
        return result
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Analysis failed: {str(e)}")


@router.get("/{symbol}/chart-data")
async def chart_data(
    symbol: str,
    timeframe: str = Query("1d", regex="^(1m|5m|15m|30m|60m|4h|1d|1wk|1mo)$"),
):
    """Return OHLCV + EMA data for TradingView chart rendering."""
    try:
        data = await fetch_ohlcv_async(symbol.upper(), timeframe)
        return {"symbol": symbol.upper(), "timeframe": timeframe, "bars": data}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Data fetch failed: {str(e)}")


_JSONB_COLS = {"trailing_plan"}


def _serialize(row) -> dict:
    d = dict(row)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
        elif type(v).__name__ == "UUID":
            d[k] = str(v)
        elif type(v).__name__ == "Decimal":
            d[k] = float(v)
        elif k in _JSONB_COLS and isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                pass
    return d
