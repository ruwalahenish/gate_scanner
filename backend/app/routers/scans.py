import asyncio
import hashlib
import json
from uuid import uuid4, UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
import asyncpg

from app.config import get_settings
from app.dependencies import db_conn, redis_client
from app.limiter import limiter
from app.utils.display import enrich_signal_display
from app.utils.serialization import serialize_row
from app.models.scan import TriggerScanRequest, TriggerScanResponse, ScanStatus
from app.queries.scans import create_scan, get_scan, list_scans, has_running_scan, update_scan_status
from app.queries.signals import get_latest_signals
from app.tasks.scanner_tasks import run_scan_task
import redis.asyncio as aioredis


class ScanScheduleUpdate(BaseModel):
    enabled: bool | None = None
    cron_expression: str | None = None
    mode: str | None = None

router = APIRouter(tags=["scans"])

SCAN_LOCK_KEY = "scan:running"
SCAN_LOCK_TTL = 600  # 10 minutes

_SIGNALS_CACHE_PREFIX = "signals:list"


def _signals_cache_key(status, category, min_rank, min_gate, side, timeframe, limit, offset) -> str:
    raw = f"{status}:{category}:{min_rank}:{min_gate}:{side}:{timeframe}:{limit}:{offset}"
    return f"{_SIGNALS_CACHE_PREFIX}:{hashlib.md5(raw.encode()).hexdigest()}"


@router.get("", response_model=list[ScanStatus])
async def get_scans(
    limit: int = 20,
    offset: int = 0,
    conn: asyncpg.Connection = Depends(db_conn),
):
    rows = await list_scans(conn, limit, offset)
    return [dict(r) for r in rows]


@router.post("/trigger", response_model=TriggerScanResponse)
@limiter.limit("5/minute")
async def trigger_scan(
    request: Request,
    body: TriggerScanRequest,
    conn: asyncpg.Connection = Depends(db_conn),
    redis: aioredis.Redis = Depends(redis_client),
):
    # Prevent concurrent scans via Redis lock (skip gracefully if Redis unavailable)
    try:
        locked = await redis.set(SCAN_LOCK_KEY, "1", nx=True, ex=SCAN_LOCK_TTL)
        if not locked:
            actually_running = await has_running_scan(conn)
            if not actually_running:
                await redis.delete(SCAN_LOCK_KEY)
                locked = await redis.set(SCAN_LOCK_KEY, "1", nx=True, ex=SCAN_LOCK_TTL)
            if not locked:
                raise HTTPException(status_code=409, detail="A scan is already in progress. Try again later.")
    except HTTPException:
        raise
    except Exception:
        pass  # Redis unavailable — skip distributed lock

    scan_id = uuid4()
    await create_scan(conn, scan_id, body.mode)

    try:
        run_scan_task.apply_async(
            args=[str(scan_id), body.universe, body.mode],
            queue="scans",
        )
    except Exception:
        from app.tasks.scanner_tasks import _run_scan_async
        asyncio.create_task(_run_scan_async(str(scan_id), body.universe, body.mode))

    return TriggerScanResponse(scan_id=str(scan_id))


@router.get("/latest/signals")
async def get_latest_signals_endpoint(
    status: str | None = Query(None, pattern="^(BUY|WATCH|NO_ACTION)$"),
    min_rank: float = Query(0, ge=0, le=100),
    min_gate: float = Query(0, ge=0, le=100),
    side: str | None = None,
    timeframe: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn: asyncpg.Connection = Depends(db_conn),
    redis: aioredis.Redis = Depends(redis_client),
):
    """Primary signals endpoint — returns latest scan results with business terminology."""
    # Map display status filter back to internal categories
    category_filter = None
    if status == "BUY":
        category_filter = None  # handled via post-filter below
    elif status == "WATCH":
        category_filter = "WATCH"
    elif status == "NO_ACTION":
        category_filter = "IGNORE"

    cache_key = _signals_cache_key(status, category_filter, min_rank, min_gate, side, timeframe, limit, offset)
    try:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    rows, total = await get_latest_signals(
        conn,
        category=category_filter,
        min_rank=min_rank,
        min_gate=min_gate,
        side=side,
        timeframe=timeframe,
        limit=limit if status != "BUY" else 200,
        offset=offset if status != "BUY" else 0,
    )

    items = [enrich_signal_display(serialize_row(r, _JSONB_COLS)) for r in rows]

    # BUY filter: keep INVESTMENT/SWING/POSITIONAL only
    if status == "BUY":
        items = [i for i in items if i["display_status"] == "BUY"]
        items = items[offset: offset + limit]
        total = len(items)

    result = {"total": total, "items": items}
    try:
        await redis.set(cache_key, json.dumps(result), ex=get_settings().signals_cache_ttl)
    except Exception:
        pass

    return result


@router.get("/{scan_id}/signals")
async def get_scan_signals(
    scan_id: UUID,
    status: str | None = Query(None, pattern="^(BUY|WATCH|NO_ACTION)$"),
    min_rank: float = Query(0, ge=0, le=100),
    min_gate: float = Query(0, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn: asyncpg.Connection = Depends(db_conn),
):
    """Signals for a specific scan run."""
    row = await get_scan(conn, scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    category_filter = None
    if status == "WATCH":
        category_filter = "WATCH"
    elif status == "NO_ACTION":
        category_filter = "IGNORE"

    rows, total = await get_latest_signals(
        conn,
        category=category_filter,
        min_rank=min_rank,
        min_gate=min_gate,
        limit=limit if status != "BUY" else 200,
        offset=offset if status != "BUY" else 0,
    )

    items = [enrich_signal_display(serialize_row(r, _JSONB_COLS)) for r in rows]
    if status == "BUY":
        items = [i for i in items if i["display_status"] == "BUY"]
        items = items[offset: offset + limit]
        total = len(items)

    return {"total": total, "items": items}


@router.get("/schedule")
async def get_scan_schedule(conn: asyncpg.Connection = Depends(db_conn)):
    """Return the current scan schedule configuration."""
    row = await conn.fetchrow("SELECT * FROM scan_schedule WHERE id=1")
    if not row:
        return {"enabled": True, "cron_expression": "0 16 * * 1-5", "mode": "nifty500"}
    return _serialize_schedule(row)


@router.put("/schedule")
async def update_scan_schedule(
    body: ScanScheduleUpdate,
    conn: asyncpg.Connection = Depends(db_conn),
):
    """Update scan schedule settings (cron expression, enabled flag, mode)."""
    updates = []
    params: list = []
    idx = 1
    if body.enabled is not None:
        updates.append(f"enabled=${idx}")
        params.append(body.enabled)
        idx += 1
    if body.cron_expression is not None:
        updates.append(f"cron_expression=${idx}")
        params.append(body.cron_expression)
        idx += 1
    if body.mode is not None:
        updates.append(f"mode=${idx}")
        params.append(body.mode)
        idx += 1

    if not updates:
        raise HTTPException(status_code=422, detail="No fields provided for update")

    updates.append("updated_at=NOW()")
    params.append(1)  # WHERE id=1
    await conn.execute(
        f"UPDATE scan_schedule SET {', '.join(updates)} WHERE id=${idx}",
        *params,
    )
    row = await conn.fetchrow("SELECT * FROM scan_schedule WHERE id=1")
    return _serialize_schedule(row)


@router.post("/{scan_id}/stop")
async def stop_scan(
    scan_id: UUID,
    conn: asyncpg.Connection = Depends(db_conn),
    redis: aioredis.Redis = Depends(redis_client),
):
    """Force-stop a running or stuck scan."""
    from datetime import datetime, timezone

    row = await get_scan(conn, scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    if row["status"] not in ("pending", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"Scan is already {row['status']} — nothing to stop",
        )

    # Mark as failed in DB
    await update_scan_status(conn, scan_id, "failed", error_message="Stopped by user")

    # Release distributed lock so new scans can start immediately
    try:
        await redis.delete(SCAN_LOCK_KEY)
    except Exception:
        pass

    # Broadcast scan.failed → WebSocket manager fans out to all clients
    try:
        await redis.publish("scan:progress", json.dumps({
            "type": "scan.failed",
            "payload": {"scan_id": str(scan_id), "error": "Stopped by user"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
    except Exception:
        pass

    # Bust dashboard cache
    try:
        await redis.delete("dashboard:stats")
    except Exception:
        pass

    return {"stopped": True, "scan_id": str(scan_id)}


@router.get("/{scan_id}", response_model=ScanStatus)
async def get_scan_status(
    scan_id: UUID,
    conn: asyncpg.Connection = Depends(db_conn),
):
    row = await get_scan(conn, scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")
    return dict(row)


_serialize_schedule = serialize_row

_JSONB_COLS = frozenset({"trailing_plan"})
