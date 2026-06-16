"""
Internal task-trigger endpoints — called by cron-job.org to replace Celery Beat.

All endpoints require:  Authorization: Bearer <INTERNAL_SECRET>

Tasks run directly as FastAPI BackgroundTasks (no Celery broker / Redis required).
The Celery worker has been removed from supervisord.conf to eliminate BRPOP polling
that was consuming ~518k Redis requests/month (exceeding the Upstash free-tier limit).
"""
import asyncpg
import logging
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from app.config import get_settings

router = APIRouter()
_log = logging.getLogger(__name__)


def _require_auth(authorization: str | None) -> None:
    secret = get_settings().internal_secret
    if not secret:
        raise HTTPException(status_code=403, detail="Internal endpoints disabled: INTERNAL_SECRET not set")
    if authorization != f"Bearer {secret}":
        raise HTTPException(status_code=403, detail="Invalid token")


async def _run_daily_scan_direct(universe: list[str], mode: str) -> None:
    """Create a scan record then run the GATE pipeline directly (no Celery)."""
    from uuid import uuid4
    from app.queries.scans import create_scan
    from app.tasks.scanner_tasks import _run_scan_async

    settings = get_settings()
    # Create the scan row in its own short-lived pool so _run_scan_async
    # can open a fresh pool independently without touching the FastAPI global pool.
    pool = await asyncpg.create_pool(
        dsn=settings.database_url, min_size=1, max_size=2,
        command_timeout=30, statement_cache_size=0,
    )
    scan_id = uuid4()
    try:
        async with pool.acquire() as conn:
            await create_scan(conn, scan_id, mode)
    finally:
        await pool.close()

    await _run_scan_async(str(scan_id), universe, mode)


# ── Daily post-market scan — 16:05 IST Mon–Fri (10:35 UTC Mon–Fri) ──────────
@router.post("/tasks/daily-scan")
async def trigger_daily_scan(
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
):
    _require_auth(authorization)
    background_tasks.add_task(_run_daily_scan_direct, [], "daily")
    _log.info("internal: daily-scan queued as background task")
    return {"queued": "daily-scan"}


# ── Weekly stock master sync — 06:00 IST Sunday (00:30 UTC Sunday) ──────────
@router.post("/tasks/stock-sync")
async def trigger_stock_sync(
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
):
    _require_auth(authorization)
    from app.tasks.stock_tasks import _sync_async
    background_tasks.add_task(_sync_async, ["equity", "index_flags"])
    _log.info("internal: stock-sync queued as background task")
    return {"queued": "stock-sync"}


# ── Fundamentals enrichment — every 15 min ───────────────────────────────────
@router.post("/tasks/fundamentals")
async def trigger_fundamentals(
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
):
    _require_auth(authorization)
    from app.tasks.stock_tasks import _sync_async
    background_tasks.add_task(_sync_async, ["fundamentals"])
    _log.info("internal: fundamentals queued as background task")
    return {"queued": "fundamentals"}


# ── Paper trade monitor — every 5 min during market hours ────────────────────
@router.post("/tasks/monitor-trades")
async def trigger_monitor_trades(
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
):
    _require_auth(authorization)
    from app.tasks.trading_tasks import _monitor_async
    background_tasks.add_task(_monitor_async)
    _log.info("internal: monitor-trades queued as background task")
    return {"queued": "monitor-trades"}


# ── Live price broadcast — every 2 min during market hours ───────────────────
@router.post("/tasks/broadcast-prices")
async def trigger_broadcast_prices(
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
):
    _require_auth(authorization)
    from app.tasks.trading_tasks import _broadcast_prices_async
    background_tasks.add_task(_broadcast_prices_async)
    _log.info("internal: broadcast-prices queued as background task")
    return {"queued": "broadcast-prices"}
