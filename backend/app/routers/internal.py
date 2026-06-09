"""
Internal task-trigger endpoints — called by cron-job.org to replace Celery Beat.

All endpoints require:  Authorization: Bearer <INTERNAL_SECRET>

These are the equivalent of Celery Beat's beat_schedule entries.
cron-job.org (free, no credit card) calls these on the same schedule that
Beat used to fire them. The request wakes the sleeping container AND queues
the task in the Celery worker.
"""
from fastapi import APIRouter, Header, HTTPException

from app.config import get_settings

router = APIRouter()


def _require_auth(authorization: str | None) -> None:
    secret = get_settings().internal_secret
    if not secret:
        raise HTTPException(status_code=403, detail="Internal endpoints disabled: INTERNAL_SECRET not set")
    if authorization != f"Bearer {secret}":
        raise HTTPException(status_code=403, detail="Invalid token")


# ── Daily post-market scan — 16:05 IST Mon–Fri (10:35 UTC Mon–Fri) ──────────
@router.post("/tasks/daily-scan")
def trigger_daily_scan(authorization: str | None = Header(None)):
    _require_auth(authorization)
    from app.tasks.scanner_tasks import run_scheduled_scan
    run_scheduled_scan.apply_async(args=([], "daily"), queue="scans")
    return {"queued": "daily-scan"}


# ── Weekly stock master sync — 06:00 IST Sunday (00:30 UTC Sunday) ──────────
@router.post("/tasks/stock-sync")
def trigger_stock_sync(authorization: str | None = Header(None)):
    _require_auth(authorization)
    from app.tasks.stock_tasks import sync_stock_master
    sync_stock_master.apply_async(args=(["equity", "index_flags"],), queue="admin")
    return {"queued": "stock-sync"}


# ── Fundamentals enrichment — every 15 min ───────────────────────────────────
@router.post("/tasks/fundamentals")
def trigger_fundamentals(authorization: str | None = Header(None)):
    _require_auth(authorization)
    from app.tasks.stock_tasks import enrich_fundamentals_batch
    enrich_fundamentals_batch.apply_async(queue="admin")
    return {"queued": "fundamentals"}


# ── Paper trade monitor — every 5 min during market hours ────────────────────
@router.post("/tasks/monitor-trades")
def trigger_monitor_trades(authorization: str | None = Header(None)):
    _require_auth(authorization)
    from app.tasks.trading_tasks import monitor_paper_trades_task
    monitor_paper_trades_task.apply_async(queue="default")
    return {"queued": "monitor-trades"}


# ── Live price broadcast — every 5 min during market hours ───────────────────
@router.post("/tasks/broadcast-prices")
def trigger_broadcast_prices(authorization: str | None = Header(None)):
    _require_auth(authorization)
    from app.tasks.trading_tasks import broadcast_position_prices_task
    broadcast_position_prices_task.apply_async(queue="default")
    return {"queued": "broadcast-prices"}
