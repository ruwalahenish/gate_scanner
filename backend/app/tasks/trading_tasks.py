"""
Celery tasks for continuous paper trade lifecycle management.

Two periodic tasks (both registered in beat_schedule):
  - monitor_paper_trades_task  (every 5 min) — checks SL/target hits and auto-exits positions
  - broadcast_position_prices_task (every 2 min) — pushes live prices to WebSocket clients

Both tasks are no-ops outside IST market hours (9:15–15:30, weekdays).
"""
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone, time as dtime

import structlog

from app.tasks.celery_app import celery_app

log = structlog.get_logger()

_IST = timezone(timedelta(hours=5, minutes=30))


def _is_market_open() -> bool:
    now = datetime.now(_IST)
    if now.weekday() >= 5:
        return False
    t = now.time()
    return dtime(9, 15) <= t <= dtime(15, 30)


# ---------------------------------------------------------------------------
# Task 1: monitor open positions for SL / target hits
# ---------------------------------------------------------------------------

@celery_app.task(
    name="app.tasks.trading_tasks.monitor_paper_trades_task",
    queue="default",
)
def monitor_paper_trades_task():
    """Auto-exit paper positions when SL or target is hit. No-op outside market hours."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_monitor_async())


async def _monitor_async():
    import asyncpg
    import redis.asyncio as aioredis
    from app.config import get_settings
    from app.services.automation_service import auto_exit_positions
    from app.services.ws_manager import make_event

    if not _is_market_open():
        log.info("monitor_paper_trades_skipped", reason="market_closed")
        return

    settings = get_settings()
    db_pool = None
    redis = None
    try:
        db_pool = await asyncpg.create_pool(
            dsn=settings.database_url, min_size=1, max_size=3,
            command_timeout=30, statement_cache_size=0,
        )
        redis = aioredis.from_url(settings.redis_url, decode_responses=True)

        async with db_pool.acquire() as conn:
            closed = await auto_exit_positions(conn, redis)

        log.info("monitor_paper_trades_done", positions_closed=closed)

        if closed > 0:
            event = make_event("trade.monitor", {"positions_closed": closed})
            await redis.publish("scan:post_process", json.dumps(event))

    except Exception as exc:
        log.error("monitor_paper_trades_failed", error=str(exc))
    finally:
        if db_pool is not None:
            await db_pool.close()
        if redis is not None:
            try:
                await redis.aclose()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Task 2: broadcast live prices for all open positions
# ---------------------------------------------------------------------------

@celery_app.task(
    name="app.tasks.trading_tasks.broadcast_position_prices_task",
    queue="default",
)
def broadcast_position_prices_task():
    """Publish live prices for open paper positions to the price:update WebSocket channel."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_broadcast_prices_async())


async def _broadcast_prices_async():
    import asyncpg
    import redis.asyncio as aioredis
    from app.config import get_settings
    from app.services.price_service import get_bulk_prices
    from app.services.ws_manager import make_event

    if not _is_market_open():
        log.info("broadcast_position_prices_skipped", reason="market_closed")
        return

    settings = get_settings()
    db_pool = None
    redis = None
    try:
        db_pool = await asyncpg.create_pool(
            dsn=settings.database_url, min_size=1, max_size=3,
            command_timeout=30, statement_cache_size=0,
        )
        redis = aioredis.from_url(settings.redis_url, decode_responses=True)

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT symbol FROM positions WHERE status IN ('open', 'partially_closed')"
            )

        if not rows:
            log.info("broadcast_position_prices_done", symbols=0)
            return

        symbols = [r["symbol"] for r in rows]
        prices = await get_bulk_prices(symbols, redis)

        for symbol, price in prices.items():
            if price is not None:
                event = make_event("price.update", {"symbol": symbol, "price": price})
                await redis.publish("price:update", json.dumps(event))

        log.info("broadcast_position_prices_done", symbols=len(prices))

    except Exception as exc:
        log.error("broadcast_position_prices_failed", error=str(exc))
    finally:
        if db_pool is not None:
            await db_pool.close()
        if redis is not None:
            try:
                await redis.aclose()
            except Exception:
                pass
