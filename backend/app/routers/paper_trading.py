from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
import asyncpg

from app.dependencies import db_conn, redis_client
from app.limiter import limiter
from app.models.paper_trading import SellRequest, PaperTradingSummary
from app.queries import portfolio as q
from app.services.portfolio_service import execute_sell
from app.services.price_service import get_bulk_prices
from app.exceptions import PositionNotFoundError
from app.utils.serialization import serialize_row
import redis.asyncio as aioredis

router = APIRouter(tags=["paper_trading"])


class CapitalUpdate(BaseModel):
    amount: float = Field(..., gt=0, description="New capital amount in INR")


@router.get("/summary", response_model=PaperTradingSummary)
async def get_summary(
    conn: asyncpg.Connection = Depends(db_conn),
    redis: aioredis.Redis = Depends(redis_client),
):
    summary = await q.get_portfolio_summary(conn)
    positions = await q.get_open_positions(conn)
    if positions:
        symbols = list({p["symbol"] for p in positions})
        try:
            prices = await get_bulk_prices(symbols, redis)
        except Exception:
            prices = {}
        unrealized = sum(
            (prices.get(p["symbol"], p["avg_entry"]) - float(p["avg_entry"])) * p["quantity"]
            for p in positions
        )
        summary["unrealized_pnl"] = round(unrealized, 2)
    return summary


@router.get("/positions")
async def get_positions(
    conn: asyncpg.Connection = Depends(db_conn),
    redis: aioredis.Redis = Depends(redis_client),
):
    positions = await q.get_open_positions(conn)
    if not positions:
        return []
    symbols = list({p["symbol"] for p in positions})
    try:
        prices = await get_bulk_prices(symbols, redis)
    except Exception:
        prices = {}

    result = []
    for p in positions:
        d = _serialize(p)
        current = prices.get(p["symbol"])
        if current:
            entry = float(p["avg_entry"])
            pnl_abs = (current - entry) * p["quantity"]
            d["current_price"] = current
            d["unrealized_pnl"] = round(pnl_abs, 2)
            d["unrealized_pnl_pct"] = round((current - entry) / entry * 100, 2)
        result.append(d)
    return result


@router.get("/trades")
async def get_trades(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn: asyncpg.Connection = Depends(db_conn),
):
    rows, total = await q.get_trade_history(conn, limit, offset)
    return {"total": total, "items": [_serialize(r) for r in rows]}


@router.post("/sell")
@limiter.limit("30/minute")
async def sell(
    request: Request,
    body: SellRequest,
    conn: asyncpg.Connection = Depends(db_conn),
):
    """Manual sell override — auto-exits are handled by automation_service."""
    try:
        result = await execute_sell(
            conn,
            UUID(body.position_id),
            body.quantity,
            body.price,
            exit_reason=body.exit_reason,
            notes=body.notes,
        )
        return result
    except PositionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/capital")
@limiter.limit("10/minute")
async def set_capital(
    request: Request,
    body: CapitalUpdate,
    conn: asyncpg.Connection = Depends(db_conn),
):
    await q.reset_capital(conn, body.amount)
    return {"updated": True, "amount": body.amount}


@router.put("/positions/{position_id}/sl")
async def update_sl(
    position_id: UUID,
    sl: float = Query(..., gt=0, description="New stop-loss price (must be positive)"),
    level: str = "manual",
    conn: asyncpg.Connection = Depends(db_conn),
):
    pos = await q.get_position(conn, position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    await q.update_trailing_sl(conn, position_id, sl, level)
    return {"updated": True, "trailing_sl": sl}


@router.get("/performance")
async def get_performance(
    conn: asyncpg.Connection = Depends(db_conn),
    redis: aioredis.Redis = Depends(redis_client),
):
    """
    Extended paper-trading performance metrics: win rate, trade stats,
    P&L breakdown, and live unrealized P&L from current prices.
    """
    config = await q.get_portfolio_config(conn)
    if config is None:
        return _empty_performance()

    trade_stats = await conn.fetchrow(
        """SELECT
             COUNT(*) FILTER (WHERE pnl_abs IS NOT NULL)           AS total_trades,
             COUNT(*) FILTER (WHERE pnl_abs > 0)                   AS winning_trades,
             COUNT(*) FILTER (WHERE pnl_abs < 0)                   AS losing_trades,
             COALESCE(SUM(pnl_abs) FILTER (WHERE pnl_abs IS NOT NULL), 0) AS realized_pnl,
             COALESCE(AVG(pnl_pct) FILTER (WHERE pnl_pct > 0), 0) AS avg_win_pct,
             COALESCE(AVG(pnl_pct) FILTER (WHERE pnl_pct < 0), 0) AS avg_loss_pct,
             COALESCE(MAX(pnl_pct), 0)                             AS best_trade_pct,
             COALESCE(MIN(pnl_pct), 0)                             AS worst_trade_pct
           FROM trades"""
    )

    positions = await q.get_open_positions(conn)
    unrealized = 0.0
    if positions:
        symbols = list({p["symbol"] for p in positions})
        try:
            prices = await get_bulk_prices(symbols, redis)
        except Exception:
            prices = {}
        unrealized = sum(
            (prices.get(p["symbol"], float(p["avg_entry"])) - float(p["avg_entry"])) * p["quantity"]
            for p in positions
        )

    initial = float(config["initial_capital"])
    current = float(config["current_capital"])
    realized = float(trade_stats["realized_pnl"] or 0)
    total_pnl = current - initial + realized + unrealized
    total_trades = trade_stats["total_trades"] or 0
    winning = trade_stats["winning_trades"] or 0

    return {
        "initial_capital":  initial,
        "current_capital":  current,
        "invested_value":   sum(float(p["avg_entry"]) * p["quantity"] for p in positions),
        "unrealized_pnl":   round(unrealized, 2),
        "realized_pnl":     round(realized, 2),
        "total_pnl":        round(total_pnl, 2),
        "total_pnl_pct":    round((total_pnl / initial) * 100, 2) if initial else 0.0,
        "open_positions":   len(positions),
        "total_trades":     total_trades,
        "winning_trades":   winning,
        "losing_trades":    trade_stats["losing_trades"] or 0,
        "win_rate":         round((winning / total_trades) * 100, 1) if total_trades else 0.0,
        "avg_win_pct":      round(float(trade_stats["avg_win_pct"] or 0), 2),
        "avg_loss_pct":     round(float(trade_stats["avg_loss_pct"] or 0), 2),
        "best_trade_pct":   round(float(trade_stats["best_trade_pct"] or 0), 2),
        "worst_trade_pct":  round(float(trade_stats["worst_trade_pct"] or 0), 2),
    }


def _empty_performance() -> dict:
    return {
        "initial_capital": 0.0, "current_capital": 0.0, "invested_value": 0.0,
        "unrealized_pnl": 0.0, "realized_pnl": 0.0, "total_pnl": 0.0,
        "total_pnl_pct": 0.0, "open_positions": 0, "total_trades": 0,
        "winning_trades": 0, "losing_trades": 0, "win_rate": 0.0,
        "avg_win_pct": 0.0, "avg_loss_pct": 0.0,
        "best_trade_pct": 0.0, "worst_trade_pct": 0.0,
    }


# Canonical implementation lives in app/utils/serialization.py
_serialize = serialize_row
