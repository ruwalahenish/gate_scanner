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

from app.db import get_pool
from app.redis_client import get_redis
from app.services.price_service import get_bulk_prices

log = structlog.get_logger()
router = APIRouter(tags=["dashboard"])

_CACHE_KEY = "dashboard:stats"
_CACHE_TTL = 60  # seconds


# ---------------------------------------------------------------------------
# Public endpoint
# ---------------------------------------------------------------------------

@router.get("")
async def get_dashboard(response: Response):
    """
    Single-call dashboard payload:
      scanner      — latest scan stats + signal counts
      watchlist    — counts by status
      paper_trading — live P&L, open positions, trade stats
      backtesting  — total runs, best CAGR
      recent_opportunities — top 5 BUY signals from latest scan
      recent_trades        — last 5 closed paper trades
      system_health        — DB / Redis / last scan duration
    """
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    redis: aioredis.Redis | None = None
    try:
        redis = get_redis()
        cached = await redis.get(_CACHE_KEY)
        if cached:
            return json.loads(cached)
    except Exception:
        pass  # Redis unavailable — fall through to DB

    try:
        pool = get_pool()
        async with pool.acquire(timeout=10) as conn:
            result = await _build(conn, redis)
    except Exception as exc:
        log.warning("dashboard_build_failed", error=str(exc))
        return _empty_dashboard()

    try:
        if redis is not None:
            await redis.set(_CACHE_KEY, json.dumps(result, default=str), ex=_CACHE_TTL)
    except Exception:
        pass

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
        recent_opportunities = [_enrich(_serialize(r)) for r in opp_rows]

    # ── Watchlist ──────────────────────────────────────────────────────────
    wl_counts = await conn.fetchrow(
        """SELECT
             COUNT(*)                                           AS total,
             COUNT(*) FILTER (WHERE status='active')           AS active,
             COUNT(*) FILTER (WHERE status='buy_triggered')    AS buy_triggered,
             COUNT(*) FILTER (WHERE status='target_hit')       AS target_hit,
             COUNT(*) FILTER (WHERE status='sl_hit')           AS sl_hit,
             COUNT(*) FILTER (WHERE status='closed')           AS closed
           FROM watchlist"""
    )
    watchlist_stats = dict(wl_counts) if wl_counts else {
        "total": 0, "active": 0, "buy_triggered": 0,
        "target_hit": 0, "sl_hit": 0, "closed": 0,
    }

    # ── Paper trading ──────────────────────────────────────────────────────
    pt_config = await conn.fetchrow("SELECT * FROM portfolio_config LIMIT 1")
    pt_trade_stats = await conn.fetchrow(
        """SELECT
             COUNT(*) FILTER (WHERE pnl_abs IS NOT NULL) AS total_trades,
             COUNT(*) FILTER (WHERE pnl_abs > 0)         AS winning_trades,
             COALESCE(SUM(pnl_abs) FILTER (WHERE pnl_abs IS NOT NULL), 0) AS realized_pnl
           FROM trades"""
    )
    open_positions = await conn.fetch(
        "SELECT * FROM positions WHERE status IN ('open','partially_closed')"
    )

    unrealized_pnl = 0.0
    if open_positions:
        symbols = list({p["symbol"] for p in open_positions})
        try:
            prices = await get_bulk_prices(symbols, redis)
            unrealized_pnl = sum(
                (prices.get(p["symbol"], float(p["avg_entry"])) - float(p["avg_entry"])) * p["quantity"]
                for p in open_positions
            )
        except Exception:
            pass

    total_trades = (pt_trade_stats["total_trades"] or 0) if pt_trade_stats else 0
    winning_trades = (pt_trade_stats["winning_trades"] or 0) if pt_trade_stats else 0
    realized_pnl = float((pt_trade_stats["realized_pnl"] or 0)) if pt_trade_stats else 0.0

    paper_trading_stats = {
        "open_positions":  len(open_positions),
        "total_trades":    total_trades,
        "winning_trades":  winning_trades,
        "win_rate":        round((winning_trades / total_trades) * 100, 1) if total_trades else 0.0,
        "realized_pnl":    round(realized_pnl, 2),
        "unrealized_pnl":  round(unrealized_pnl, 2),
        "total_pnl":       round(realized_pnl + unrealized_pnl, 2),
        "current_capital": float(pt_config["current_capital"]) if pt_config else 0.0,
    }

    # ── Recent trades ──────────────────────────────────────────────────────
    recent_trade_rows = await conn.fetch(
        """SELECT symbol, side, quantity, price, executed_at, exit_reason, pnl_abs, pnl_pct
           FROM trades WHERE pnl_abs IS NOT NULL
           ORDER BY executed_at DESC LIMIT 5"""
    )
    recent_trades = [_serialize(r) for r in recent_trade_rows]

    # ── Backtesting ────────────────────────────────────────────────────────
    bt_stats_row = await conn.fetchrow(
        """SELECT
             COUNT(*)              AS total_runs,
             MAX(started_at)       AS last_run_at,
             MAX(cagr)             AS best_cagr,
             MAX(win_rate)         AS best_win_rate
           FROM backtests WHERE status='done'"""
    )
    backtesting_stats = {
        "total_runs":    int(bt_stats_row["total_runs"] or 0) if bt_stats_row else 0,
        "last_run_at":   bt_stats_row["last_run_at"].isoformat() if bt_stats_row and bt_stats_row["last_run_at"] else None,
        "best_cagr":     round(float(bt_stats_row["best_cagr"] or 0), 2) if bt_stats_row else 0.0,
        "best_win_rate": round(float(bt_stats_row["best_win_rate"] or 0), 1) if bt_stats_row else 0.0,
    }

    # ── System health ──────────────────────────────────────────────────────
    redis_ok = False
    try:
        await redis.ping()
        redis_ok = True
    except Exception:
        pass

    system_health = {
        "db_ok":                True,  # we are connected if we reached here
        "redis_ok":             redis_ok,
        "last_scan_duration_sec": scanner_stats["last_scan_duration_sec"],
    }

    return {
        "scanner":               scanner_stats,
        "watchlist":             watchlist_stats,
        "paper_trading":         paper_trading_stats,
        "backtesting":           backtesting_stats,
        "recent_opportunities":  recent_opportunities,
        "recent_trades":         recent_trades,
        "system_health":         system_health,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DISPLAY_STATUS = {
    "INVESTMENT": "BUY",
    "SWING":      "BUY",
    "POSITIONAL": "BUY",
    "WATCH":      "WATCH",
    "IGNORE":     "NO_ACTION",
}

_DISPLAY_CATEGORY = {
    "INVESTMENT": "Long-Term Buy",
    "SWING":      "Swing Buy",
    "POSITIONAL": "Positional Buy",
    "WATCH":      "Watch",
    "IGNORE":     "No Action",
}


def _enrich(d: dict) -> dict:
    cat = d.get("category", "IGNORE")
    d["display_status"] = _DISPLAY_STATUS.get(cat, "NO_ACTION")
    d["display_category"] = _DISPLAY_CATEGORY.get(cat, "No Action")
    return d


def _empty_dashboard() -> dict:
    return {
        "scanner": {
            "last_scan_at": None, "last_scan_duration_sec": None,
            "total_signals": 0, "buy_count": 0, "watch_count": 0, "no_action_count": 0,
        },
        "watchlist": {
            "total": 0, "active": 0, "buy_triggered": 0,
            "target_hit": 0, "sl_hit": 0, "closed": 0,
        },
        "paper_trading": {
            "open_positions": 0, "total_trades": 0, "winning_trades": 0,
            "win_rate": 0.0, "realized_pnl": 0.0, "unrealized_pnl": 0.0,
            "total_pnl": 0.0, "current_capital": 0.0,
        },
        "backtesting": {
            "total_runs": 0, "last_run_at": None, "best_cagr": 0.0, "best_win_rate": 0.0,
        },
        "recent_opportunities": [],
        "recent_trades": [],
        "system_health": {"db_ok": False, "redis_ok": False, "last_scan_duration_sec": None},
    }


def _serialize(row) -> dict:
    d = dict(row)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
        elif type(v).__name__ == "UUID":
            d[k] = str(v)
        elif type(v).__name__ == "Decimal":
            d[k] = float(v)
    return d
