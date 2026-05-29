"""
Celery task for running the walk-forward backtester.
"""
import asyncio
import json
import time
from uuid import UUID

import structlog
from app.tasks.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(bind=True, max_retries=1, name="app.tasks.backtest_tasks.run_backtest_task")
def run_backtest_task(
    self, backtest_id: str, universe: list[str], start_date: str, end_date: str
):
    try:
        asyncio.run(_run_backtest_async(backtest_id, universe, start_date, end_date))
    except Exception as exc:
        log.error("backtest_failed", backtest_id=backtest_id, error=str(exc))
        asyncio.run(_mark_failed(backtest_id, str(exc)))
        raise self.retry(exc=exc, countdown=10)


async def _run_backtest_async(
    backtest_id: str, universe: list[str], start_date: str, end_date: str
):
    from app.db import create_pool, close_pool
    from app.config import get_settings
    import redis.asyncio as aioredis

    settings = get_settings()
    db_pool = await create_pool()
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    bid = UUID(backtest_id)
    t0 = time.perf_counter()

    try:
        # Run backtester in thread (CPU-bound)
        loop = asyncio.get_event_loop()
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as ex:
            result = await loop.run_in_executor(
                ex, _run_backtest_sync, universe, start_date, end_date
            )

        duration = time.perf_counter() - t0
        async with db_pool.acquire() as conn:
            await _persist_backtest(conn, bid, result)

        await redis.publish("scan:complete", json.dumps({
            "type": "backtest.complete",
            "payload": {"backtest_id": backtest_id},
            "timestamp": _now(),
        }))
        log.info("backtest_completed", backtest_id=backtest_id, duration=round(duration, 1))
    finally:
        await close_pool()
        await redis.aclose()


def _run_backtest_sync(universe: list[str], start_date: str, end_date: str) -> dict:
    from gate_scanner.backtester.engine import BacktestEngine
    engine = BacktestEngine(universe=universe, start_date=start_date, end_date=end_date)
    return engine.run()


async def _persist_backtest(conn, backtest_id: UUID, result: dict):
    metrics = result.get("metrics", {})
    await conn.execute(
        """UPDATE backtests SET
           status='done', completed_at=NOW(),
           final_equity=$2, total_trades=$3, winning_trades=$4,
           win_rate=$5, cagr=$6, sharpe_ratio=$7, max_drawdown=$8
           WHERE id=$1""",
        backtest_id,
        metrics.get("final_equity"),
        metrics.get("total_trades"),
        metrics.get("winning_trades"),
        metrics.get("win_rate"),
        metrics.get("cagr"),
        metrics.get("sharpe"),
        metrics.get("max_drawdown"),
    )


async def _mark_failed(backtest_id: str, error: str):
    from app.db import create_pool, close_pool
    db_pool = await create_pool()
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE backtests SET status='failed', completed_at=NOW() WHERE id=$1",
            UUID(backtest_id),
        )
    await close_pool()


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
