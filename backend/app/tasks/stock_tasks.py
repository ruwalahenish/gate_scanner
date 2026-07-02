"""
stock_tasks.py
==============
Celery tasks for stock_master sync operations.

Follows the exact structure of scanner_tasks.py:
  - Outer sync Celery task calls asyncio.run()
  - Inner async function creates its own local asyncpg pool
    (same pattern used here — see _sync_async below)
  - Windows asyncio policy set before each asyncio.run()
"""
from __future__ import annotations

import asyncio
import sys

import structlog

from app.tasks.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(
    bind=True,
    name="app.tasks.stock_tasks.sync_stock_master",
    max_retries=2,
    default_retry_delay=120,
    autoretry_for=(ConnectionError, TimeoutError),
    queue="admin",
)
def sync_stock_master(self, phases: list[str] | None = None):
    """
    Full or partial sync of stock_master.

    phases: list of any subset of
            ['equity', 'bse_equity', 'index_flags', 'fundamentals']
            None = run all in order
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(_sync_async(
            phases or ["equity", "bse_equity", "index_flags", "fundamentals"]
        ))
    except Exception:
        log.exception("sync_stock_master_failed")
        raise


@celery_app.task(
    name="app.tasks.stock_tasks.enrich_fundamentals_batch",
    max_retries=1,
    default_retry_delay=60,
    queue="admin",
)
def enrich_fundamentals_batch():
    """
    Lightweight scheduled task: enrich the next 50 pending/failed rows.
    Runs every 15 minutes via Celery Beat until the queue is empty.
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(_sync_async(["fundamentals"]))
    except Exception:
        log.exception("enrich_fundamentals_batch_failed")
        raise


# ---------------------------------------------------------------------------
# Async implementation
# ---------------------------------------------------------------------------

async def _sync_async(phases: list[str]) -> None:
    """
    Creates its own local asyncpg pool independent of the FastAPI global pool
    (same pattern used throughout this module).
    """
    import json
    import asyncpg
    import redis.asyncio as aioredis
    from app.config import get_settings
    from app.services.stock_service import (
        sync_nse_equity_async,
        sync_bse_equity_async,
        sync_index_flags_async,
        enrich_fundamentals_async,
    )

    settings = get_settings()
    local_pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1,
        max_size=3,
        command_timeout=60,
    )
    redis = await aioredis.from_url(settings.redis_url, decode_responses=True)
    _TTL = 7200

    async def _set_phase(name: str) -> None:
        await redis.set("stock_sync:phase", name, ex=_TTL)

    try:
        if "equity" in phases:
            await _set_phase("equity")
            async with local_pool.acquire() as conn:
                result = await sync_nse_equity_async(conn)
                log.info("stock_master_equity_sync_done", **result)

        # BSE must run after NSE equity so dedup-by-ISIN sees NSE listings.
        if "bse_equity" in phases:
            await _set_phase("bse_equity")
            async with local_pool.acquire() as conn:
                result = await sync_bse_equity_async(conn)
                log.info("stock_master_bse_sync_done", **result)

        if "index_flags" in phases:
            await _set_phase("index_flags")
            async with local_pool.acquire() as conn:
                result = await sync_index_flags_async(conn)
                log.info("stock_master_index_flags_done", **result)

        if "fundamentals" in phases:
            await _set_phase("fundamentals")
            total_processed = total_succeeded = total_failed = 0
            while True:
                async with local_pool.acquire() as conn:
                    result = await enrich_fundamentals_async(conn, batch_size=50)
                total_processed += result["processed"]
                total_succeeded += result["succeeded"]
                total_failed    += result["failed"]
                await redis.set("stock_sync:progress", json.dumps({
                    "processed": total_processed,
                    "succeeded": total_succeeded,
                    "failed":    total_failed,
                }), ex=_TTL)
                log.info("stock_master_fundamentals_batch", **result)
                if result["processed"] == 0:
                    break
            log.info(
                "stock_master_fundamentals_done",
                processed=total_processed,
                succeeded=total_succeeded,
                failed=total_failed,
            )

        # Mark completion so get_sync_status can detect done state even when
        # the Celery result backend is disabled (task_ignore_result=True).
        await redis.set("stock_sync:phase", "complete", ex=_TTL)

    except Exception:
        try:
            await redis.set("stock_sync:phase", "failed", ex=_TTL)
        except Exception:
            pass
        raise

    finally:
        await redis.aclose()
        await local_pool.close()
