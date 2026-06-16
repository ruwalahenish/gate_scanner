"""
screener_tasks.py
=================
Celery task for weekly Screener.in fundamentals sync.

Runs every Sunday at 04:30 UTC (30 min before weekly-stock-master-sync).
Processes ALL active stocks in batches, updating extended fundamentals
(roce_actual, opm_latest, shareholding, CAGR, price, etc.) in stock_master.

Unlike enrich_fundamentals_batch (which only processes pending/failed rows
for basic yfinance enrichment), this task refreshes EVERY stock with richer
Screener.in data on a weekly cadence.
"""
from __future__ import annotations

import asyncio
import sys

import structlog

from app.tasks.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(
    bind=True,
    name="app.tasks.screener_tasks.sync_screener_fundamentals",
    max_retries=1,
    default_retry_delay=300,
    queue="admin",
)
def sync_screener_fundamentals(self, batch_size: int = 50):
    """
    Sync Screener.in fundamentals for all active NSE stocks.

    Args:
        batch_size: Stocks processed per DB transaction (default 50).
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(_sync_screener_async(batch_size=batch_size))
    except Exception:
        log.exception("sync_screener_fundamentals_failed")
        raise


async def _sync_screener_async(batch_size: int = 50) -> None:
    import asyncpg
    from app.config import get_settings
    from app.core.scanner.universe.screener_fetcher import fetch_company
    from app.queries.stock_master import update_screener_data, mark_sync_failed

    settings = get_settings()
    pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1,
        max_size=3,
        command_timeout=60,
    )

    try:
        # Fetch all active NSE symbols in one query
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT symbol, exchange
                FROM stock_master
                WHERE sync_status != 'delisted' AND exchange = 'NSE'
                ORDER BY symbol
                """
            )
        symbols = [dict(r) for r in rows]
        total   = len(symbols)
        log.info("screener_sync_started", total=total)

        succeeded = failed = 0

        for i, row in enumerate(symbols):
            symbol   = row["symbol"]
            exchange = row["exchange"]

            # fetch_company already sleeps 1.5–3.5s internally
            data = fetch_company(symbol)

            async with pool.acquire() as conn:
                if data:
                    await update_screener_data(conn, symbol, exchange, data)
                    succeeded += 1
                else:
                    await mark_sync_failed(
                        conn, symbol, exchange,
                        "screener_fetcher returned empty result"
                    )
                    failed += 1

            if (i + 1) % 100 == 0:
                log.info(
                    "screener_sync_progress",
                    processed=i + 1,
                    total=total,
                    succeeded=succeeded,
                    failed=failed,
                )

        log.info(
            "screener_sync_done",
            total=total,
            succeeded=succeeded,
            failed=failed,
        )

    finally:
        await pool.close()
