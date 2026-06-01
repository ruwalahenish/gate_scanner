from __future__ import annotations

from typing import Annotated, Optional

import asyncpg
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import db_conn, redis_client
from app.services.price_service import get_bulk_prices
from app.models.stock import (
    StockListResponse,
    StockResponse,
    StockSearchResult,
    SyncTriggerRequest,
    SyncTriggerResponse,
)
from app.queries.stock_master import (
    get_stats,
    get_stock,
    list_stocks_with_signals,
    search_stocks,
    _index_filter_to_column,
)

router = APIRouter(tags=["stock_master"])

_VALID_INDEX_FILTERS = {
    "nifty50", "nifty_next50", "nifty100", "nifty500",
    "midcap150", "smallcap100", "fno",
}


# ---------------------------------------------------------------------------
# Search (must come before /{symbol}/* to avoid route shadowing)
# ---------------------------------------------------------------------------

@router.get("/search", response_model=list[StockSearchResult])
async def search_endpoint(
    q: Annotated[str, Query(min_length=1, max_length=50)],
    limit: int = Query(20, ge=1, le=50),
    exchange: Optional[str] = None,
    index_filter: Optional[str] = None,
    sector: Optional[str] = None,
    conn: asyncpg.Connection = Depends(db_conn),
):
    if index_filter and index_filter not in _VALID_INDEX_FILTERS:
        raise HTTPException(status_code=422, detail=f"Invalid index_filter: {index_filter}")
    rows = await search_stocks(conn, q, limit=limit, exchange=exchange,
                               index_filter=index_filter, sector=sector)
    return [_serialize(r) for r in rows]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
async def stats_endpoint(conn: asyncpg.Connection = Depends(db_conn)):
    return await get_stats(conn)


# ---------------------------------------------------------------------------
# Sync trigger (admin action)
# ---------------------------------------------------------------------------

@router.post("/sync/trigger", response_model=SyncTriggerResponse)
async def trigger_sync(body: SyncTriggerRequest):
    """Dispatch a Celery sync task for the requested phases."""
    valid_phases = {"equity", "index_flags", "fundamentals"}
    bad = [p for p in body.phases if p not in valid_phases]
    if bad:
        raise HTTPException(status_code=422, detail=f"Unknown phases: {bad}")

    try:
        from app.tasks.stock_tasks import sync_stock_master
        task = sync_stock_master.delay(body.phases)
        return SyncTriggerResponse(task_id=str(task.id), phases=body.phases, status="queued")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Celery unavailable: {e}")


# ---------------------------------------------------------------------------
# List (paginated, enriched with latest signal data)
# ---------------------------------------------------------------------------

@router.get("", response_model=StockListResponse)
async def list_stocks_endpoint(
    exchange: Optional[str] = None,
    index_filter: Optional[str] = None,
    sector: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn: asyncpg.Connection = Depends(db_conn),
    redis: aioredis.Redis = Depends(redis_client),
):
    if index_filter and index_filter not in _VALID_INDEX_FILTERS:
        raise HTTPException(status_code=422, detail=f"Invalid index_filter: {index_filter}")
    rows, total = await list_stocks_with_signals(
        conn, exchange=exchange, index_filter=index_filter,
        sector=sector, category=category, limit=limit, offset=offset,
    )
    items = [_serialize(r) for r in rows]

    # Fetch live prices for all symbols in this page and embed them
    symbols = [item["symbol"] for item in items]
    if symbols:
        prices = await get_bulk_prices(symbols, redis)
        for item in items:
            item["live_price"] = prices.get(item["symbol"])

    return StockListResponse(total=total, items=items)


# ---------------------------------------------------------------------------
# Single stock detail
# ---------------------------------------------------------------------------

@router.get("/{symbol}", response_model=StockResponse)
async def get_stock_detail(
    symbol: str,
    exchange: str = "NSE",
    conn: asyncpg.Connection = Depends(db_conn),
):
    row = await get_stock(conn, symbol.upper(), exchange)
    if not row:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found in stock master")
    return _serialize(row)


# ---------------------------------------------------------------------------
# Per-symbol chart data (proxies scan_service.fetch_ohlcv_async)
# ---------------------------------------------------------------------------

@router.get("/{symbol}/chart-data")
async def get_chart_data(
    symbol: str,
    timeframe: str = Query("1d"),
):
    from app.services.scan_service import fetch_ohlcv_async
    try:
        bars = await fetch_ohlcv_async(symbol.upper(), timeframe)
        return {"symbol": symbol.upper(), "timeframe": timeframe, "bars": bars}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Chart data unavailable: {e}")


# ---------------------------------------------------------------------------
# Per-symbol live GATE analysis (~5s, expensive)
# ---------------------------------------------------------------------------

@router.get("/{symbol}/analysis")
async def get_analysis(symbol: str):
    from app.services.scan_service import analyze_symbol_async
    try:
        return await analyze_symbol_async(symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Analysis failed: {e}")


# ---------------------------------------------------------------------------
# Per-symbol backtest trade history
# ---------------------------------------------------------------------------

@router.get("/{symbol}/backtest-trades")
async def get_backtest_trades(
    symbol: str,
    limit: int = Query(50, ge=1, le=200),
    conn: asyncpg.Connection = Depends(db_conn),
):
    from app.routers.backtests import get_trades_for_symbol
    return await get_trades_for_symbol(conn, symbol.upper(), limit)


# ---------------------------------------------------------------------------
# Serialization helper (same pattern as signals.py, portfolio.py, etc.)
# ---------------------------------------------------------------------------

def _serialize(row) -> dict:
    d = dict(row)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
        elif type(v).__name__ == "Decimal":
            d[k] = float(v)
    return d
