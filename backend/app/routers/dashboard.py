"""
dashboard.py
============
Unified dashboard endpoint — returns all platform stats in a single call.
Response is cached in Redis for 60 seconds (busted on scan completion).
"""
from __future__ import annotations

import json

import asyncpg
import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Response

from app.config import get_settings
from app.db import get_read_pool
from app.redis_client import get_redis
from app.utils.display import enrich_signal_display
from app.utils.serialization import serialize_row

log = structlog.get_logger()
router = APIRouter(tags=["dashboard"])

_CACHE_KEY = "dashboard:stats"


# ---------------------------------------------------------------------------
# Public endpoint
# ---------------------------------------------------------------------------

@router.get("")
async def get_dashboard(response: Response):
    """
    Single-call dashboard payload:
      scanner      — latest scan stats + signal counts
      watchlist    — counts by status
      recent_opportunities — top 5 BUY signals from latest scan
      system_health        — DB / Redis / last scan duration
    """
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    redis: aioredis.Redis | None = None
    try:
        redis = get_redis()
        cached = await redis.get(_CACHE_KEY)
        if cached:
            return json.loads(cached)
    except Exception as exc:
        # Redis unavailable — fall through to DB
        log.warning("dashboard_cache_read_failed", error=str(exc))

    try:
        pool = get_read_pool()
        async with pool.acquire(timeout=10) as conn:
            result = await _build(conn, redis)
    except Exception as exc:
        log.warning("dashboard_build_failed", error=str(exc))
        return _empty_dashboard()

    try:
        if redis is not None:
            await redis.set(
                _CACHE_KEY, json.dumps(result, default=str), ex=get_settings().dashboard_cache_ttl
            )
    except Exception as exc:
        log.warning("dashboard_cache_write_failed", error=str(exc))

    return result


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

async def _build(conn: asyncpg.Connection, redis: aioredis.Redis) -> dict:
    # ── Latest scan ────────────────────────────────────────────────────────
    latest_scan = await conn.fetchrow(
        "SELECT * FROM scans WHERE status='done' ORDER BY triggered_at DESC LIMIT 1"
    )

    scanner_stats: dict = {
        "last_scan_at": None,
        "last_scan_duration_sec": None,
        "total_signals": 0,
        "buy_count": 0,
        "watch_count": 0,
        "no_action_count": 0,
    }
    recent_opportunities: list = []

    if latest_scan:
        scanner_stats["last_scan_at"] = latest_scan["triggered_at"].isoformat()
        scanner_stats["last_scan_duration_sec"] = (
            float(latest_scan["duration_sec"]) if latest_scan["duration_sec"] else None
        )
        scan_id = latest_scan["id"]

        counts = await conn.fetchrow(
            """SELECT
                 COUNT(*)                                                         AS total,
                 COUNT(*) FILTER (WHERE category IN ('INVESTMENT','SWING','POSITIONAL')) AS buy_count,
                 COUNT(*) FILTER (WHERE category = 'WATCH')                      AS watch_count,
                 COUNT(*) FILTER (WHERE category = 'IGNORE')                     AS no_action_count
               FROM signals WHERE scan_id=$1""",
            scan_id,
        )
        if counts:
            scanner_stats["total_signals"]   = counts["total"] or 0
            scanner_stats["buy_count"]       = counts["buy_count"] or 0
            scanner_stats["watch_count"]     = counts["watch_count"] or 0
            scanner_stats["no_action_count"] = counts["no_action_count"] or 0

        opp_rows = await conn.fetch(
            """SELECT s.symbol, s.category, s.signal_timeframe, s.entry,
                      s.stop_loss, s.t1, s.rr_t1, s.gate_strength,
                      s.confidence, s.rank_score,
                      sm.company_name, sm.sector
               FROM signals s
               LEFT JOIN stock_master sm ON s.symbol=sm.symbol AND sm.exchange='NSE'
               WHERE s.scan_id=$1
                 AND s.category IN ('INVESTMENT','SWING','POSITIONAL')
               ORDER BY s.rank_score DESC NULLS LAST
               LIMIT 5""",
            scan_id,
        )
        recent_opportunities = [enrich_signal_display(serialize_row(r)) for r in opp_rows]

    # ── System health ──────────────────────────────────────────────────────
    redis_ok = False
    try:
        await redis.ping()
        redis_ok = True
    except Exception as exc:
        log.debug("dashboard_redis_ping_failed", error=str(exc))

    system_health = {
        "db_ok":                True,  # we are connected if we reached here
        "redis_ok":             redis_ok,
        "last_scan_duration_sec": scanner_stats["last_scan_duration_sec"],
    }

    return {
        "scanner":               scanner_stats,
        "recent_opportunities":  recent_opportunities,
        "system_health":         system_health,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_dashboard() -> dict:
    return {
        "scanner": {
            "last_scan_at": None, "last_scan_duration_sec": None,
            "total_signals": 0, "buy_count": 0, "watch_count": 0, "no_action_count": 0,
        },
        "recent_opportunities": [],
        "system_health": {"db_ok": False, "redis_ok": False, "last_scan_duration_sec": None},
    }
