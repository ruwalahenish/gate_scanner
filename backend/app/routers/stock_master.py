from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Optional
from uuid import uuid4

import asyncpg
import redis.asyncio as aioredis
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.dependencies import db_conn, db_read_conn, redis_client
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
)
from app.utils.serialization import serialize_row

_log = logging.getLogger(__name__)

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
    conn: asyncpg.Connection = Depends(db_read_conn),
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
async def stats_endpoint(conn: asyncpg.Connection = Depends(db_read_conn)):
    return await get_stats(conn)


# ---------------------------------------------------------------------------
# Sync trigger (admin action)
# ---------------------------------------------------------------------------

async def _run_sync_direct(phases: list[str]) -> None:
    """Direct sync without Celery — used as fallback when Redis/Celery is unavailable."""
    from app.config import get_settings
    from app.services.stock_service import (
        sync_nse_equity_async,
        sync_bse_equity_async,
        sync_index_flags_async,
        enrich_fundamentals_async,
    )
    settings = get_settings()
    pool = await asyncpg.create_pool(
        dsn=settings.database_url, min_size=1, max_size=3, command_timeout=60
    )
    try:
        if "equity" in phases:
            async with pool.acquire() as conn:
                _log.info("direct_sync: equity started")
                result = await sync_nse_equity_async(conn)
                _log.info("direct_sync: equity done %s", result)
        if "bse_equity" in phases:
            async with pool.acquire() as conn:
                _log.info("direct_sync: bse_equity started")
                result = await sync_bse_equity_async(conn)
                _log.info("direct_sync: bse_equity done %s", result)
        if "index_flags" in phases:
            async with pool.acquire() as conn:
                _log.info("direct_sync: index_flags started")
                result = await sync_index_flags_async(conn)
                _log.info("direct_sync: index_flags done %s", result)
        if "fundamentals" in phases:
            _log.info("direct_sync: fundamentals started")
            while True:
                async with pool.acquire() as conn:
                    result = await enrich_fundamentals_async(conn, batch_size=50)
                _log.info("direct_sync: fundamentals batch %s", result)
                if result["processed"] == 0:
                    break
        _log.info("direct_sync: all phases complete %s", phases)
    except Exception:
        _log.exception("direct_sync_failed phases=%s", phases)
    finally:
        await pool.close()


@router.post("/sync/trigger", response_model=SyncTriggerResponse)
async def trigger_sync(
    body: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    redis: aioredis.Redis = Depends(redis_client),
):
    """Dispatch a Celery sync task for the requested phases.

    Falls back to direct in-process execution via FastAPI BackgroundTasks when
    Celery or Redis is unavailable (e.g. Upstash free-tier request limit hit).
    """
    valid_phases = {"equity", "bse_equity", "index_flags", "fundamentals"}
    bad = [p for p in body.phases if p not in valid_phases]
    if bad:
        raise HTTPException(status_code=422, detail=f"Unknown phases: {bad}")

    try:
        from app.tasks.stock_tasks import sync_stock_master
        task = sync_stock_master.delay(body.phases)

        # Best-effort Redis tracking — skip silently if Redis is rate-limited.
        try:
            await redis.set("stock_sync:current", json.dumps({
                "task_id":    str(task.id),
                "phases":     body.phases,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }), ex=7200)
            await redis.delete("stock_sync:progress")
            await redis.delete("stock_sync:phase")
        except Exception:
            pass

        return SyncTriggerResponse(task_id=str(task.id), phases=body.phases, status="queued")

    except Exception:
        # Celery unavailable — run sync directly inside the FastAPI process.
        task_id = str(uuid4())
        background_tasks.add_task(_run_sync_direct, body.phases)
        _log.warning("Celery unavailable — running stock sync directly (phases=%s)", body.phases)
        return SyncTriggerResponse(task_id=task_id, phases=body.phases, status="running_direct")


@router.get("/sync/status")
async def get_sync_status(redis: aioredis.Redis = Depends(redis_client)):
    """Return current sync task state + live fundamentals progress."""
    try:
        raw = await redis.get("stock_sync:current")
    except Exception:
        return {"is_running": False, "state": "redis_unavailable",
                "error": "Redis rate-limited — sync may still be running in background"}

    if not raw:
        return {"is_running": False, "state": "idle"}

    info = json.loads(raw)
    task_id = info["task_id"]

    try:
        from app.tasks.celery_app import celery_app
        cel_result = celery_app.AsyncResult(task_id)
        state = cel_result.state          # PENDING / STARTED / SUCCESS / FAILURE
        error = str(cel_result.result) if state == "FAILURE" else None
    except Exception:
        state = "UNKNOWN"
        error = None

    try:
        progress_raw  = await redis.get("stock_sync:progress")
        current_phase = await redis.get("stock_sync:phase")
    except Exception:
        progress_raw  = None
        current_phase = None

    # `stock_sync:phase` is set to "complete" or "failed" by the task when it
    # finishes — use this as the primary completion signal so the status endpoint
    # works correctly even when the Celery result backend is disabled.
    phase_str = (current_phase.decode() if isinstance(current_phase, bytes) else current_phase) or ""
    if phase_str in ("complete", "failed"):
        is_running = False
        if phase_str == "failed" and not error:
            error = "Sync failed — check worker logs"
    else:
        is_running = state in ("PENDING", "STARTED", "RETRY", "UNKNOWN")

    return {
        "is_running":    is_running,
        "task_id":       task_id,
        "phases":        info["phases"],
        "started_at":    info["started_at"],
        "state":         state,
        "current_phase": current_phase,
        "progress":      json.loads(progress_raw) if progress_raw else None,
        "error":         error,
    }


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
    conn: asyncpg.Connection = Depends(db_read_conn),
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
    conn: asyncpg.Connection = Depends(db_read_conn),
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
# Per-symbol backtest trigger
# ---------------------------------------------------------------------------

class SymbolBacktestRequest(BaseModel):
    investment_per_stock: float = Field(10_000, ge=5_000)
    start_date: Optional[date] = None   # defaults to 7 years ago


@router.post("/{symbol}/backtest")
async def trigger_symbol_backtest(
    symbol: str,
    body: SymbolBacktestRequest,
    conn: asyncpg.Connection = Depends(db_conn),
):
    """Queue a 7-year walk-forward backtest for a single stock."""
    sym = symbol.upper()
    start = body.start_date or (date.today() - timedelta(days=7 * 365))
    end = date.today()
    bt_id = uuid4()

    await conn.execute(
        """INSERT INTO backtests(id, started_at, universe, start_date, end_date,
               initial_capital, status, scope, investment_per_stock)
           VALUES($1, NOW(), $2, $3, $4, $5, 'pending', 'symbol', $6)""",
        bt_id, [sym], start, end, body.investment_per_stock, body.investment_per_stock,
    )

    from app.tasks.backtest_tasks import run_backtest_task
    task = run_backtest_task.apply_async(
        kwargs={
            "backtest_id": str(bt_id),
            "universe": [sym],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "initial_capital": body.investment_per_stock,
            "investment_per_stock": body.investment_per_stock,
        },
        queue="backtests",
    )
    await conn.execute("UPDATE backtests SET task_id=$2 WHERE id=$1", bt_id, str(task.id))
    return {"backtest_id": str(bt_id), "status": "pending"}


# ---------------------------------------------------------------------------
# Per-symbol backtest trade history
# ---------------------------------------------------------------------------

@router.get("/{symbol}/backtest-trades")
async def get_backtest_trades(
    symbol: str,
    limit: int = Query(50, ge=1, le=200),
    conn: asyncpg.Connection = Depends(db_read_conn),
):
    from app.routers.backtests import get_trades_for_symbol
    return await get_trades_for_symbol(conn, symbol.upper(), limit)


# ---------------------------------------------------------------------------
# Serialization helper (same pattern as signals.py, portfolio.py, etc.)
# ---------------------------------------------------------------------------

# Canonical implementation lives in app/utils/serialization.py
_serialize = serialize_row
