import hashlib
import json

from fastapi import APIRouter, Depends, Query, HTTPException
import asyncpg
import redis.asyncio as aioredis

from app.dependencies import db_conn, redis_client
from app.queries.signals import get_latest_signals, get_signal_history
from app.services.scan_service import analyze_symbol_async, fetch_ohlcv_async

router = APIRouter(tags=["signals"])

# Server-side Redis cache for the filtered signals list (30 s TTL).
# Invalidated by scan_tasks.py when a scan completes (DEL signals:list:*).
_SIGNALS_CACHE_TTL = 30
_SIGNALS_CACHE_PREFIX = "signals:list"


def _cache_key(category, min_rank, min_gate, side, timeframe, limit, offset) -> str:
    raw = f"{category}:{min_rank}:{min_gate}:{side}:{timeframe}:{limit}:{offset}"
    return f"{_SIGNALS_CACHE_PREFIX}:{hashlib.md5(raw.encode()).hexdigest()}"


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
    redis: aioredis.Redis = Depends(redis_client),
):
    key = _cache_key(category, min_rank, min_gate, side, timeframe, limit, offset)

    # Try Redis cache first
    try:
        cached = await redis.get(key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass  # Redis unavailable — fall through to DB

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
    result = {"total": total, "items": [_serialize(r) for r in rows]}

    # Cache in Redis for 30 s
    try:
        await redis.set(key, json.dumps(result), ex=_SIGNALS_CACHE_TTL)
    except Exception:
        pass

    return result


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
    Run live MTF analysis — expensive (~5 s). Cached by RTK Query for 5 min client-side.
    """
    try:
        result = await analyze_symbol_async(symbol.upper())
        return result
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Analysis failed: {str(e)}")


@router.get("/{symbol}/chart-data")
async def chart_data(
    symbol: str,
    timeframe: str = Query("1d", pattern="^(1m|5m|15m|30m|60m|4h|1d|1wk|1mo)$"),
):
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
