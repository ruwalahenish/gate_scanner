"""
Celery tasks for GATE scan execution.
Runs in a separate worker process — uses the backend scan_service layer.
"""
import asyncio
import sys
import time
import traceback
from uuid import UUID

import structlog
from app.tasks.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(
    bind=True,
    name="app.tasks.scanner_tasks.run_scan_task",
    max_retries=2,
    default_retry_delay=30,
    autoretry_for=(ConnectionError, TimeoutError),
    queue="scans",
)
def run_scan_task(self, scan_id: str, universe: list[str], mode: str = "daily"):
    """
    Execute the 5-stage GATE pipeline and persist results to NeonDB.
    Called from POST /api/scans/trigger.
    """
    # asyncpg requires SelectorEventLoop on Windows (Celery defaults to ProactorEventLoop)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(_run_scan_async(scan_id, universe, mode))
    except Exception as exc:
        tb = traceback.format_exc()
        log.error("scan_task_failed", scan_id=scan_id, error=str(exc), traceback=tb)
        raise


async def _run_scan_async(scan_id: str, universe: list[str], mode: str):
    import redis.asyncio as aioredis
    from app.config import get_settings
    from app.core.json_utils import CustomEncoder
    from app.services.scan_service import run_scan_async
    from app.db import create_pool, close_pool, get_pool
    from app.queries.scans import update_scan_status
    from app.queries.signals import insert_signals_batch
    import json

    settings = get_settings()
    db_pool = None
    redis = None
    try:
        db_pool = await create_pool()
        redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    except Exception as exc:
        log.error("scan_init_failed", scan_id=scan_id, error=str(exc))
        raise

    sid = UUID(scan_id)
    t0 = time.perf_counter()
    total_inserted = 0
    final_status = "failed"

    # Guarantee the scan row exists before the pipeline starts.
    # The router already inserts it, but NeonDB's serverless cold-start can create a
    # brief visibility gap when the Celery worker opens a brand-new connection pool.
    # ON CONFLICT DO NOTHING is idempotent — it's a no-op when the row already exists.
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO scans(id, mode, status) VALUES($1, $2, 'pending') "
            "ON CONFLICT (id) DO NOTHING",
            sid, mode,
        )

    async def _publish(channel: str, payload: dict):
        try:
            await redis.publish(channel, json.dumps(payload, cls=CustomEncoder))
        except Exception:
            pass

    async def on_batch(batch: list, done: int, total: int):
        """Called after each batch of ranked symbols — insert to DB and broadcast."""
        nonlocal total_inserted
        try:
            async with db_pool.acquire() as conn:
                count = await insert_signals_batch(conn, sid, batch)
                total_inserted += count
        except Exception as e:
            log.warning("batch_insert_failed", scan_id=scan_id, error=str(e))

        # Serialize signals for WebSocket (strip bulky ohlcv DataFrames)
        ws_signals = _serialize_batch_for_ws(batch)

        await _publish("scan:batch", {
            "type": "scan.batch",
            "payload": {
                "scan_id": scan_id,
                "done": done,
                "total": total,
                "signals": ws_signals,
            },
            "timestamp": _now(),
        })
        await _publish("scan:progress", {
            "type": "scan.progress",
            "payload": {
                "scan_id": scan_id,
                "symbols_done": done,
                "symbols_total": total,
            },
            "timestamp": _now(),
        })

    try:
        await _publish("scan:progress", {
            "type": "scan.started",
            "payload": {"scan_id": scan_id},
            "timestamp": _now(),
        })

        await run_scan_async(universe, mode, on_batch=on_batch)
        duration = time.perf_counter() - t0
        final_status = "done"

        async with db_pool.acquire() as conn:
            await update_scan_status(
                conn, sid, "done",
                signals_found=total_inserted,
                duration_sec=round(duration, 2),
            )

        await _publish("scan:complete", {
            "type": "scan.complete",
            "payload": {"scan_id": scan_id, "signals_count": total_inserted},
            "timestamp": _now(),
        })
        # Bust the server-side signals list cache so the next request hits the DB
        try:
            keys = await redis.keys("signals:list:*")
            if keys:
                await redis.delete(*keys)
        except Exception:
            pass
        log.info("scan_completed", scan_id=scan_id, signals=total_inserted, duration=round(duration, 1))

        # ── Post-scan automation ─────────────────────────────────────────
        watch_added = 0
        trades_created = 0
        try:
            from app.services.automation_service import (
                auto_update_watchlist,
                auto_create_paper_trades,
            )
            async with db_pool.acquire() as conn:
                scan_signals = await conn.fetch(
                    "SELECT * FROM signals WHERE scan_id=$1", sid
                )
                signals_list = [dict(r) for r in scan_signals]
                # Normalise asyncpg Decimal/UUID types for automation functions
                signals_list = [
                    {k: (float(v) if hasattr(v, "__float__") and not isinstance(v, (int, float, bool)) else
                         str(v) if hasattr(v, "hex") else v)  # UUID → str
                     for k, v in row.items()}
                    for row in signals_list
                ]
                watch_added = await auto_update_watchlist(conn, signals_list)
                trades_created = await auto_create_paper_trades(conn, signals_list)

            await _publish("scan:post_process", {
                "type": "scan.post_process",
                "payload": {
                    "scan_id": scan_id,
                    "watch_added": watch_added,
                    "trades_created": trades_created,
                },
                "timestamp": _now(),
            })
            # Bust dashboard cache so next request reflects new data immediately
            try:
                await redis.delete("dashboard:stats")
            except Exception:
                pass
            log.info("post_scan_automation_done",
                     watch_added=watch_added, trades_created=trades_created)
        except Exception as exc:
            log.warning("post_scan_automation_failed", error=str(exc))

    except Exception as exc:
        await _publish("scan:progress", {
            "type": "scan.failed",
            "payload": {"scan_id": scan_id, "error": str(exc)},
            "timestamp": _now(),
        })
        raise

    finally:
        # Always update scan status (even if it was already set to done above)
        if final_status != "done":
            try:
                async with db_pool.acquire() as conn:
                    await update_scan_status(conn, sid, "failed")
            except Exception:
                pass

        if redis is not None:
            try:
                await redis.delete("scan:running")
            except Exception:
                pass
        await close_pool()
        if redis is not None:
            try:
                await redis.aclose()
            except Exception:
                pass


def _serialize_batch_for_ws(batch: list) -> list:
    """Strip DataFrames and return only JSON-serializable signal fields."""
    result = []
    for item in batch:
        signal = item.get("signal") or {}
        cls = item.get("classification") or {}
        rr = signal.get("rr") or {}
        if not signal and cls.get("category", "IGNORE") == "IGNORE":
            continue
        result.append({
            "symbol":               item.get("symbol"),
            "category":             cls.get("category", "IGNORE"),
            "side":                 signal.get("side"),
            "signal_timeframe":     signal.get("signal_timeframe"),
            "entry":                signal.get("entry"),
            "stop_loss":            signal.get("stop_loss"),
            "t1":                   signal.get("T1"),
            "t2":                   signal.get("T2"),
            "t3":                   signal.get("T3"),
            "rr_t1":                rr.get("T1"),
            "rr_t2":                rr.get("T2"),
            "gate_strength":        signal.get("gate_strength"),
            "confidence":           signal.get("confidence"),
            "rank_score":           signal.get("rank_score"),
            "htf_confirmed":        signal.get("htf_confirmed"),
        })
    return result


async def _mark_scan_failed(scan_id: str, error: str):
    from app.db import create_pool, close_pool
    from app.queries.scans import update_scan_status
    db_pool = await create_pool()
    try:
        async with db_pool.acquire() as conn:
            await update_scan_status(conn, UUID(scan_id), "failed", error_message=error)
    finally:
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
