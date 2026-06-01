"""
stock_tasks.py
==============
Celery tasks for stock_master sync operations.

Follows the exact structure of scanner_tasks.py:
  - Outer sync Celery task calls asyncio.run()
  - Inner async function creates its own local asyncpg pool
    (same pattern as backtest_tasks._run_backtest_async)
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

    phases: list of any subset of ['equity', 'index_flags', 'fundamentals']
            None = run all three in order
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(_sync_async(phases or ["equity", "index_flags", "fundamentals"]))
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
    (same pattern as _run_backtest_async in backtest_tasks.py).
    """
    import asyncpg
    from app.config import get_settings
    from app.services.stock_service import (
        sync_nse_equity_async,
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
    try:
        if "equity" in phases:
            async with local_pool.acquire() as conn:
                result = await sync_nse_equity_async(conn)
                log.info("stock_master_equity_sync_done", **result)

        if "index_flags" in phases:
            async with local_pool.acquire() as conn:
                result = await sync_index_flags_async(conn)
                log.info("stock_master_index_flags_done", **result)

        if "fundamentals" in phases:
            async with local_pool.acquire() as conn:
                result = await enrich_fundamentals_async(conn, batch_size=50)
                log.info("stock_master_fundamentals_done", **result)

    finally:
        await local_pool.close()
