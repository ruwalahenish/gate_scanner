import asyncio
from uuid import uuid4, UUID
from fastapi import APIRouter, Depends, HTTPException
import asyncpg

from app.dependencies import db_conn, redis_client
from app.models.scan import TriggerScanRequest, TriggerScanResponse, ScanStatus
from app.queries.scans import create_scan, get_scan, list_scans
from app.tasks.scanner_tasks import run_scan_task
from app.exceptions import ScanInProgressError
import redis.asyncio as aioredis

router = APIRouter(tags=["scans"])

SCAN_LOCK_KEY = "scan:running"
SCAN_LOCK_TTL = 600  # 10 minutes


@router.get("", response_model=list[ScanStatus])
async def get_scans(
    limit: int = 20,
    offset: int = 0,
    conn: asyncpg.Connection = Depends(db_conn),
):
    rows = await list_scans(conn, limit, offset)
    return [dict(r) for r in rows]


@router.post("/trigger", response_model=TriggerScanResponse)
async def trigger_scan(
    body: TriggerScanRequest,
    conn: asyncpg.Connection = Depends(db_conn),
    redis: aioredis.Redis = Depends(redis_client),
):
    # Prevent concurrent scans via Redis lock (skip gracefully if Redis unavailable)
    try:
        locked = await redis.set(SCAN_LOCK_KEY, "1", nx=True, ex=SCAN_LOCK_TTL)
        if not locked:
            raise HTTPException(status_code=409, detail="A scan is already in progress. Try again later.")
    except HTTPException:
        raise
    except Exception:
        pass  # Redis unavailable — skip distributed lock

    scan_id = uuid4()
    await create_scan(conn, scan_id, body.mode)

    # Dispatch to Celery worker; fall back to asyncio background task if broker unavailable
    try:
        run_scan_task.delay(str(scan_id), body.universe, body.mode)
    except Exception:
        from app.tasks.scanner_tasks import _run_scan_async
        asyncio.create_task(_run_scan_async(str(scan_id), body.universe, body.mode))

    return TriggerScanResponse(scan_id=str(scan_id))


@router.get("/latest/signals")
async def get_latest_signals_redirect():
    """Shortcut: redirect to /signals with no scan_id filter."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/api/signals")


@router.get("/{scan_id}", response_model=ScanStatus)
async def get_scan_status(
    scan_id: UUID,
    conn: asyncpg.Connection = Depends(db_conn),
):
    row = await get_scan(conn, scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")
    return dict(row)
