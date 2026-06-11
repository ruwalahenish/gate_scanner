from uuid import uuid4, UUID
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
import asyncpg

from app.dependencies import db_conn
from app.limiter import limiter
from app.tasks.backtest_tasks import run_backtest_task
from app.utils.serialization import serialize_row

router = APIRouter(tags=["backtests"])


class RunBacktestRequest(BaseModel):
    universe: list[str] = []
    start_date: date
    end_date: Optional[date] = None
    initial_capital: float = 1_000_000


@router.get("")
async def list_backtests(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    conn: asyncpg.Connection = Depends(db_conn),
):
    rows = await conn.fetch(
        "SELECT * FROM backtests ORDER BY started_at DESC LIMIT $1 OFFSET $2",
        limit, offset,
    )
    return [_serialize(r) for r in rows]


@router.post("/run")
@limiter.limit("2/minute")
async def run_backtest(
    request: Request,  # required by slowapi
    body: RunBacktestRequest,
    conn: asyncpg.Connection = Depends(db_conn),
):
    end = body.end_date or date.today()
    if end <= body.start_date:
        raise HTTPException(status_code=422, detail="end_date must be after start_date")

    bt_id = uuid4()
    await conn.execute(
        """INSERT INTO backtests(id, started_at, universe, start_date, end_date, initial_capital, status, scope)
           VALUES($1, NOW(), $2, $3, $4, $5, 'pending', 'portfolio')""",
        bt_id, body.universe, body.start_date, end, body.initial_capital,
    )
    task = run_backtest_task.apply_async(
        args=[str(bt_id), body.universe, body.start_date.isoformat(), end.isoformat(), body.initial_capital],
        queue="backtests",
    )
    await conn.execute("UPDATE backtests SET task_id=$2 WHERE id=$1", bt_id, str(task.id))
    return {"backtest_id": str(bt_id), "status": "pending"}


@router.post("/{backtest_id}/cancel")
async def cancel_backtest(
    backtest_id: UUID,
    conn: asyncpg.Connection = Depends(db_conn),
):
    row = await conn.fetchrow(
        "SELECT task_id, status FROM backtests WHERE id=$1", backtest_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Backtest not found")
    if row["status"] not in ("pending", "running"):
        raise HTTPException(status_code=409, detail=f"Backtest is already {row['status']}")

    if row["task_id"]:
        from app.tasks.celery_app import celery_app
        celery_app.control.revoke(row["task_id"], terminate=True, signal="SIGTERM")

    await conn.execute(
        "UPDATE backtests SET status='cancelled', completed_at=NOW() WHERE id=$1",
        backtest_id,
    )
    return {"status": "cancelled"}


@router.get("/{backtest_id}")
async def get_backtest(
    backtest_id: UUID,
    conn: asyncpg.Connection = Depends(db_conn),
):
    row = await conn.fetchrow("SELECT * FROM backtests WHERE id=$1", backtest_id)
    if not row:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return _serialize(row)


@router.get("/{backtest_id}/trades")
async def get_backtest_trades(
    backtest_id: UUID,
    symbol: Optional[str] = None,
    conn: asyncpg.Connection = Depends(db_conn),
):
    if symbol:
        rows = await conn.fetch(
            "SELECT * FROM backtest_trades WHERE backtest_id=$1 AND symbol=$2 ORDER BY entry_date",
            backtest_id, symbol.upper(),
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM backtest_trades WHERE backtest_id=$1 ORDER BY entry_date", backtest_id
        )
    return [_serialize(r) for r in rows]


@router.get("/{backtest_id}/stock-results")
async def get_stock_results(
    backtest_id: UUID,
    conn: asyncpg.Connection = Depends(db_conn),
):
    rows = await conn.fetch(
        """SELECT symbol, status, total_trades, winning_trades, win_rate,
                  total_pnl_abs, avg_pnl_pct, best_trade_pct, worst_trade_pct,
                  avg_holding_days, category, error_message, completed_at
           FROM backtest_stock_results
           WHERE backtest_id=$1
           ORDER BY total_pnl_abs DESC NULLS LAST""",
        backtest_id,
    )
    return [_serialize(r) for r in rows]


@router.get("/{backtest_id}/equity-curve")
async def get_equity_curve(
    backtest_id: UUID,
    conn: asyncpg.Connection = Depends(db_conn),
):
    rows = await conn.fetch(
        "SELECT * FROM backtest_equity_curve WHERE backtest_id=$1 ORDER BY curve_date",
        backtest_id,
    )
    return [_serialize(r) for r in rows]


async def get_trades_for_symbol(
    conn: asyncpg.Connection, symbol: str, limit: int = 50
) -> list[dict]:
    rows = await conn.fetch("""
        SELECT bt.symbol,
               bt.entry_date, bt.exit_date,
               bt.entry_price, bt.exit_price,
               bt.sl_price, bt.t1, bt.t2, bt.t3,
               bt.quantity,
               (bt.quantity * bt.entry_price) AS invested_amount,
               bt.pnl_abs, bt.pnl_pct,
               bt.exit_reason, bt.holding_days, bt.rr_achieved,
               bt.timeframe, bt.category,
               b.started_at AS backtest_date,
               b.id        AS backtest_id
        FROM backtest_trades bt
        JOIN backtests b ON bt.backtest_id = b.id
        WHERE bt.symbol = $1 AND b.status = 'done'
        ORDER BY bt.entry_date DESC
        LIMIT $2
    """, symbol.upper(), limit)
    return [_serialize(r) for r in rows]


# Canonical implementation lives in app/utils/serialization.py
_serialize = serialize_row
