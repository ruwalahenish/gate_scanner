"""
Celery tasks for GATE scan execution.
Runs in a separate worker process — imports gate_scanner engines directly.
"""
import asyncio
import json
import time
from uuid import UUID

import structlog
from app.tasks.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(bind=True, max_retries=2, name="app.tasks.scanner_tasks.run_scan_task")
def run_scan_task(self, scan_id: str, universe: list[str], mode: str = "daily"):
    """
    Execute the 5-stage GATE pipeline and persist results to NeonDB.
    Called from POST /api/scans/trigger.
    """
    try:
        asyncio.run(_run_scan_async(scan_id, universe, mode))
    except Exception as exc:
        log.error("scan_task_failed", scan_id=scan_id, error=str(exc))
        asyncio.run(_mark_scan_failed(scan_id, str(exc)))
        raise self.retry(exc=exc, countdown=30)


async def _run_scan_async(scan_id: str, universe: list[str], mode: str):
    import redis.asyncio as aioredis
    from app.config import get_settings
    from app.services.engine_adapter import run_scan_async
    from app.db import create_pool, close_pool
    from app.queries.scans import update_scan_status
    from app.queries.signals import insert_signals_batch

    settings = get_settings()
    db_pool = await create_pool()
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)

    sid = UUID(scan_id)
    t0 = time.perf_counter()

    try:
        # Broadcast scan started
        await redis.publish("scan:progress", json.dumps({
            "type": "scan.started",
            "payload": {"scan_id": scan_id},
            "timestamp": _now(),
        }))

        results = await run_scan_async(universe, mode)
        duration = time.perf_counter() - t0

        async with db_pool.acquire() as conn:
            count = await insert_signals_batch(conn, sid, results)
            await update_scan_status(
                conn, sid, "done",
                signals_found=count,
                duration_sec=round(duration, 2),
            )

        # Broadcast complete
        top = [r.get("signal") or {} for r in results[:5] if r.get("signal")]
        await redis.publish("scan:complete", json.dumps({
            "type": "scan.complete",
            "payload": {"scan_id": scan_id, "signals_count": len(results), "top_signals": top},
            "timestamp": _now(),
        }))
        log.info("scan_completed", scan_id=scan_id, signals=len(results), duration=round(duration, 1))

    finally:
        await close_pool()
        await redis.aclose()


async def _mark_scan_failed(scan_id: str, error: str):
    from app.db import create_pool, close_pool
    from app.queries.scans import update_scan_status
    db_pool = await create_pool()
    async with db_pool.acquire() as conn:
        await update_scan_status(conn, UUID(scan_id), "failed", error_message=error)
    await close_pool()


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


@celery_app.task(name="app.tasks.scanner_tasks.run_scheduled_scan")
def run_scheduled_scan(universe: list[str], mode: str = "daily"):
    """Scheduled daily scan — triggered by Celery Beat at 4:05 PM IST."""
    import asyncio
    from uuid import uuid4
    from app.db import create_pool, close_pool
    from app.queries.scans import create_scan

    async def _create_and_run():
        db_pool = await create_pool()
        scan_id = uuid4()
        async with db_pool.acquire() as conn:
            await create_scan(conn, scan_id, mode)
        await close_pool()
        run_scan_task.delay(str(scan_id), universe, mode)

    asyncio.run(_create_and_run())
